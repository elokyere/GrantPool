"""Add credit conversion tracking to payments

Revision ID: credit_conversion_001
Revises: grant_patterns_001
Create Date: 2025-01-XX XX:XX:XX.XXXXXX

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'credit_conversion_001'
down_revision: str = 'grant_patterns_001'  # Matches revision from 007_add_grant_recipient_patterns.py
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    # Add converted_to_credit field to track if refinement payment has been converted
    op.add_column('payments', sa.Column('converted_to_credit', sa.Boolean(), nullable=True, server_default='false'))
    
    # Create index for faster queries
    op.create_index(op.f('ix_payments_converted_to_credit'), 'payments', ['converted_to_credit'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_payments_converted_to_credit'), table_name='payments')
    op.drop_column('payments', 'converted_to_credit')
