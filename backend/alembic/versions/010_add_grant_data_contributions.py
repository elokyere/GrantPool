"""Add grant data contributions table

Revision ID: contributions_001
Revises: credit_conversion_001
Create Date: 2025-01-18 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'contributions_001'
down_revision: str = 'nullable_fit_fields_001'  # Matches revision from 009_make_fit_fields_nullable.py
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    # Create grant_data_contributions table
    op.create_table(
        'grant_data_contributions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('grant_id', sa.Integer(), nullable=True),
        sa.Column('evaluation_id', sa.Integer(), nullable=True),
        sa.Column('grant_name', sa.String(), nullable=True),
        sa.Column('grant_url', sa.String(), nullable=True),
        sa.Column('field_name', sa.String(length=50), nullable=False),
        sa.Column('field_value', sa.Text(), nullable=False),
        sa.Column('source_url', sa.String(), nullable=True),
        sa.Column('source_description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['grant_id'], ['grants.id'], ),
        sa.ForeignKeyConstraint(['evaluation_id'], ['evaluations.id'], ),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_grant_data_contributions_id'), 'grant_data_contributions', ['id'], unique=False)
    op.create_index(op.f('ix_grant_data_contributions_user_id'), 'grant_data_contributions', ['user_id'], unique=False)
    op.create_index(op.f('ix_grant_data_contributions_grant_id'), 'grant_data_contributions', ['grant_id'], unique=False)
    op.create_index(op.f('ix_grant_data_contributions_evaluation_id'), 'grant_data_contributions', ['evaluation_id'], unique=False)
    op.create_index(op.f('ix_grant_data_contributions_field_name'), 'grant_data_contributions', ['field_name'], unique=False)
    op.create_index(op.f('ix_grant_data_contributions_status'), 'grant_data_contributions', ['status'], unique=False)
    op.create_index(op.f('ix_grant_data_contributions_created_at'), 'grant_data_contributions', ['created_at'], unique=False)
    
    # Create composite indexes
    op.create_index('idx_contributions_grant_status', 'grant_data_contributions', ['grant_id', 'status'], unique=False)
    op.create_index('idx_contributions_user_status', 'grant_data_contributions', ['user_id', 'status'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_contributions_user_status', table_name='grant_data_contributions')
    op.drop_index('idx_contributions_grant_status', table_name='grant_data_contributions')
    op.drop_index(op.f('ix_grant_data_contributions_created_at'), table_name='grant_data_contributions')
    op.drop_index(op.f('ix_grant_data_contributions_status'), table_name='grant_data_contributions')
    op.drop_index(op.f('ix_grant_data_contributions_field_name'), table_name='grant_data_contributions')
    op.drop_index(op.f('ix_grant_data_contributions_evaluation_id'), table_name='grant_data_contributions')
    op.drop_index(op.f('ix_grant_data_contributions_grant_id'), table_name='grant_data_contributions')
    op.drop_index(op.f('ix_grant_data_contributions_user_id'), table_name='grant_data_contributions')
    op.drop_index(op.f('ix_grant_data_contributions_id'), table_name='grant_data_contributions')
    
    # Drop table
    op.drop_table('grant_data_contributions')
