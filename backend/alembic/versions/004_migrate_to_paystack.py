"""Migrate from Stripe to Paystack

Revision ID: 004_migrate_to_paystack
Revises: 003_add_payment_tables
Create Date: 2024-01-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004_migrate_to_paystack'
down_revision = '003_add_payment_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename Stripe columns to Paystack in users table
    op.alter_column('users', 'stripe_customer_id', 
                    new_column_name='paystack_customer_code',
                    existing_type=sa.String(255),
                    existing_nullable=True)
    op.drop_index('ix_users_stripe_customer_id', table_name='users')
    op.create_index('ix_users_paystack_customer_code', 'users', ['paystack_customer_code'], unique=True)
    
    # Rename Stripe columns to Paystack in payments table
    op.alter_column('payments', 'stripe_payment_intent_id', 
                    new_column_name='paystack_reference',
                    existing_type=sa.String(255),
                    existing_nullable=True)
    op.alter_column('payments', 'stripe_customer_id', 
                    new_column_name='paystack_customer_code',
                    existing_type=sa.String(255),
                    existing_nullable=True)
    
    # Rename metadata to payment_metadata (SQLAlchemy reserved word)
    op.alter_column('payments', 'metadata', 
                    new_column_name='payment_metadata',
                    existing_type=sa.JSON,
                    existing_nullable=True)
    
    # Rename metadata to log_metadata in audit_logs (SQLAlchemy reserved word)
    op.alter_column('audit_logs', 'metadata', 
                    new_column_name='log_metadata',
                    existing_type=sa.JSON,
                    existing_nullable=True)
    
    # Update indexes
    op.drop_index('ix_payments_stripe_payment_intent_id', table_name='payments')
    op.create_index('ix_payments_paystack_reference', 'payments', ['paystack_reference'], unique=True)


def downgrade() -> None:
    # Revert to Stripe column names
    op.drop_index('ix_payments_paystack_reference', table_name='payments')
    op.create_index('ix_payments_stripe_payment_intent_id', 'payments', ['paystack_reference'], unique=True)
    
    op.alter_column('audit_logs', 'log_metadata', 
                    new_column_name='metadata',
                    existing_type=sa.JSON,
                    existing_nullable=True)
    
    op.alter_column('payments', 'payment_metadata', 
                    new_column_name='metadata',
                    existing_type=sa.JSON,
                    existing_nullable=True)
    
    op.alter_column('payments', 'paystack_customer_code', 
                    new_column_name='stripe_customer_id',
                    existing_type=sa.String(255),
                    existing_nullable=True)
    op.alter_column('payments', 'paystack_reference', 
                    new_column_name='stripe_payment_intent_id',
                    existing_type=sa.String(255),
                    existing_nullable=True)
    
    op.drop_index('ix_users_paystack_customer_code', table_name='users')
    op.create_index('ix_users_stripe_customer_id', 'users', ['paystack_customer_code'], unique=True)
    op.alter_column('users', 'paystack_customer_code', 
                    new_column_name='stripe_customer_id',
                    existing_type=sa.String(255),
                    existing_nullable=True)

