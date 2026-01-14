"""
GrantPool Backend API

FastAPI application for grant evaluation and management.
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import traceback
import logging

from app.core.config import settings
from app.core.middleware import AuditLogMiddleware, get_rate_limiter
from app.api.v1 import api_router
from app.db.database import engine
from app.db import models

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for startup and shutdown."""
    # Startup
    models.Base.metadata.create_all(bind=engine)
    yield
    # Shutdown
    pass


app = FastAPI(
    title="GrantPool API",
    description="Decisive grant triage system API",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiter
limiter = get_rate_limiter()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Global exception handler to ensure CORS headers in error responses
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler that ensures CORS headers are included."""
    # Log full error details server-side
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    # For production, use generic error message
    if settings.DEBUG:
        error_detail = str(exc)
        error_detail += f"\n{traceback.format_exc()}"
    else:
        error_detail = "An internal error occurred. Please contact support if this persists."
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": error_detail},
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )


# HTTPS enforcement middleware (production only)
@app.middleware("http")
async def https_redirect_middleware(request: Request, call_next):
    """Redirect HTTP to HTTPS in production."""
    # Skip HTTPS redirect for health checks (internal monitoring uses HTTP)
    if request.url.path == "/health":
        return await call_next(request)
    
    if not settings.DEBUG and request.url.scheme != "https":
        # Redirect to HTTPS
        https_url = str(request.url).replace("http://", "https://", 1)
        return RedirectResponse(url=https_url, status_code=301)
    return await call_next(request)


# Security headers middleware
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    
    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # HSTS header (HTTPS only, production only)
    if not settings.DEBUG and request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    
    return response

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Audit logging middleware
app.add_middleware(AuditLogMiddleware)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "GrantPool API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Include API routes
# IMPORTANT: With preserve_path_prefix=true in Digital Ocean ingress,
# the /api prefix is PRESERVED when forwarding to backend.
# So /api/v1/* requests arrive at backend as /api/v1/*
# Therefore, we must use /api/v1 prefix here to match.
app.include_router(api_router, prefix="/api/v1")

