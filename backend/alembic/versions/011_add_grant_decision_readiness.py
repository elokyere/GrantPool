"""Add grant decision readiness system

Revision ID: decision_readiness_001
Revises: contributions_001
Create Date: 2025-01-14 12:00:00.000000

Adds decision readiness indicators and related fields to grants table.
This replaces the opaque "Data: X/10" score with explainable bucket states.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'decision_readiness_001'
down_revision: str = 'contributions_001'
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    # Create ENUM types for bucket states (only if they don't exist)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE bucket_state AS ENUM ('known', 'partial', 'unknown');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE grant_scope AS ENUM ('Local', 'National', 'International', 'Unclear');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Add bucket state columns (5 decision readiness indicators)
    op.add_column('grants', sa.Column('timeline_clarity', sa.Enum('known', 'partial', 'unknown', name='bucket_state'), nullable=True))
    op.add_column('grants', sa.Column('winner_signal', sa.Enum('known', 'partial', 'unknown', name='bucket_state'), nullable=True))
    op.add_column('grants', sa.Column('mission_specificity', sa.Enum('known', 'partial', 'unknown', name='bucket_state'), nullable=True))
    op.add_column('grants', sa.Column('application_burden', sa.Enum('known', 'partial', 'unknown', name='bucket_state'), nullable=True))
    op.add_column('grants', sa.Column('award_structure_clarity', sa.Enum('known', 'partial', 'unknown', name='bucket_state'), nullable=True))
    
    # Add derived/computed fields
    op.add_column('grants', sa.Column('decision_readiness', sa.String(length=50), nullable=True))
    op.add_column('grants', sa.Column('status_of_knowledge', sa.String(length=50), nullable=True))
    op.add_column('grants', sa.Column('scope', sa.Enum('Local', 'National', 'International', 'Unclear', name='grant_scope'), nullable=True))
    
    # Add source verification fields
    op.add_column('grants', sa.Column('source_verified', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('grants', sa.Column('source_verified_checked_at', sa.DateTime(timezone=True), nullable=True))
    
    # Add evaluation completion flag
    op.add_column('grants', sa.Column('evaluation_complete', sa.Boolean(), nullable=False, server_default='false'))
    
    # Create indexes for filtering and sorting
    op.create_index('ix_grants_decision_readiness', 'grants', ['decision_readiness'], unique=False)
    op.create_index('ix_grants_status_of_knowledge', 'grants', ['status_of_knowledge'], unique=False)
    op.create_index('ix_grants_scope', 'grants', ['scope'], unique=False)
    op.create_index('ix_grants_evaluation_complete', 'grants', ['evaluation_complete'], unique=False)
    op.create_index('ix_grants_source_verified', 'grants', ['source_verified'], unique=False)
    
    # Composite index for common queries
    op.create_index('idx_grants_readiness_complete', 'grants', ['decision_readiness', 'evaluation_complete'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_grants_readiness_complete', table_name='grants')
    op.drop_index('ix_grants_source_verified', table_name='grants')
    op.drop_index('ix_grants_evaluation_complete', table_name='grants')
    op.drop_index('ix_grants_scope', table_name='grants')
    op.drop_index('ix_grants_status_of_knowledge', table_name='grants')
    op.drop_index('ix_grants_decision_readiness', table_name='grants')
    
    # Drop columns
    op.drop_column('grants', 'evaluation_complete')
    op.drop_column('grants', 'source_verified_checked_at')
    op.drop_column('grants', 'source_verified')
    op.drop_column('grants', 'scope')
    op.drop_column('grants', 'status_of_knowledge')
    op.drop_column('grants', 'decision_readiness')
    op.drop_column('grants', 'award_structure_clarity')
    op.drop_column('grants', 'application_burden')
    op.drop_column('grants', 'mission_specificity')
    op.drop_column('grants', 'winner_signal')
    op.drop_column('grants', 'timeline_clarity')
    
    # Drop ENUM types
    op.execute("DROP TYPE IF EXISTS grant_scope")
    op.execute("DROP TYPE IF EXISTS bucket_state")
