"""Add defense-in-depth RLS while retaining the API's existing SQL privileges."""

from alembic import op

revision = "024_runtime_rls"
down_revision = "023_hr_checkpoint_creation"
branch_labels = None
depends_on = None

TABLES = (
    "alembic_version", "departments", "roles", "users", "employees",
    "salary_history", "audit_log", "suspicious_activity_flags", "chain_state",
    "chain_checkpoints", "backups", "security_audit_events", "suspicious_activity_reviews",
)


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
        # Argus is a single-organization API. Clerk authorizes the user in the
        # API; SQL GRANTs authorize each operation and isolate auditor PII.
        # Policies add no SQL privileges. No policy permits Data API roles.
        op.execute(f'''CREATE POLICY argus_runtime_access ON public."{table}"
                       TO hr_admin, compliance_auditor, argus_audit_owner
                       USING (true) WITH CHECK (true)''')


def downgrade():
    raise RuntimeError("Runtime RLS is forward-only security hardening.")
