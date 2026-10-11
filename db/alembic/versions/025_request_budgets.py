"""Persist API request budgets across workers and restarts."""

from alembic import op

revision = "025_request_budgets"
down_revision = "024_runtime_rls"
branch_labels = None
depends_on = None

SQL = """
GRANT argus_audit_owner TO CURRENT_USER;
GRANT SELECT (user_id, role, is_active) ON public.users TO argus_audit_owner;
CREATE TABLE argus_private.request_budgets (
    actor_user_id integer NOT NULL REFERENCES public.users(user_id) ON DELETE CASCADE,
    scope text NOT NULL,
    window_id bigint NOT NULL,
    request_count integer NOT NULL,
    PRIMARY KEY (actor_user_id, scope)
);
ALTER TABLE argus_private.request_budgets OWNER TO argus_audit_owner;
REVOKE ALL ON argus_private.request_budgets FROM PUBLIC;
ALTER TABLE argus_private.request_budgets ENABLE ROW LEVEL SECURITY;
CREATE FUNCTION argus_private.consume_request_budget(p_actor_user_id integer, p_scope text, p_limit integer)
RETURNS TABLE (allowed boolean, retry_after integer)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, argus_private, pg_temp
AS $function$
DECLARE
    v_seconds bigint := floor(extract(epoch FROM clock_timestamp()))::bigint;
    v_window bigint := v_seconds / 60;
    v_count integer;
BEGIN
    IF session_user::text NOT IN ('hr_admin', 'compliance_auditor')
       OR p_scope NOT IN ('api', 'blind_index') OR p_limit < 1 OR p_limit > 300
       OR NOT EXISTS (SELECT 1 FROM public.users WHERE user_id = p_actor_user_id
                      AND is_active AND role = session_user::text) THEN
        RAISE EXCEPTION 'Invalid request budget context' USING ERRCODE = '28000';
    END IF;
    INSERT INTO argus_private.request_budgets AS budget
        (actor_user_id, scope, window_id, request_count)
    VALUES (p_actor_user_id, p_scope, v_window, 1)
    ON CONFLICT (actor_user_id, scope) DO UPDATE SET
        window_id = v_window,
        request_count = CASE WHEN budget.window_id = v_window
                             THEN least(budget.request_count + 1, p_limit + 1) ELSE 1 END
    RETURNING request_count INTO v_count;
    RETURN QUERY SELECT v_count <= p_limit, (60 - v_seconds % 60)::integer;
END;
$function$;
ALTER FUNCTION argus_private.consume_request_budget(integer, text, integer) OWNER TO argus_audit_owner;
REVOKE ALL ON FUNCTION argus_private.consume_request_budget(integer, text, integer) FROM PUBLIC;
GRANT USAGE ON SCHEMA argus_private TO hr_admin, compliance_auditor;
GRANT EXECUTE ON FUNCTION argus_private.consume_request_budget(integer, text, integer)
    TO hr_admin, compliance_auditor;
REVOKE argus_audit_owner FROM CURRENT_USER;
"""


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute(SQL)


def downgrade():
    raise RuntimeError("Shared request budgets are forward-only security hardening.")
