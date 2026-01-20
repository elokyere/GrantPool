"""add_email_verification_fields

Revision ID: add_email_verification
Revises: afa9a777c7ea
Create Date: 2026-01-20 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_email_verification'
down_revision: Union[str, None] = 'decision_readiness_001'  # Latest migration (head)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add email verification fields
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('email_verification_token', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('email_verification_expires', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_users_email_verification_token'), 'users', ['email_verification_token'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_email_verification_token'), table_name='users')
    op.drop_column('users', 'email_verification_expires')
    op.drop_column('users', 'email_verification_token')
    op.drop_column('users', 'email_verified')
