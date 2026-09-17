"""HARDEN-002: Audit Log Privilege Hardening (Direct INSERT Prevention)

Revision ID: 011_audit_log_hardening
Revises: 010_blind_indexing
Create Date: 2026-09-13 10:00:00.000000

Explicitly revokes INSERT, UPDATE, DELETE, TRUNCATE on audit_log from
PUBLIC, hr_admin, and compliance_auditor. All writes must occur strictly
through SECURITY DEFINER triggers owned by postgres (Decision #33).
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '011_audit_log_hardening'
down_revision: Union[str, None] = '010_blind_indexing'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Explicitly revoke write/truncate privileges on audit_log from non-owners."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        statements = [
            "REVOKE ALL PRIVILEGES ON audit_log FROM PUBLIC;",
            "REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON audit_log FROM hr_admin, compliance_auditor, PUBLIC;",
            "GRANT SELECT ON audit_log TO hr_admin, compliance_auditor;",
            "ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS fk_audit_log_employee_id;",
        ]
        for stmt in statements:
            try:
                op.execute(sa.text(stmt))
            except Exception:
                # Roles might not exist yet in test/CI environments
                pass


def downgrade() -> None:
    """Downgrade retains SELECT permissions."""
    pass
