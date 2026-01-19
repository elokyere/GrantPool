"""
Security middleware for rate limiting, audit logging, and request tracking.
"""

import time
from typing import Callable
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db import models
from app.core.config import settings
from urllib.parse import urlparse


# Rate limiter instance
limiter = Limiter(key_func=get_remote_address)


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Middleware to log all requests for audit purposes."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip logging for health checks and static files
        if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)
        
        # Get user ID from token if available
        user_id = None
        if "authorization" in request.headers:
            try:
                from app.core.security import decode_access_token
                token = request.headers["authorization"].replace("Bearer ", "")
                payload = decode_access_token(token)
                if payload:
                    email = payload.get("sub")
                    if email:
                        db = SessionLocal()
                        try:
                            user = db.query(models.User).filter(models.User.email == email).first()
                            if user:
                                user_id = user.id
                        finally:
                            db.close()
            except Exception:
                pass  # Ignore errors in audit logging
        
        # Get IP and user agent
        ip_address = get_remote_address(request)
        user_agent = request.headers.get("user-agent", "")
        
        # Determine action type
        action = f"{request.method}_{request.url.path.replace('/', '_').replace('-', '_')}"
        if action.startswith("_"):
            action = action[1:]
        
        # Log the request
        db = SessionLocal()
        try:
            audit_log = models.AuditLog(
                user_id=user_id,
                action=action,
                resource_type=None,
                resource_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                log_metadata={
                    "method": request.method,
                    "path": str(request.url.path),
                    "query_params": str(request.query_params),
                }
            )
            db.add(audit_log)
            db.commit()
        except Exception as e:
            db.rollback()
            # Don't fail the request if audit logging fails
            print(f"Audit logging error: {e}")
        finally:
            db.close()
        
        # Process request
        response = await call_next(request)
        return response


def get_rate_limiter():
    """Get the rate limiter instance."""
    return limiter


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection middleware.
    
    For state-changing operations (POST, PUT, DELETE, PATCH), verifies that:
    1. Origin header matches allowed CORS origins (if present)
    2. Referer header matches allowed origins (if Origin not present)
    
    Note: Since we use JWT tokens in Authorization headers (not cookies),
    CSRF risk is already mitigated. This adds defense-in-depth by checking
    Origin/Referer headers.
    
    Skips:
    - GET, HEAD, OPTIONS requests (safe methods)
    - Health checks and API docs
    - Webhook endpoints (they have their own signature verification)
    """
    
    # State-changing HTTP methods
    UNSAFE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
    
    # Paths to skip CSRF checks (webhooks have their own verification)
    SKIP_PATHS = [
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/v1/webhooks",  # Webhooks verify signatures separately
    ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip CSRF check for safe methods
        if request.method not in self.UNSAFE_METHODS:
            return await call_next(request)
        
        # Skip CSRF check for excluded paths
        if any(request.url.path.startswith(path) for path in self.SKIP_PATHS):
            return await call_next(request)
        
        # Get allowed origins from CORS settings
        allowed_origins = settings.cors_origins_list
        
        # If no allowed origins configured, skip check (development mode)
        if not allowed_origins or settings.DEBUG:
            return await call_next(request)
        
        # Get Origin header
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")
        
        # Check Origin header first (most reliable)
        if origin:
            origin_parsed = urlparse(origin)
            origin_base = f"{origin_parsed.scheme}://{origin_parsed.netloc}"
            
            if origin_base not in allowed_origins:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="CSRF protection: Origin not allowed"
                )
            return await call_next(request)
        
        # Fall back to Referer header if Origin not present
        if referer:
            referer_parsed = urlparse(referer)
            referer_base = f"{referer_parsed.scheme}://{referer_parsed.netloc}"
            
            if referer_base not in allowed_origins:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="CSRF protection: Referer not allowed"
                )
            return await call_next(request)
        
        # If neither Origin nor Referer present, allow in development, block in production
        if settings.DEBUG:
            return await call_next(request)
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF protection: Missing Origin or Referer header"
            )
