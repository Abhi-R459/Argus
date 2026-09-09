"""DB-004 & DB-005: Create Employee Directory and Compliance Overview Views

Revision ID: 004_views
Revises: 003_chain_state_seed
Create Date: 2026-07-25 10:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_views'
down_revision: Union[str, None] = '003_chain_state_seed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. v_employee_directory View
    op.execute("""
        CREATE VIEW v_employee_directory AS
        SELECT 
            e.employee_id,
            e.full_name,
            e.email,
            r.title AS role_title,
            d.name AS department_name,
            r.salary_band_min,
            r.salary_band_max,
            e.date_hired,
            e.is_active,
            e.created_at
        FROM employees e
        JOIN roles r ON e.role_id = r.role_id
        JOIN departments d ON r.department_id = d.department_id;
    """)

    # 2. v_compliance_overview View
    op.execute("""
        CREATE VIEW v_compliance_overview AS
        SELECT 
            a.sequence_id,
            a.actor_user_id,
            a.employee_id,
            a.action,
            a.table_name,
            a.row_id,
            a.severity,
            f.flag_id,
            f.flag_reason,
            f.reviewed_by_user_id,
            f.reviewed_at,
            a.created_at
        FROM audit_log a
        LEFT JOIN suspicious_activity_flags f ON a.sequence_id = f.audit_log_sequence_id;
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_compliance_overview;")
    op.execute("DROP VIEW IF EXISTS v_employee_directory;")
