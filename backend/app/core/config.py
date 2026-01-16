"""
Application configuration using Pydantic settings.
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings."""
    
    # Database
    DATABASE_URL: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    
    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Anthropic API (optional - only needed for LLM evaluations)
    ANTHROPIC_API_KEY: str = ""
    
    # Paystack Payment Configuration
    PAYSTACK_SECRET_KEY: str = ""
    PAYSTACK_PUBLIC_KEY: str = ""
    PAYSTACK_WEBHOOK_SECRET: str = ""
    
    # Application URL (for Paystack callback)
    APP_URL: str = "http://localhost:8000"  # Update in production
    FRONTEND_URL: str = "http://localhost:3000"  # Frontend URL for payment redirects
    
    # Payment Pricing - Model B: Free → Refine → Standard → Bundle
    # USD prices are reference only (for display)
    USD_PRICE_REFINEMENT: int = 300  # $3.00 in cents (refinement unlock)
    USD_PRICE_STANDARD: int = 700  # $7.00 in cents (standard assessment)
    USD_PRICE_BUNDLE: int = 1800  # $18.00 in cents (3 assessments bundle)
    # GHS prices are locked and authoritative (all payments charged in GHS)
    GHS_PRICE_REFINEMENT: int = 3217  # 32.17 GHS in pesewas (≈$3.00)
    GHS_PRICE_STANDARD: int = 7507  # 75.07 GHS in pesewas (≈$7.00)
    GHS_PRICE_BUNDLE: int = 19305  # 193.05 GHS in pesewas (≈$18.00)
    
    # Legacy pricing (for backward compatibility)
    USD_PRICE: int = 700  # $7.00 in cents (defaults to standard)
    GHS_PRICE: int = 2800  # 28.00 GHS in pesewas (defaults to standard)
    
    # Email Configuration
    EMAIL_PROVIDER: str = "smtp"  # Options: "smtp", "sendgrid", "ses"
    EMAIL_FROM: str = "noreply@grantpool.org"
    EMAIL_FROM_NAME: str = "GrantPool"
    
    # SMTP Configuration (for EMAIL_PROVIDER="smtp")
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    
    # SendGrid Configuration (for EMAIL_PROVIDER="sendgrid")
    SENDGRID_API_KEY: str = ""
    
    # AWS SES Configuration (for EMAIL_PROVIDER="ses")
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    
    # Slack Configuration (admin orchestration only)
    SLACK_SIGNING_SECRET: str = ""
    SLACK_WORKSPACE_ID: str = ""  # Allowlist: only accept from this workspace
    SLACK_ADMIN_USER_IDS: str = ""  # Comma-separated allowlist of admin user IDs
    SLACK_WEBHOOK_URL: str = ""  # Incoming webhook for notifications
    
    # Application
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001,http://localhost:5173"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        # In production, filter out localhost origins
        if not self.DEBUG:
            origins = [origin for origin in origins if not origin.startswith("http://localhost")]
        return origins
    
    def validate_secret_key(self) -> bool:
        """Validate that SECRET_KEY is strong enough."""
        if len(self.SECRET_KEY) < 32:
            raise ValueError(
                f"SECRET_KEY must be at least 32 characters long. "
                f"Current length: {len(self.SECRET_KEY)}. "
                f"Generate a new one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        return True
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra environment variables


settings = Settings()

# Validate SECRET_KEY strength in production
if not settings.DEBUG:
    try:
        settings.validate_secret_key()
    except ValueError as e:
        import warnings
        warnings.warn(str(e), UserWarning)