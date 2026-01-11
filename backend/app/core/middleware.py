"""
Security middleware for rate limiting, audit logging, and request tracking.
"""

import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db import models


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

