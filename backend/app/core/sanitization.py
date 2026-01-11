"""
Input sanitization utilities to prevent XSS attacks and dangerous URL insertion.
"""

import bleach
import re
import ipaddress
from urllib.parse import urlparse, parse_qs
from typing import Optional

# Allowed HTML tags for rich text content
ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'a', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']

# Allowed attributes per tag
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target'],
    'p': [],
    'br': [],
    'strong': [],
    'em': [],
    'ul': [],
    'ol': [],
    'li': [],
    'h1': [],
    'h2': [],
    'h3': [],
    'h4': [],
    'h5': [],
    'h6': [],
}

# Allowed URL schemes for links (only HTTP/HTTPS for grant URLs)
ALLOWED_SCHEMES = ['http', 'https']

# Dangerous protocols that should never be allowed
DANGEROUS_PROTOCOLS = [
    'javascript', 'data', 'file', 'ftp', 'gopher', 'jar', 'vbscript',
    'about', 'chrome', 'chrome-extension', 'ms-help', 'mhtml',
    'mk', 'onenote', 'res', 'telnet', 'view-source', 'ws', 'wss'
]

# Private/internal IP ranges (RFC 1918, RFC 4193, localhost, etc.)
PRIVATE_IP_RANGES = [
    ipaddress.IPv4Network('10.0.0.0/8'),
    ipaddress.IPv4Network('172.16.0.0/12'),
    ipaddress.IPv4Network('192.168.0.0/16'),
    ipaddress.IPv4Network('127.0.0.0/8'),
    ipaddress.IPv4Network('169.254.0.0/16'),  # Link-local
    ipaddress.IPv4Network('224.0.0.0/4'),      # Multicast
    ipaddress.IPv6Network('fc00::/7'),         # RFC 4193
    ipaddress.IPv6Network('fe80::/10'),        # Link-local
    ipaddress.IPv6Network('::1/128'),          # localhost
]

# Maximum URL length
MAX_URL_LENGTH = 2048


def sanitize_html(text: str) -> str:
    """
    Sanitize HTML input to prevent XSS attacks.
    
    Args:
        text: HTML string to sanitize
        
    Returns:
        Sanitized HTML string
    """
    if not text:
        return ""
    
    return bleach.clean(
        text,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_SCHEMES,
        strip=True
    )


def sanitize_text(text: str) -> str:
    """
    Sanitize plain text input by removing all HTML.
    
    Args:
        text: Text string to sanitize
        
    Returns:
        Plain text string with HTML removed
    """
    if not text:
        return ""
    
    return bleach.clean(text, tags=[], strip=True)


def is_private_ip(host: str) -> bool:
    """
    Check if host is a private/internal IP address.
    
    Args:
        host: Hostname or IP address
        
    Returns:
        True if host is a private IP, False otherwise
    """
    try:
        # Try to resolve hostname to IP
        import socket
        try:
            ip_addr = socket.gethostbyname(host)
        except (socket.gaierror, socket.herror):
            # If can't resolve, check if it's already an IP
            try:
                ip_addr = host
            except:
                return False
        
        # Check if it's an IPv4 private IP
        try:
            ip = ipaddress.IPv4Address(ip_addr)
            for private_range in PRIVATE_IP_RANGES[:5]:  # IPv4 ranges only
                if ip in private_range:
                    return True
        except:
            pass
        
        # Check if it's an IPv6 private IP
        try:
            ip = ipaddress.IPv6Address(ip_addr)
            for private_range in PRIVATE_IP_RANGES[5:]:  # IPv6 ranges
                if ip in private_range:
                    return True
        except:
            pass
            
    except Exception:
        pass
    
    return False


def validate_url_security(url: str) -> tuple[bool, Optional[str]]:
    """
    Validate URL security - check for SSRF, dangerous protocols, etc.
    
    Args:
        url: URL string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url:
        return False, "URL cannot be empty"
    
    # Check length
    if len(url) > MAX_URL_LENGTH:
        return False, f"URL exceeds maximum length of {MAX_URL_LENGTH} characters"
    
    # Remove any HTML tags
    url = bleach.clean(url, tags=[], strip=True)
    
    if not url:
        return False, "URL is empty after sanitization"
    
    # Normalize protocol-relative URLs
    url_lower = url.lower().strip()
    if url_lower.startswith('//'):
        url = f"https:{url}"
    
    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Invalid URL format: {str(e)}"
    
    # Check protocol/scheme
    scheme = parsed.scheme.lower()
    
    # Reject dangerous protocols
    if scheme in DANGEROUS_PROTOCOLS:
        return False, f"Dangerous protocol '{scheme}' is not allowed"
    
    # Only allow HTTP/HTTPS for grant URLs
    if scheme not in ALLOWED_SCHEMES:
        return False, f"Only HTTP and HTTPS protocols are allowed, got '{scheme}'"
    
    # Check for suspicious characters in scheme
    if not re.match(r'^[a-z][a-z0-9+.-]*$', scheme):
        return False, "Invalid URL scheme format"
    
    # Get hostname
    hostname = parsed.netloc.split(':')[0]  # Remove port if present
    
    if not hostname:
        return False, "URL must have a valid hostname"
    
    # Check for IP addresses
    try:
        # Check if hostname is an IP address
        ipaddress.ip_address(hostname)
        # If it's an IP, check if it's private
        if is_private_ip(hostname):
            return False, "Private/internal IP addresses are not allowed (SSRF protection)"
    except ValueError:
        # Not an IP address, continue with hostname validation
        pass
    
    # Check hostname format
    if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$', hostname):
        return False, "Invalid hostname format"
    
    # Check for localhost variations
    localhost_variants = ['localhost', '127.0.0.1', '0.0.0.0', '::1', '0:0:0:0:0:0:0:1']
    if hostname.lower() in localhost_variants or hostname.lower().endswith('.localhost'):
        return False, "localhost addresses are not allowed (SSRF protection)"
    
    # Check for suspicious patterns in path
    suspicious_paths = [
        'file://', 'javascript:', 'data:', 'vbscript:',
        '@localhost', '@127.0.0.1', '@0.0.0.0'
    ]
    path_lower = parsed.path.lower()
    for suspicious in suspicious_paths:
        if suspicious in path_lower:
            return False, f"Suspicious pattern detected in URL path"
    
    # Check for excessive encoding (potential obfuscation)
    encoded_percentage = (url.count('%') / len(url)) * 100
    if encoded_percentage > 30:
        return False, "URL contains excessive encoding (potential obfuscation)"
    
    return True, None


def sanitize_url(url: str) -> str:
    """
    Sanitize and validate URL to prevent XSS, SSRF, and malicious links.
    
    Args:
        url: URL string to sanitize
        
    Returns:
        Sanitized URL or raises ValueError if invalid/dangerous
    """
    if not url:
        return ""
    
    # Validate URL security
    is_valid, error_msg = validate_url_security(url)
    if not is_valid:
        raise ValueError(error_msg or "Invalid URL")
    
    # Clean HTML tags
    url = bleach.clean(url, tags=[], strip=True)
    
    # Normalize protocol-relative URLs
    url_lower = url.lower().strip()
    if url_lower.startswith('//'):
        url = f"https:{url}"
    
    # Parse and reconstruct to normalize
    try:
        parsed = urlparse(url)
        # Reconstruct URL with only safe components
        # Remove query and fragment to prevent injection
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return normalized
    except Exception:
        raise ValueError("Failed to parse URL")


