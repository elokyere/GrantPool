"""add_grant_normalization_fields

Revision ID: grant_normalization_001
Revises: 1cc3a3bbd0fd
Create Date: 2026-01-14 12:00:00.000000

Adds raw data fields to Grant table and creates GrantNormalization table
for two-layer data model: immutable source of record + editable presentation layer.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'grant_normalization_001'
down_revision: Union[str, None] = '1cc3a3bbd0fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add raw data fields to grants table (Source of Record - immutable)
    op.add_column('grants', sa.Column('raw_title', sa.String(), nullable=True))
    op.add_column('grants', sa.Column('raw_content', sa.Text(), nullable=True))
    op.add_column('grants', sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=True))
    
    # Backfill raw_* fields for existing grants
    # Set raw_title = name, raw_content = description || mission || '', fetched_at = created_at
    op.execute("""
        UPDATE grants 
        SET raw_title = name,
            raw_content = COALESCE(description, mission, ''),
            fetched_at = created_at
        WHERE raw_title IS NULL
    """)
    
    # Create grant_normalizations table (Presentation Layer - editable, auditable)
    op.create_table(
        'grant_normalizations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('grant_id', sa.Integer(), nullable=False),
        sa.Column('canonical_title', sa.String(), nullable=True),
        sa.Column('canonical_summary', sa.Text(), nullable=True),
        sa.Column('timeline_status', sa.String(20), nullable=True),  # 'active', 'closed', 'rolling', 'unknown'
        sa.Column('normalized_by', sa.String(20), server_default='system', nullable=False),
        sa.Column('confidence_level', sa.String(10), nullable=True),  # 'high', 'medium', 'low'
        sa.Column('revision_notes', sa.Text(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_grant_normalizations_id'), 'grant_normalizations', ['id'], unique=False)
    op.create_index(op.f('ix_grant_normalizations_grant_id'), 'grant_normalizations', ['grant_id'], unique=True)
    
    # Create foreign keys
    op.create_foreign_key(
        'fk_grant_normalizations_grant_id',
        'grant_normalizations', 'grants',
        ['grant_id'], ['id'],
        ondelete='CASCADE'
    )
    
    op.create_foreign_key(
        'fk_grant_normalizations_approved_by',
        'grant_normalizations', 'users',
        ['approved_by_user_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Drop foreign keys
    op.drop_constraint('fk_grant_normalizations_approved_by', 'grant_normalizations', type_='foreignkey')
    op.drop_constraint('fk_grant_normalizations_grant_id', 'grant_normalizations', type_='foreignkey')
    
    # Drop indexes
    op.drop_index(op.f('ix_grant_normalizations_grant_id'), table_name='grant_normalizations')
    op.drop_index(op.f('ix_grant_normalizations_id'), table_name='grant_normalizations')
    
    # Drop grant_normalizations table
    op.drop_table('grant_normalizations')
    
    # Remove raw data fields from grants table
    op.drop_column('grants', 'fetched_at')
    op.drop_column('grants', 'raw_content')
    op.drop_column('grants', 'raw_title')
