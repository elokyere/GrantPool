"""add_rls_policies

Revision ID: afa9a777c7ea
Revises: 1dbfb3c7cf34
Create Date: 2026-01-05 19:28:30.246156

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'afa9a777c7ea'
down_revision: Union[str, None] = '1dbfb3c7cf34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Enable Row Level Security (RLS) on user-owned tables.
    
    Note: This provides defense-in-depth. The application layer already
    enforces user isolation, but RLS adds an additional security layer
    at the database level.
    
    Policies use a function that checks if the current session variable
    'app.user_id' matches the user_id column. The application should
    set this variable when creating database sessions.
    """
    # Enable RLS on user-owned tables
    op.execute("ALTER TABLE projects ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE evaluations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE payments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE assessment_purchases ENABLE ROW LEVEL SECURITY")
    
    # Create function to check user context
    # This function will be used by RLS policies
    op.execute("""
        CREATE OR REPLACE FUNCTION check_user_context(table_user_id INTEGER)
        RETURNS BOOLEAN AS $$
        BEGIN
            -- If app.user_id is not set, deny access (application must set it)
            IF current_setting('app.user_id', true) IS NULL THEN
                RETURN FALSE;
            END IF;
            
            -- Check if the table's user_id matches the session user_id
            RETURN table_user_id = current_setting('app.user_id', true)::INTEGER;
        EXCEPTION
            WHEN OTHERS THEN
                -- If any error occurs, deny access
                RETURN FALSE;
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
    """)
    
    # Create RLS policies for each table
    # Projects policy
    op.execute("""
        CREATE POLICY projects_user_isolation ON projects
            FOR ALL
            USING (check_user_context(user_id));
    """)
    
    # Evaluations policy
    op.execute("""
        CREATE POLICY evaluations_user_isolation ON evaluations
            FOR ALL
            USING (check_user_context(user_id));
    """)
    
    # Payments policy
    op.execute("""
        CREATE POLICY payments_user_isolation ON payments
            FOR ALL
            USING (check_user_context(user_id));
    """)
    
    # Assessment purchases policy
    op.execute("""
        CREATE POLICY assessment_purchases_user_isolation ON assessment_purchases
            FOR ALL
            USING (check_user_context(user_id));
    """)
    
    # Note: Grants table is shared (all users can read), so no RLS needed
    # Users table is managed by application, RLS not needed


def downgrade() -> None:
    """Disable RLS and remove policies."""
    # Drop policies
    op.execute("DROP POLICY IF EXISTS projects_user_isolation ON projects")
    op.execute("DROP POLICY IF EXISTS evaluations_user_isolation ON evaluations")
    op.execute("DROP POLICY IF EXISTS payments_user_isolation ON payments")
    op.execute("DROP POLICY IF EXISTS assessment_purchases_user_isolation ON assessment_purchases")
    
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS check_user_context(INTEGER)")
    
    # Disable RLS
    op.execute("ALTER TABLE projects DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE evaluations DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE payments DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE assessment_purchases DISABLE ROW LEVEL SECURITY")
