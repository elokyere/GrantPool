"""add_grant_approval_status

Revision ID: grant_approval_001
Revises: 845c7481d2d3
Create Date: 2026-01-05 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'grant_approval_001'
down_revision: Union[str, None] = '845c7481d2d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add approval status fields to grants table
    op.add_column('grants', sa.Column('approval_status', sa.String(), server_default='pending', nullable=False))
    op.add_column('grants', sa.Column('approved_by', sa.Integer(), nullable=True))
    op.add_column('grants', sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('grants', sa.Column('rejection_reason', sa.Text(), nullable=True))
    
    # Create foreign key for approved_by
    op.create_foreign_key(
        'fk_grants_approved_by_users',
        'grants', 'users',
        ['approved_by'], ['id'],
        ondelete='SET NULL'
    )
    
    # Set existing grants to 'approved' status
    op.execute("UPDATE grants SET approval_status = 'approved' WHERE approval_status = 'pending'")


def downgrade() -> None:
    # Drop foreign key
    op.drop_constraint('fk_grants_approved_by_users', 'grants', type_='foreignkey')
    
    # Drop columns
    op.drop_column('grants', 'rejection_reason')
    op.drop_column('grants', 'approved_at')
    op.drop_column('grants', 'approved_by')
    op.drop_column('grants', 'approval_status')

