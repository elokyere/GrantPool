"""add_assessment_type

Revision ID: assessment_type_001
Revises: grant_normalization_001
Create Date: 2025-01-15 10:00:00.000000

Adds assessment_type enum to evaluations table for new two-tier framework.
Marks existing evaluations as legacy.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'assessment_type_001'
down_revision: Union[str, None] = 'grant_normalization_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add assessment_type column to evaluations (using String for flexibility)
    op.add_column('evaluations', sa.Column('assessment_type', sa.String(10), nullable=True))
    
    # Add is_legacy column to mark existing evaluations
    op.add_column('evaluations', sa.Column('is_legacy', sa.Boolean(), nullable=True, server_default='false'))
    
    # Set default assessment_type based on evaluation_tier for existing records
    # Free tier -> 'free', refined/standard -> 'paid'
    op.execute("""
        UPDATE evaluations 
        SET assessment_type = CASE 
            WHEN evaluation_tier = 'free' THEN 'free'
            ELSE 'paid'
        END,
        is_legacy = true
        WHERE assessment_type IS NULL
    """)
    
    # Set default for new records (free)
    op.alter_column('evaluations', 'assessment_type', 
                    server_default=sa.text("'free'"),
                    nullable=False)
    
    # Set default for is_legacy (false for new records)
    op.alter_column('evaluations', 'is_legacy',
                    server_default=sa.text('false'),
                    nullable=False)
    
    # Create index for assessment_type
    op.create_index('ix_evaluations_assessment_type', 'evaluations', ['assessment_type'], unique=False)
    
    # Create index for is_legacy
    op.create_index('ix_evaluations_is_legacy', 'evaluations', ['is_legacy'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_evaluations_is_legacy', table_name='evaluations')
    op.drop_index('ix_evaluations_assessment_type', table_name='evaluations')
    
    # Remove columns
    op.drop_column('evaluations', 'is_legacy')
    op.drop_column('evaluations', 'assessment_type')
