"""Unit and integration tests for HARDEN-002: Direct audit_log INSERT Privilege Isolation.

Validates that:
1. Role permission definitions explicitly revoke INSERT, UPDATE, DELETE, TRUNCATE
   from hr_admin, compliance_auditor, and PUBLIC.
2. Trigger functions run as SECURITY DEFINER owned by postgres.
3. Direct INSERT into audit_log as hr_admin is rejected at the PostgreSQL kernel level.
4. Normal employee mutations by hr_admin succeed and append to audit_log via
   the elevated SECURITY DEFINER trigger context.
"""

import os
import pytest
from sqlalchemy import create_engine, text

# Check if live PostgreSQL environment is available
POSTGRES_AVAILABLE = bool(os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URL_HR_ADMIN"))
requires_postgres = pytest.mark.skipif(
    not POSTGRES_AVAILABLE,
    reason="PostgreSQL not available — skipping live kernel privilege tests"
)


class TestAuditLogPrivilegeStaticVerification:
    """Static verification of DDL scripts and Alembic migrations."""

    def test_setup_roles_explicit_revocations(self):
        """Verify that setup_roles.sql explicitly revokes all write and truncate privileges."""
        sql_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "setup_roles.sql")
        assert os.path.exists(sql_path), f"File not found: {sql_path}"
        with open(sql_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check explicit revocation statements
        assert "REVOKE ALL PRIVILEGES ON audit_log FROM PUBLIC;" in content
        assert "REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON audit_log FROM hr_admin, compliance_auditor, PUBLIC;" in content
        assert "REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON audit_log FROM compliance_auditor;" in content

    def test_triggers_are_security_definer(self):
        """Verify that audit trigger functions are defined with SECURITY DEFINER."""
        emp_trigger_path = os.path.join(os.path.dirname(__file__), "..", "triggers", "audit_employees.sql")
        salary_trigger_path = os.path.join(os.path.dirname(__file__), "..", "triggers", "audit_salary_history.sql")

        assert os.path.exists(emp_trigger_path)
        assert os.path.exists(salary_trigger_path)

        with open(emp_trigger_path, "r", encoding="utf-8") as f:
            emp_sql = f.read()
        with open(salary_trigger_path, "r", encoding="utf-8") as f:
            salary_sql = f.read()

        assert "SECURITY DEFINER" in emp_sql, "trg_employees_hash_chain_fn must be SECURITY DEFINER"
        assert "SECURITY DEFINER" in salary_sql, "trg_salary_history_hash_chain_fn must be SECURITY DEFINER"

    def test_migration_011_structure(self):
        """Verify migration 011 exists and targets 010_blind_indexing."""
        import importlib
        mig11 = importlib.import_module("db.alembic.versions.011_audit_log_hardening")
        assert mig11.revision == "011_audit_log_hardening"
        assert mig11.down_revision == "010_blind_indexing"


@requires_postgres
class TestAuditLogLivePrivilegeIsolation:
    """Live PostgreSQL privilege tests testing kernel-level enforcement."""

    @pytest.fixture
    def pg_conn(self):
        import psycopg2
        db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/argus")
        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        yield conn
        conn.rollback()
        conn.close()

    def test_direct_audit_log_insert_rejected_for_hr_admin(self, pg_conn):
        """Direct INSERT INTO audit_log as hr_admin must raise InsufficientPrivilege."""
        import psycopg2.errors
        with pg_conn.cursor() as cur:
            # Switch session role to hr_admin
            cur.execute("SET ROLE hr_admin;")
            with pytest.raises(psycopg2.errors.InsufficientPrivilege) as exc_info:
                cur.execute("""
                    INSERT INTO audit_log (
                        table_name, row_id, action, entry_hash, previous_hash
                    ) VALUES (
                        'employees', 99999, 'INSERT',
                        '0000000000000000000000000000000000000000000000000000000000000000',
                        '0000000000000000000000000000000000000000000000000000000000000000'
                    );
                """)
            assert "permission denied for table audit_log" in str(exc_info.value)
            pg_conn.rollback()

    def test_direct_audit_log_update_delete_rejected_for_hr_admin(self, pg_conn):
        """Direct UPDATE / DELETE on audit_log as hr_admin must raise InsufficientPrivilege."""
        import psycopg2.errors
        with pg_conn.cursor() as cur:
            cur.execute("SET ROLE hr_admin;")
            with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                cur.execute("UPDATE audit_log SET action = 'FORGED' WHERE sequence_id = 1;")
            pg_conn.rollback()

            cur.execute("SET ROLE hr_admin;")
            with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                cur.execute("DELETE FROM audit_log WHERE sequence_id = 1;")
            pg_conn.rollback()

    def test_normal_employee_mutation_succeeds_via_security_definer(self, pg_conn):
        """Normal employee INSERT by hr_admin succeeds and appends to audit_log via trigger."""
        with pg_conn.cursor() as cur:
            # Query count before
            cur.execute("SELECT count(*) FROM audit_log;")
            count_before = cur.fetchone()[0]

            # Find a valid role_id
            cur.execute("SELECT role_id FROM roles LIMIT 1;")
            role_row = cur.fetchone()
            role_id = role_row[0] if role_row else 1

            # Set actor session variables
            cur.execute("SET LOCAL argus.actor_user_id = 1;")
            cur.execute("SET LOCAL argus.actor_employee_id = 0;")

            # Execute employee write as hr_admin
            cur.execute("SET ROLE hr_admin;")
            cur.execute("""
                INSERT INTO employees (
                    full_name, email, role_id, national_id_encrypted, contact_info_encrypted, date_hired, is_active
                ) VALUES (
                    'Harden Isolation Test', 'harden.isolation@argustech.internal', %s, %s, %s, '2026-01-01', true
                ) RETURNING employee_id;
            """, (role_id, b"\\xDE\\xAD\\xBE\\xEF", b"\\xCA\\xFE\\xBA\\xBE"))
            emp_id = cur.fetchone()[0]
            assert emp_id is not None

            # Verify audit log was appended
            cur.execute("RESET ROLE;")
            cur.execute("SELECT count(*) FROM audit_log;")
            count_after = cur.fetchone()[0]
            assert count_after == count_before + 1

            # Verify the entry details
            cur.execute("""
                SELECT action, table_name, row_id, entry_hash
                FROM audit_log
                ORDER BY sequence_id DESC
                LIMIT 1;
            """)
            action, table_name, row_id, entry_hash = cur.fetchone()
            assert action == "INSERT"
            assert table_name == "employees"
            assert row_id == emp_id
            assert len(entry_hash) == 64
            pg_conn.rollback()
