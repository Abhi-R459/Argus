"""DB-015: Finalize GRANT/REVOKE Permissions

Revision ID: 008_finalize_permissions
Revises: 007_trigger_business_rules
Create Date: 2026-07-31

Applies the complete, finalized GRANT/REVOKE permission matrix for the
`hr_admin` and `compliance_auditor` roles.

Key security enforcement (Decision #12):
  REVOKE UPDATE, DELETE ON audit_log FROM hr_admin, compliance_auditor
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008_finalize_permissions'
down_revision: Union[str, None] = '007_trigger_business_rules'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply the finalized permission matrix."""
    bind = op.get_bind()
    roles_exist = bind.execute(sa.text(
        "SELECT COUNT(*) FROM pg_roles "
        "WHERE rolname IN ('hr_admin', 'compliance_auditor')"
    )).scalar_one()
    # Some automated migration environments do not create application roles.
    # Check before issuing GRANTs: swallowing a PostgreSQL permission error
    # leaves the surrounding Alembic transaction aborted.
    if roles_exist != 2:
        return

    statements = [
        # ---------- HR Admin ----------
        "GRANT SELECT ON audit_log TO hr_admin",
        "REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON audit_log FROM hr_admin",
        "GRANT SELECT ON suspicious_activity_flags TO hr_admin",
        "GRANT SELECT ON v_compliance_overview TO hr_admin",

        # ---------- Compliance Auditor ----------
        "REVOKE INSERT, UPDATE, DELETE ON audit_log FROM compliance_auditor",
        "GRANT SELECT ON audit_log TO compliance_auditor",
        "GRANT SELECT ON suspicious_activity_flags TO compliance_auditor",
        "GRANT SELECT ON chain_state TO compliance_auditor",
        "GRANT SELECT ON chain_checkpoints TO compliance_auditor",
        "GRANT SELECT ON backups TO compliance_auditor",
        "GRANT SELECT ON v_compliance_overview TO compliance_auditor",
        "GRANT SELECT ON v_employee_directory TO compliance_auditor",
    ]
    for stmt in statements:
        op.execute(stmt)


def downgrade() -> None:
    """Downgrade is a no-op — permission reverts handled by dropping roles."""
    pass
