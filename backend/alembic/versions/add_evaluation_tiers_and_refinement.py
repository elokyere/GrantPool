"""Add evaluation tiers and refinement support

Revision ID: add_evaluation_tiers
Revises: afa9a777c7ea
Create Date: 2026-01-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_evaluation_tiers'
down_revision: Union[str, None] = 'afa9a777c7ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add evaluation tier fields to evaluations table
    op.add_column('evaluations', sa.Column('evaluation_tier', sa.String(20), nullable=True))
    op.add_column('evaluations', sa.Column('parent_evaluation_id', sa.Integer(), nullable=True))
    op.add_column('evaluations', sa.Column('is_refinement', sa.Boolean(), nullable=True))
    
    # Update existing evaluations to be 'standard' tier (for backward compatibility)
    op.execute("UPDATE evaluations SET evaluation_tier = 'standard' WHERE evaluation_tier IS NULL")
    op.execute("UPDATE evaluations SET is_refinement = false WHERE is_refinement IS NULL")
    
    # Now make columns NOT NULL with defaults
    op.alter_column('evaluations', 'evaluation_tier', nullable=False, server_default='standard')
    op.alter_column('evaluations', 'is_refinement', nullable=False, server_default='false')
    
    # Add foreign key for parent_evaluation_id
    op.create_foreign_key(
        'fk_evaluations_parent_evaluation',
        'evaluations', 'evaluations',
        ['parent_evaluation_id'], ['id'],
        ondelete='SET NULL'
    )
    
    # Add index for parent_evaluation_id
    op.create_index('ix_evaluations_parent_evaluation_id', 'evaluations', ['parent_evaluation_id'])
    
    # Add payment_type to payments table
    op.add_column('payments', sa.Column('payment_type', sa.String(20), nullable=True))
    
    # Update existing payments to be 'standard' type
    op.execute("UPDATE payments SET payment_type = 'standard' WHERE payment_type IS NULL")
    
    # Now make column NOT NULL with default
    op.alter_column('payments', 'payment_type', nullable=False, server_default='standard')


def downgrade() -> None:
    # Remove payment_type from payments
    op.drop_column('payments', 'payment_type')
    
    # Remove evaluation tier fields
    op.drop_index('ix_evaluations_parent_evaluation_id', table_name='evaluations')
    op.drop_constraint('fk_evaluations_parent_evaluation', 'evaluations', type_='foreignkey')
    op.drop_column('evaluations', 'is_refinement')
    op.drop_column('evaluations', 'parent_evaluation_id')
    op.drop_column('evaluations', 'evaluation_tier')

