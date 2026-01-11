"""add_support_requests_and_refund_tracking

Revision ID: 845c7481d2d3
Revises: add_evaluation_tiers
Create Date: 2026-01-06 18:16:41.588652

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '845c7481d2d3'
down_revision: Union[str, None] = 'add_evaluation_tiers'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create support_requests table if it doesn't exist
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    
    if 'support_requests' not in inspector.get_table_names():
        op.create_table(
        'support_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('payment_id', sa.Integer(), nullable=True),  # Optional - may be for general support
        sa.Column('evaluation_id', sa.Integer(), nullable=True),  # Optional - for technical error reports
        sa.Column('issue_type', sa.String(50), nullable=False),  # 'duplicate_payment', 'technical_error', 'payment_issue', 'other'
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),  # 'pending', 'in_review', 'resolved', 'denied'
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('resolution_type', sa.String(20), nullable=True),  # 'credit', 'refund', 'none'
        sa.Column('resolution_amount', sa.Integer(), nullable=True),  # Amount in cents/pesewas
        sa.Column('resolution_currency', sa.String(3), nullable=True),  # USD, GHS, etc.
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column('auto_verified', sa.Boolean(), nullable=False, server_default='false'),  # True if system auto-verified
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ),
        sa.ForeignKeyConstraint(['evaluation_id'], ['evaluations.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_support_requests_user_id'), 'support_requests', ['user_id'], unique=False)
        op.create_index(op.f('ix_support_requests_status'), 'support_requests', ['status'], unique=False)
        op.create_index(op.f('ix_support_requests_issue_type'), 'support_requests', ['issue_type'], unique=False)
    
    # Add refund tracking columns to payments table if they don't exist
    payments_columns = [col['name'] for col in inspector.get_columns('payments')]
    
    if 'refund_status' not in payments_columns:
        op.add_column('payments', sa.Column('refund_status', sa.String(20), nullable=True))  # 'none', 'requested', 'approved', 'processed', 'denied'
    if 'refund_amount' not in payments_columns:
        op.add_column('payments', sa.Column('refund_amount', sa.Integer(), nullable=True))  # Amount refunded
    if 'refund_reason' not in payments_columns:
        op.add_column('payments', sa.Column('refund_reason', sa.Text(), nullable=True))  # Reason for refund
    if 'refunded_at' not in payments_columns:
        op.add_column('payments', sa.Column('refunded_at', sa.DateTime(timezone=True), nullable=True))
    if 'refund_metadata' not in payments_columns:
        op.add_column('payments', sa.Column('refund_metadata', sa.JSON(), nullable=True))  # Additional refund info


def downgrade() -> None:
    # Remove refund tracking columns from payments
    op.drop_column('payments', 'refund_metadata')
    op.drop_column('payments', 'refunded_at')
    op.drop_column('payments', 'refund_reason')
    op.drop_column('payments', 'refund_amount')
    op.drop_column('payments', 'refund_status')
    
    # Drop support_requests table
    op.drop_index(op.f('ix_support_requests_issue_type'), table_name='support_requests')
    op.drop_index(op.f('ix_support_requests_status'), table_name='support_requests')
    op.drop_index(op.f('ix_support_requests_user_id'), table_name='support_requests')
    op.drop_table('support_requests')

