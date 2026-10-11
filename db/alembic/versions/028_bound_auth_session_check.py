"""Bind Auth table references without granting access to the Auth namespace.

Supabase's managed Auth schema does not let the project administrator grant
schema USAGE. A SQL-standard body resolves table references at creation time,
while execution still checks the non-login owner's minimal column privileges.
"""
from alembic import op

revision = "028_bound_auth_session_check"
down_revision = "027_supabase_sessions"
branch_labels = None
depends_on = None

SQL = """
DO $grant$
BEGIN
    IF current_setting('server_version_num')::integer >= 160000 THEN
        EXECUTE 'GRANT argus_audit_owner TO CURRENT_USER WITH ADMIN FALSE, INHERIT TRUE, SET TRUE';
        EXECUTE 'GRANT argus_auth_reader TO CURRENT_USER WITH ADMIN FALSE, INHERIT TRUE, SET TRUE';
    ELSE
        EXECUTE 'GRANT argus_audit_owner TO CURRENT_USER';
        EXECUTE 'GRANT argus_auth_reader TO CURRENT_USER';
    END IF;
END;
$grant$;
DO $migration$
BEGIN
    IF to_regclass('auth.sessions') IS NOT NULL THEN
        EXECUTE $definition$
            CREATE OR REPLACE FUNCTION argus_private.supabase_session_active(p_user_id uuid, p_session_id uuid)
            RETURNS boolean LANGUAGE sql SECURITY DEFINER
            SET search_path = pg_catalog, pg_temp
            BEGIN ATOMIC
                SELECT session_user::text = 'hr_admin'
                   AND EXISTS (SELECT 1 FROM auth.sessions WHERE id = p_session_id AND user_id = p_user_id
                               AND (not_after IS NULL OR not_after > clock_timestamp()))
                   AND EXISTS (SELECT 1 FROM auth.users WHERE id = p_user_id AND deleted_at IS NULL
                               AND (banned_until IS NULL OR banned_until <= clock_timestamp()));
            END;
        $definition$;
    ELSE
        EXECUTE $definition$
            CREATE OR REPLACE FUNCTION argus_private.supabase_session_active(p_user_id uuid, p_session_id uuid)
            RETURNS boolean LANGUAGE sql SECURITY DEFINER
            SET search_path = pg_catalog, pg_temp
            BEGIN ATOMIC
                SELECT false;
            END;
        $definition$;
    END IF;
END;
$migration$;
ALTER FUNCTION argus_private.supabase_session_active(uuid, uuid) OWNER TO argus_auth_reader;
REVOKE ALL ON FUNCTION argus_private.supabase_session_active(uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION argus_private.supabase_session_active(uuid, uuid) TO hr_admin;
REVOKE argus_auth_reader FROM CURRENT_USER;
REVOKE argus_audit_owner FROM CURRENT_USER;
"""


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute(SQL)


def downgrade():
    raise RuntimeError("Session revocation protection is forward-only security hardening.")
