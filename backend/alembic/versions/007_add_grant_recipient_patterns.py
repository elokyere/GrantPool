"""add_grant_recipient_patterns

Revision ID: grant_patterns_001
Revises: project_profile_001
Create Date: 2025-01-15 10:00:00.000000

Adds recipient_patterns JSONB field to grants table for storing recipient data
and competition statistics with source/confidence tagging.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'grant_patterns_001'
down_revision: Union[str, None] = 'project_profile_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add recipient_patterns JSONB field to grants table
    op.add_column('grants', sa.Column('recipient_patterns', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    
    # Create GIN index for efficient JSON queries
    op.execute("CREATE INDEX IF NOT EXISTS ix_grants_recipient_patterns ON grants USING GIN (recipient_patterns)")
    
    # Example structure (documented, not enforced):
    # {
    #   "recipients": [
    #     {
    #       "career_stage": "Mid-career",
    #       "career_stage_confidence": "high",
    #       "career_stage_source": "llm",
    #       "organization_type": "NGO",
    #       "organization_type_confidence": "high",
    #       "organization_type_source": "llm",
    #       "country": "Kenya",
    #       "country_confidence": "medium",
    #       "country_source": "llm",
    #       "education_level": "Graduate",
    #       "education_level_confidence": "low",
    #       "education_level_source": "llm",
    #       "year": 2023,
    #       "locked": false
    #     }
    #   ],
    #   "competition_stats": {
    #     "applications_received": 150,
    #     "awards_made": 25,
    #     "acceptance_rate": 12.5,
    #     "year": 2023,
    #     "source": "official",
    #     "confidence": "high",
    #     "notes": "Explicitly stated on grant page"
    #   }
    # }


def downgrade() -> None:
    # Drop index
    op.execute("DROP INDEX IF EXISTS ix_grants_recipient_patterns")
    
    # Remove column
    op.drop_column('grants', 'recipient_patterns')
