"""
Database connection and session management.
"""

from sqlalchemy import create_engine
from sqlalchemy.sql import text as sa_text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

# SQLAlchemy 2.0+ supports both psycopg (v3) and psycopg2
# If DATABASE_URL uses postgresql://, we need to ensure it uses psycopg
# Convert postgresql:// to postgresql+psycopg:// if psycopg is available
database_url = settings.DATABASE_URL
if database_url.startswith("postgresql://") and not database_url.startswith("postgresql+psycopg"):
    # Try to use psycopg if available (Python 3.13 compatible)
    try:
        import psycopg
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    except ImportError:
        # Fall back to psycopg2 if psycopg not available
        pass

engine = create_engine(
    database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def set_user_context(db: Session, user_id: int):
    """
    Set user context for Row Level Security (RLS).
    
    This sets a session variable that RLS policies can use to filter data.
    Call this before database operations that need RLS filtering.
    
    Args:
        db: Database session
        user_id: Current user ID
    """
    db.execute(sa_text(f"SET LOCAL app.user_id = {user_id}"))
    db.commit()

