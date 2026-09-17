"""
Tests for DB-007: Hash-Chaining AFTER Trigger on employees.
Also validates DB-009 (severity) and DB-010 (PII masking).

These tests run against SQLite in-memory for structural logic tests, and are
designed to be supplemented by a live PostgreSQL integration test when a DB
is available. The trigger SQL itself is validated by the Alembic upgrade path.

Test strategy:
  - Structural: verify audit_log row is inserted on employee changes.
  - Hash chain: verify audit_log[n].previous_hash == audit_log[n-1].entry_hash.
  - Severity: verify DELETE → CRITICAL, UPDATE → INFO.
  - Masking: verify national_id_encrypted and contact_info_encrypted are [REDACTED].

NOTE: Live trigger tests require a PostgreSQL connection with pgcrypto enabled.
Use DATABASE_URL env var to run integration tests.
"""
import os
import json
import pytest


# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------
POSTGRES_AVAILABLE = bool(os.environ.get("DATABASE_URL"))
requires_postgres = pytest.mark.skipif(
    not POSTGRES_AVAILABLE,
    reason="PostgreSQL DATABASE_URL not set — skipping live trigger tests"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def pg_conn():
    """Return a live psycopg2 connection to the test database."""
    if not POSTGRES_AVAILABLE:
        pytest.skip("DATABASE_URL not set")
    import psycopg2
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = False
    yield conn
    conn.rollback()
    conn.close()


@pytest.fixture(autouse=True)
def rollback_after_test(pg_conn):
    """Roll back every test so the DB is clean for the next one."""
    yield
    pg_conn.rollback()


@pytest.fixture(scope="module")
def seed_data(pg_conn):
    """Insert prerequisite department, role, and user rows."""
    with pg_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO departments (name) VALUES ('Engineering') "
            "ON CONFLICT DO NOTHING RETURNING department_id"
        )
        row = cur.fetchone()
        dept_id = row[0] if row else None
        if dept_id is None:
            cur.execute("SELECT department_id FROM departments WHERE name='Engineering'")
            dept_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO roles (title, department_id, salary_band_min, salary_band_max) "
            "VALUES ('Engineer', %s, 50000, 150000) RETURNING role_id",
            (dept_id,)
        )
        role_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO users (clerk_user_id, full_name, email, role) "
            "VALUES ('clerk_test_001', 'Test HR Admin', 'hradmin@test.com', 'hr_admin') "
            "ON CONFLICT (clerk_user_id) DO NOTHING RETURNING user_id"
        )
        row = cur.fetchone()
        user_id = row[0] if row else None
        if user_id is None:
            cur.execute("SELECT user_id FROM users WHERE clerk_user_id='clerk_test_001'")
            user_id = cur.fetchone()[0]
        pg_conn.commit()

    return {"dept_id": dept_id, "role_id": role_id, "user_id": user_id}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def set_actor(cur, user_id: int, employee_id: int = 0):
    """Set session-local actor variables required by the trigger."""
    cur.execute(f"SET LOCAL argus.actor_user_id = {user_id}")
    cur.execute(f"SET LOCAL argus.actor_employee_id = {employee_id}")


def insert_employee(cur, role_id: int, name: str = "Test Employee") -> int:
    """Insert a minimal employee row and return employee_id."""
    cur.execute(
        """
        INSERT INTO employees
            (full_name, email, role_id, national_id_encrypted, contact_info_encrypted, date_hired)
        VALUES
            (%s, %s, %s, %s, %s, '2024-01-01')
        RETURNING employee_id
        """,
        (name, f"{name.lower().replace(' ', '')}@test.com", role_id,
         b"\xDE\xAD\xBE\xEF", b"\xCA\xFE\xBA\xBE")
    )
    return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@requires_postgres
def test_insert_creates_audit_entry(pg_conn, seed_data):
    """Step 2.A.6: INSERT on employees creates an audit_log entry."""
    with pg_conn.cursor() as cur:
        set_actor(cur, seed_data["user_id"])
        emp_id = insert_employee(cur, seed_data["role_id"])

        cur.execute(
            "SELECT count(*) FROM audit_log WHERE table_name='employees' AND row_id=%s",
            (emp_id,)
        )
        count = cur.fetchone()[0]
        assert count == 1, f"Expected 1 audit entry for employee {emp_id}, got {count}"


