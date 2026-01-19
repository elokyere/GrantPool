"""Make mission_alignment and winner_pattern_match nullable for free tier assessments

Revision ID: nullable_fit_fields_001
Revises: credit_conversion_001
Create Date: 2025-01-17 17:45:00.000000

Free tier assessments don't assess fit/match (no project data), so these fields
should be NULL for free assessments and populated for paid assessments.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'nullable_fit_fields_001'
down_revision: str = 'credit_conversion_001'
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    # Make mission_alignment and winner_pattern_match nullable
    # Free tier assessments don't assess fit, so these should be NULL
    op.alter_column('evaluations', 'mission_alignment',
                    existing_type=sa.Integer(),
                    nullable=True)
    
    op.alter_column('evaluations', 'winner_pattern_match',
                    existing_type=sa.Integer(),
                    nullable=True)


def downgrade() -> None:
    # Revert to NOT NULL (will fail if there are NULL values)
    op.alter_column('evaluations', 'mission_alignment',
                    existing_type=sa.Integer(),
                    nullable=False,
                    server_default='0')
    
    op.alter_column('evaluations', 'winner_pattern_match',
                    existing_type=sa.Integer(),
                    nullable=False,
                    server_default='0')
