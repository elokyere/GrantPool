"""Rename founder_fit to winner_pattern_match

Revision ID: 002_rename_founder_fit
Revises: 001_initial
Create Date: 2024-01-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002_rename_founder_fit'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename column from founder_fit to winner_pattern_match
    op.alter_column('evaluations', 'founder_fit', 
                    new_column_name='winner_pattern_match',
                    existing_type=sa.Integer(),
                    existing_nullable=False)


def downgrade() -> None:
    # Rename column back from winner_pattern_match to founder_fit
    op.alter_column('evaluations', 'winner_pattern_match', 
                    new_column_name='founder_fit',
                    existing_type=sa.Integer(),
                    existing_nullable=False)














