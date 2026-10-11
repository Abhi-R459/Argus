"""Give the API a boolean session check, never access to Auth credentials."""
from alembic import op

revision = "027_supabase_sessions"
down_revision = "026_checkpoint_boundary_lock"
branch_labels = None
depends_on = None

SQL = """
DO $grant$
BEGIN
    IF current_setting('server_version_num')::integer >= 160000 THEN
        EXECUTE 'GRANT argus_audit_owner TO CURRENT_USER WITH ADMIN FALSE, INHERIT TRUE, SET TRUE';
    ELSE
        EXECUTE 'GRANT argus_audit_owner TO CURRENT_USER';
    END IF;
END;
$grant$;
CREATE ROLE argus_auth_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
GRANT argus_auth_reader TO CURRENT_USER;
GRANT USAGE, CREATE ON SCHEMA argus_private TO argus_auth_reader;
DO $block$
BEGIN
    IF to_regclass('auth.sessions') IS NOT NULL THEN
        GRANT USAGE ON SCHEMA auth TO argus_auth_reader;
        GRANT SELECT (id, user_id, not_after) ON auth.sessions TO argus_auth_reader;
        GRANT SELECT (id, banned_until, deleted_at) ON auth.users TO argus_auth_reader;
    END IF;
END;
$block$;
CREATE FUNCTION argus_private.supabase_session_active(p_user_id uuid, p_session_id uuid)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $function$
BEGIN
    IF session_user::text <> 'hr_admin' THEN
        RAISE EXCEPTION 'Session validation requires HR runtime role' USING ERRCODE = '28000';
    END IF;
    IF to_regclass('auth.sessions') IS NULL THEN
        RETURN false;
    END IF;
    RETURN EXISTS (SELECT 1 FROM auth.sessions WHERE id = p_session_id AND user_id = p_user_id
                   AND (not_after IS NULL OR not_after > clock_timestamp()))
       AND EXISTS (SELECT 1 FROM auth.users WHERE id = p_user_id AND deleted_at IS NULL
                   AND (banned_until IS NULL OR banned_until <= clock_timestamp()));
END;
$function$;
ALTER FUNCTION argus_private.supabase_session_active(uuid, uuid) OWNER TO argus_auth_reader;
REVOKE CREATE ON SCHEMA argus_private FROM argus_auth_reader;
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
