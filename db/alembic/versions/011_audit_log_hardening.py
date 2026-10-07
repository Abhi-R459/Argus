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
        op.execute(sa.text("REVOKE ALL PRIVILEGES ON audit_log FROM PUBLIC"))
        roles = set(bind.execute(sa.text(
            "SELECT rolname FROM pg_roles "
            "WHERE rolname IN ('hr_admin', 'compliance_auditor')"
        )).scalars().all())
        if "hr_admin" in roles:
            op.execute(sa.text("REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON audit_log FROM hr_admin"))
            op.execute(sa.text("GRANT SELECT ON audit_log TO hr_admin"))
        if "compliance_auditor" in roles:
            op.execute(sa.text("REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON audit_log FROM compliance_auditor"))
            op.execute(sa.text("GRANT SELECT ON audit_log TO compliance_auditor"))
        op.execute(sa.text("ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS fk_audit_log_employee_id"))


def downgrade() -> None:
    """Downgrade retains SELECT permissions."""
    pass
