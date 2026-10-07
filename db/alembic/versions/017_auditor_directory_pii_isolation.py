"""PROD-HARDEN: Keep employee PII out of the auditor's direct DB view.

Revision ID: 017_auditor_dir_pii_isolation
Revises: 016_secure_trigger_search_path
"""

from typing import Sequence, Union

from alembic import op


revision: str = "017_auditor_dir_pii_isolation"
down_revision: Union[str, None] = "016_secure_trigger_search_path"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE VIEW public.v_compliance_employee_directory AS
        SELECT
            e.employee_id,
            ('Employee #' || e.employee_id::TEXT)::VARCHAR(255) AS full_name,
            'Restricted'::VARCHAR(255) AS email,
            r.title AS role_title,
            d.name AS department_name,
            r.salary_band_min,
            r.salary_band_max,
            e.date_hired,
            e.is_active,
            e.created_at
        FROM public.employees e
        JOIN public.roles r ON e.role_id = r.role_id
        JOIN public.departments d ON r.department_id = d.department_id;
    """)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'compliance_auditor') THEN
                REVOKE SELECT ON public.v_employee_directory FROM compliance_auditor;
                GRANT SELECT ON public.v_compliance_employee_directory TO compliance_auditor;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'compliance_auditor') THEN
                REVOKE SELECT ON public.v_compliance_employee_directory FROM compliance_auditor;
                GRANT SELECT ON public.v_employee_directory TO compliance_auditor;
            END IF;
        END $$;
    """)
    op.execute("DROP VIEW public.v_compliance_employee_directory")
