"""Initial migration

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('is_superuser', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # Create projects table
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('stage', sa.String(), nullable=False),
        sa.Column('funding_need', sa.String(), nullable=False),
        sa.Column('urgency', sa.String(), nullable=False),
        sa.Column('founder_type', sa.String(), nullable=True),
        sa.Column('timeline_constraints', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_projects_id'), 'projects', ['id'], unique=False)

    # Create grants table
    op.create_table(
        'grants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('mission', sa.Text(), nullable=True),
        sa.Column('deadline', sa.String(), nullable=True),
        sa.Column('decision_date', sa.String(), nullable=True),
        sa.Column('award_amount', sa.String(), nullable=True),
        sa.Column('award_structure', sa.Text(), nullable=True),
        sa.Column('eligibility', sa.Text(), nullable=True),
        sa.Column('preferred_applicants', sa.Text(), nullable=True),
        sa.Column('application_requirements', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('reporting_requirements', sa.Text(), nullable=True),
        sa.Column('restrictions', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('source_url', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_grants_id'), 'grants', ['id'], unique=False)
    op.create_index(op.f('ix_grants_name'), 'grants', ['name'], unique=False)

    # Create evaluations table
    op.create_table(
        'evaluations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('grant_id', sa.Integer(), nullable=False),
        sa.Column('timeline_viability', sa.Integer(), nullable=False),
        sa.Column('mission_alignment', sa.Integer(), nullable=False),
        sa.Column('founder_fit', sa.Integer(), nullable=False),
        sa.Column('application_burden', sa.Integer(), nullable=False),
        sa.Column('award_structure', sa.Integer(), nullable=False),
        sa.Column('composite_score', sa.Integer(), nullable=False),
        sa.Column('recommendation', sa.String(), nullable=False),
        sa.Column('reasoning', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('key_insights', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('red_flags', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('confidence_notes', sa.Text(), nullable=True),
        sa.Column('evaluator_type', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['grant_id'], ['grants.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_evaluations_id'), 'evaluations', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_evaluations_id'), table_name='evaluations')
    op.drop_table('evaluations')
    op.drop_index(op.f('ix_grants_name'), table_name='grants')
    op.drop_index(op.f('ix_grants_id'), table_name='grants')
    op.drop_table('grants')
    op.drop_index(op.f('ix_projects_id'), table_name='projects')
    op.drop_table('projects')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')

