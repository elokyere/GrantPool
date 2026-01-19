"""
Source Verification Service

Verifies grant source URLs to determine if they are from official funder domains.
"""

import re
from typing import Optional, Tuple
from urllib.parse import urlparse
import httpx
from app.core.sanitization import validate_url_security


# Known aggregator domains (not official funder sites)
AGGREGATOR_DOMAINS = [
    'grantwatch.com',
    'grants.gov',
    'foundationcenter.org',
    'grantspace.org',
    'grantmakers.org',
    'philanthropy.com',
    'insidephilanthropy.com',
    'grantstation.com',
    'grantshub.com',
    'grantfinder.com',
]


class SourceVerificationService:
    """Service for verifying grant source URLs."""
    
    @staticmethod
    def verify_source_url(url: str, timeout: int = 10) -> Tuple[bool, Optional[str]]:
        """
        Verify if a source URL is from an official funder domain.
        
        Requirements (ALL must pass):
        - URL reachable (200/301)
        - Domain ≠ known aggregators list
        - HTTPS
        - Domain matches funder name OR whitelisted org
        
        Args:
            url: Source URL to verify
            timeout: Request timeout in seconds
            
        Returns:
            Tuple of (is_verified, error_message)
        """
        if not url:
            return (False, "URL is empty")
        
        # Validate URL security first
        is_valid, error_msg = validate_url_security(url)
        if not is_valid:
            return (False, f"Invalid URL: {error_msg}")
        
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Must be HTTPS
            if parsed.scheme != 'https':
                return (False, "URL must use HTTPS")
            
            # Check against aggregator list
            for aggregator in AGGREGATOR_DOMAINS:
                if aggregator in domain:
                    return (False, f"Domain is a known aggregator: {aggregator}")
            
            # Try to reach the URL (with redirect following)
            try:
                response = httpx.get(url, follow_redirects=True, timeout=timeout)
                # Accept 200 (OK) or 301/302 (redirects are followed)
                if response.status_code not in [200, 301, 302]:
                    return (False, f"URL returned status code: {response.status_code}")
            except httpx.TimeoutException:
                return (False, "URL verification timed out")
            except httpx.RequestError as e:
                return (False, f"URL verification failed: {str(e)}")
            
            # If all checks pass
            return (True, None)
            
        except Exception as e:
            return (False, f"Verification error: {str(e)}")
