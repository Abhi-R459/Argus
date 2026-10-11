"""Support Supabase's managed Auth RLS with a private fixed boolean function.

The managed tables have no policy for custom roles, and their owner cannot be
changed by the project administrator. Only this fixed, private session-status
function uses the trusted migration principal's existing RLS bypass. Runtime
roles retain no Auth-table access or RLS bypass; no Auth policy is changed.
"""
from alembic import op

revision = "029_managed_auth_rls"
down_revision = "028_bound_auth_session_check"
branch_labels = None
depends_on = None

SQL = """
DO $migration$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_class WHERE oid IN (to_regclass('auth.sessions'), to_regclass('auth.users'))
               AND relrowsecurity) THEN
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = current_user AND (rolsuper OR rolbypassrls)) THEN
            RAISE EXCEPTION 'Managed Auth session check requires the trusted RLS-bypass migration principal';
        END IF;
        IF current_setting('server_version_num')::integer >= 160000 THEN
            EXECUTE 'GRANT argus_audit_owner TO CURRENT_USER WITH ADMIN FALSE, INHERIT TRUE, SET TRUE';
            EXECUTE 'GRANT argus_auth_reader TO CURRENT_USER WITH ADMIN FALSE, INHERIT TRUE, SET TRUE';
        ELSE
            EXECUTE 'GRANT argus_audit_owner TO CURRENT_USER';
            EXECUTE 'GRANT argus_auth_reader TO CURRENT_USER';
        END IF;
        ALTER FUNCTION argus_private.supabase_session_active(uuid, uuid) OWNER TO CURRENT_USER;
        REVOKE argus_auth_reader FROM CURRENT_USER;
        REVOKE argus_audit_owner FROM CURRENT_USER;
    END IF;
END;
$migration$;
REVOKE ALL ON FUNCTION argus_private.supabase_session_active(uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION argus_private.supabase_session_active(uuid, uuid) TO hr_admin;
"""


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute(SQL)


def downgrade():
    raise RuntimeError("Session revocation protection is forward-only security hardening.")