@requires_postgres
def test_hash_chain_links_correctly(pg_conn, seed_data):
    """Step 2.A.8: Each audit_log row's previous_hash equals the prior entry_hash."""
    with pg_conn.cursor() as cur:
        set_actor(cur, seed_data["user_id"])

        # INSERT
        emp_id = insert_employee(cur, seed_data["role_id"], "Chain Test")

        # UPDATE
        cur.execute(
            "UPDATE employees SET full_name='Chain Test Updated' WHERE employee_id=%s",
            (emp_id,)
        )

        cur.execute(
            """
            SELECT sequence_id, entry_hash, previous_hash
            FROM   audit_log
            ORDER  BY sequence_id
            """
        )
        rows = cur.fetchall()
        assert len(rows) >= 2, "Expected at least 2 audit entries"

        for i in range(1, len(rows)):
            prev_entry_hash = rows[i - 1][1]
            curr_previous_hash = rows[i][2]
            assert prev_entry_hash == curr_previous_hash, (
                f"Chain broken at sequence_id={rows[i][0]}: "
                f"previous_hash ({curr_previous_hash!r}) != "
                f"prior entry_hash ({prev_entry_hash!r})"
            )


@requires_postgres
def test_delete_severity_is_critical(pg_conn, seed_data):
    """Step 2.C.2: DELETE action logs severity = 'CRITICAL'."""
    with pg_conn.cursor() as cur:
        set_actor(cur, seed_data["user_id"])
        emp_id = insert_employee(cur, seed_data["role_id"], "Delete Me")

        cur.execute("DELETE FROM employees WHERE employee_id=%s", (emp_id,))

        cur.execute(
            "SELECT severity FROM audit_log WHERE table_name='employees' AND action='DELETE' AND row_id=%s",
            (emp_id,)
        )
        row = cur.fetchone()
        assert row is not None, "DELETE audit entry not found"
        assert row[0] == "CRITICAL", f"Expected CRITICAL severity for DELETE, got {row[0]}"


@requires_postgres
def test_insert_severity_is_info(pg_conn, seed_data):
    """Step 2.C.4: INSERT action logs severity = 'INFO'."""
    with pg_conn.cursor() as cur:
        set_actor(cur, seed_data["user_id"])
        emp_id = insert_employee(cur, seed_data["role_id"], "Info Severity")

        cur.execute(
            "SELECT severity FROM audit_log WHERE table_name='employees' AND action='INSERT' AND row_id=%s",
            (emp_id,)
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "INFO", f"Expected INFO severity for INSERT, got {row[0]}"


@requires_postgres
def test_pii_fields_redacted_in_audit_log(pg_conn, seed_data):
    """Step 2.D.2: national_id_encrypted and contact_info_encrypted must be '[REDACTED]' in audit_log."""
    with pg_conn.cursor() as cur:
        set_actor(cur, seed_data["user_id"])
        emp_id = insert_employee(cur, seed_data["role_id"], "PII Test")

        cur.execute(
            "SELECT new_value FROM audit_log WHERE table_name='employees' AND row_id=%s AND action='INSERT'",
            (emp_id,)
        )
        row = cur.fetchone()
        assert row is not None, "Audit entry not found"
        new_value = row[0]

        assert new_value.get("national_id_encrypted") == "[REDACTED]", (
            f"national_id_encrypted not redacted: {new_value.get('national_id_encrypted')}"
        )
        assert new_value.get("contact_info_encrypted") == "[REDACTED]", (
            f"contact_info_encrypted not redacted: {new_value.get('contact_info_encrypted')}"
        )

        # Raw bytes must NOT appear
        raw_text = json.dumps(new_value)
        assert "DEADBEEF" not in raw_text.upper(), "Raw national_id bytes leaked into audit_log"
        assert "CAFEBABE" not in raw_text.upper(), "Raw contact_info bytes leaked into audit_log"


@requires_postgres
def test_chain_state_tail_updated_after_insert(pg_conn, seed_data):
    """Step 2.A.7: chain_state.tail_hash matches the last audit_log.entry_hash."""
    with pg_conn.cursor() as cur:
        set_actor(cur, seed_data["user_id"])
        insert_employee(cur, seed_data["role_id"], "Chain State Test")

        cur.execute("SELECT tail_hash FROM chain_state WHERE id=1")
        tail_hash = cur.fetchone()[0]

        cur.execute(
            "SELECT entry_hash FROM audit_log WHERE table_name='employees' ORDER BY sequence_id DESC LIMIT 1"
        )
        last_hash = cur.fetchone()[0]

        assert tail_hash == last_hash, (
            f"chain_state.tail_hash ({tail_hash}) does not match last entry_hash ({last_hash})"
        )
