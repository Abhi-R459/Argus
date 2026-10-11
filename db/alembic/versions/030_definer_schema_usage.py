"""Let existing audit functions resolve their already-granted public tables."""
from alembic import op

revision = "030_definer_schema_usage"
down_revision = "029_managed_auth_rls"
branch_labels = None
depends_on = None

SQL = "GRANT USAGE ON SCHEMA public TO argus_audit_owner;"


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute(SQL)


def downgrade():
    raise RuntimeError("Audit function access is forward-only security hardening.")
