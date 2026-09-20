"""Integration tests for Compliance Auditor Employee Directory Permissions & PII Shielding.

Validates that:
1. Static DDL scripts ensure compliance_auditor is granted SELECT on v_employee_directory
   and NOT on raw employees table (PII shielding).
2. Live database tests verify that compliance_auditor receives permission denied on `employees`
   table while successfully querying `v_employee_directory` and executing `reconstruct_employee_state`.
"""

import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

# Check if live PostgreSQL environment is available
POSTGRES_AVAILABLE = bool(
    os.environ.get("DATABASE_URL")
    or os.environ.get("DATABASE_URL_COMPLIANCE_AUDITOR")
    or os.environ.get("DATABASE_URL_HR_ADMIN")
)
requires_postgres = pytest.mark.skipif(
    not POSTGRES_AVAILABLE,
    reason="PostgreSQL not available — skipping live kernel privilege tests",
)


def get_auditor_db_url():
    url = os.environ.get(
        "DATABASE_URL_COMPLIANCE_AUDITOR",
        "postgresql://compliance_auditor:password@localhost:5433/argus",
    )
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


class TestAuditorDirectoryStaticPermissions:
    """Static assertion that roles and migrations adhere to PII shielding contracts."""

    def test_setup_roles_has_directory_grant_for_auditor(self):
        sql_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "setup_roles.sql")
        assert os.path.exists(sql_path), f"File not found: {sql_path}"
        with open(sql_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "GRANT SELECT ON v_employee_directory TO compliance_auditor;" in content
        assert "GRANT SELECT, INSERT, UPDATE ON employees TO hr_admin;" in content
        # Ensure raw employees table is NOT granted to compliance_auditor
        assert "GRANT SELECT ON employees TO compliance_auditor" not in content

    def test_view_schema_excludes_pii(self):
        views_path = os.path.join(os.path.dirname(__file__), "..", "alembic", "versions", "004_views.py")
        assert os.path.exists(views_path), f"File not found: {views_path}"
        with open(views_path, "r", encoding="utf-8") as f:
            content = f.read()

        # PII fields must NEVER be included in v_employee_directory
        assert "national_id" not in content
        assert "national_id_encrypted" not in content
        assert "contact_info_encrypted" not in content


@requires_postgres
class TestAuditorDirectoryLivePermissions:
    """Live PostgreSQL privilege enforcement tests."""

    def test_raw_employees_table_access_denied_for_auditor(self):
        """compliance_auditor must be forbidden from querying raw employees table directly."""
        engine = create_engine(get_auditor_db_url())
        with engine.connect() as conn:
            with pytest.raises(ProgrammingError) as exc_info:
                conn.execute(text("SELECT * FROM employees LIMIT 1;"))
            assert "permission denied" in str(exc_info.value).lower()
        engine.dispose()

    def test_view_directory_access_permitted_for_auditor(self):
        """compliance_auditor must be allowed to SELECT from v_employee_directory."""
        engine = create_engine(get_auditor_db_url())
        with engine.connect() as conn:
            res = conn.execute(text("SELECT employee_id, full_name, role_title, department_name FROM v_employee_directory LIMIT 5;"))
            rows = res.fetchall()
            assert isinstance(rows, list)
        engine.dispose()

    def test_time_travel_stored_routine_executable_by_auditor(self):
        """compliance_auditor must be allowed to execute reconstruct_employee_state."""
        engine = create_engine(get_auditor_db_url())
        with engine.connect() as conn:
            res = conn.execute(text("SELECT reconstruct_employee_state(1, NOW());"))
            # Routine must run without permission errors
            _ = res.scalar()
        engine.dispose()
