"""Allow checkpoint boundary locking without granting HR audit-state writes."""

from alembic import op

revision = '026_checkpoint_boundary_lock'
down_revision = '025_request_budgets'
branch_labels = None
depends_on = None

SQL = """
GRANT argus_audit_owner TO CURRENT_USER;
GRANT SELECT (id), UPDATE (id) ON public.chain_state TO argus_audit_owner;
GRANT SELECT ON public.chain_checkpoints TO hr_admin;
GRANT SELECT (event_id, created_at) ON public.security_audit_events TO hr_admin;
CREATE FUNCTION argus_private.lock_checkpoint_boundary() RETURNS void
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $function$
BEGIN
    IF session_user::text <> 'hr_admin' THEN
        RAISE EXCEPTION 'Checkpoint locking requires HR runtime role' USING ERRCODE = '28000';
    END IF;
    PERFORM id FROM public.chain_state WHERE id=1 FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Audit chain state is missing';
    END IF;
END;
$function$;
ALTER FUNCTION argus_private.lock_checkpoint_boundary() OWNER TO argus_audit_owner;
REVOKE ALL ON FUNCTION argus_private.lock_checkpoint_boundary() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION argus_private.lock_checkpoint_boundary() TO hr_admin;
REVOKE argus_audit_owner FROM CURRENT_USER;
"""


def upgrade():
    if op.get_bind().dialect.name == 'postgresql':
        op.execute(SQL)


def downgrade():
    raise RuntimeError('Checkpoint boundary permissions are forward-only security hardening.')
