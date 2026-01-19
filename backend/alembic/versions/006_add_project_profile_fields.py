"""add_project_profile_fields

Revision ID: project_profile_001
Revises: assessment_type_001
Create Date: 2025-01-15 10:00:00.000000

Adds new project profile columns for enhanced project data.
Uses hybrid approach: core fields as columns, extended fields in JSONB.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'project_profile_001'
down_revision: Union[str, None] = 'assessment_type_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add core project profile columns (required for paid assessments)
    op.add_column('projects', sa.Column('organization_country', sa.String(2), nullable=True))
    op.add_column('projects', sa.Column('organization_type', sa.String(50), nullable=True))
    op.add_column('projects', sa.Column('funding_need_amount', sa.Integer(), nullable=True))  # Amount in cents
    op.add_column('projects', sa.Column('funding_need_currency', sa.String(3), nullable=True))  # ISO 4217 code
    op.add_column('projects', sa.Column('has_prior_grants', sa.Boolean(), nullable=True))
    
    # Add JSONB field for extended/evolving fields
    op.add_column('projects', sa.Column('profile_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    
    # Create indexes for commonly queried fields
    op.create_index('ix_projects_organization_country', 'projects', ['organization_country'], unique=False)
    op.create_index('ix_projects_organization_type', 'projects', ['organization_type'], unique=False)
    op.create_index('ix_projects_funding_need_currency', 'projects', ['funding_need_currency'], unique=False)
    
    # Create GIN index for JSONB field (for efficient JSON queries)
    op.execute("CREATE INDEX IF NOT EXISTS ix_projects_profile_metadata ON projects USING GIN (profile_metadata)")


def downgrade() -> None:
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS ix_projects_profile_metadata")
    op.drop_index('ix_projects_funding_need_currency', table_name='projects')
    op.drop_index('ix_projects_organization_type', table_name='projects')
    op.drop_index('ix_projects_organization_country', table_name='projects')
    
    # Remove columns
    op.drop_column('projects', 'profile_metadata')
    op.drop_column('projects', 'has_prior_grants')
    op.drop_column('projects', 'funding_need_currency')
    op.drop_column('projects', 'funding_need_amount')
    op.drop_column('projects', 'organization_type')
    op.drop_column('projects', 'organization_country')
