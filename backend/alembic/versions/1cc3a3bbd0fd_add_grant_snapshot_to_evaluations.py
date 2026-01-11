"""add_grant_snapshot_to_evaluations

Revision ID: 1cc3a3bbd0fd
Revises: grant_approval_001
Create Date: 2026-01-07 15:11:20.054030

Add grant snapshot fields to evaluations for Option A: in-memory grants.
Evaluations can now store grant data directly without requiring a grant_id.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '1cc3a3bbd0fd'
down_revision: Union[str, None] = 'grant_approval_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add grant snapshot fields to evaluations
    op.add_column('evaluations', sa.Column('grant_url', sa.String(), nullable=True))
    op.add_column('evaluations', sa.Column('grant_name', sa.String(), nullable=True))
    op.add_column('evaluations', sa.Column('grant_snapshot_json', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    
    # Make grant_id nullable to support evaluations without DB grants (Option A)
    op.alter_column('evaluations', 'grant_id', nullable=True)


def downgrade() -> None:
    # Remove grant snapshot fields
    op.drop_column('evaluations', 'grant_snapshot_json')
    op.drop_column('evaluations', 'grant_name')
    op.drop_column('evaluations', 'grant_url')
    
    # Make grant_id NOT NULL again (but first need to ensure all evaluations have grant_id)
    # Note: This might fail if there are evaluations with NULL grant_id
    op.execute("UPDATE evaluations SET grant_id = 1 WHERE grant_id IS NULL")
    op.alter_column('evaluations', 'grant_id', nullable=False)

