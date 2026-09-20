"""
Tests for DB-008: Hash-Chaining AFTER Trigger on salary_history.
Also validates that the chain links correctly ACROSS both employees and salary_history.

Requires a live PostgreSQL connection with pgcrypto and all migrations applied.
Set DATABASE_URL env var to run.
"""
import os
import pytest

POSTGRES_AVAILABLE = bool(os.environ.get("DATABASE_URL"))
requires_postgres = pytest.mark.skipif(
    not POSTGRES_AVAILABLE,
    reason="PostgreSQL DATABASE_URL not set — skipping live trigger tests"
)


@pytest.fixture(scope="module")
def pg_conn():
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
    yield
    pg_conn.rollback()


@pytest.fixture(scope="module")
def test_employee(pg_conn):
    """Insert a department, role, user, and employee for salary tests."""
    with pg_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO departments (name) VALUES ('Finance') "
            "ON CONFLICT (name) DO NOTHING RETURNING department_id"
        )
        row = cur.fetchone()
        if row:
            dept_id = row[0]
        else:
            cur.execute("SELECT department_id FROM departments WHERE name='Finance'")
            dept_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO roles (title, department_id, salary_band_min, salary_band_max) "
            "VALUES ('Accountant', %s, 40000, 120000) RETURNING role_id",
            (dept_id,)
        )
        role_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO users (clerk_user_id, full_name, email, role) "
            "VALUES ('clerk_sal_test', 'Salary HR', 'salaryhr@test.com', 'hr_admin') "
            "ON CONFLICT (clerk_user_id) DO NOTHING RETURNING user_id"
        )
        row = cur.fetchone()
        user_id = row[0] if row else None
        if user_id is None:
            cur.execute("SELECT user_id FROM users WHERE clerk_user_id='clerk_sal_test'")
            user_id = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO employees
                (full_name, email, role_id, national_id_encrypted, contact_info_encrypted, date_hired)
            VALUES ('Bob Jones', 'bob@test.com', %s, %s, %s, '2024-06-01')
            ON CONFLICT (email) DO NOTHING
            RETURNING employee_id
            """,
            (role_id, b"\x01\x02\x03", b"\x04\x05\x06")
        )
        row = cur.fetchone()
        emp_id = row[0] if row else None
        if emp_id is None:
            cur.execute("SELECT employee_id FROM employees WHERE email='bob@test.com'")
            emp_id = cur.fetchone()[0]
        pg_conn.commit()

    return {"emp_id": emp_id, "user_id": user_id, "role_id": role_id}


def set_actor(cur, user_id, employee_id=0):
    cur.execute(f"SET LOCAL argus.actor_user_id = {user_id}")
    cur.execute(f"SET LOCAL argus.actor_employee_id = {employee_id}")


@requires_postgres
def test_salary_insert_creates_audit_entry(pg_conn, test_employee):
    """Step 2.B.2: Salary INSERT produces an audit_log entry."""
    with pg_conn.cursor() as cur:
        set_actor(cur, test_employee["user_id"])

        cur.execute(
            "INSERT INTO salary_history (employee_id, amount, effective_date) "
            "VALUES (%s, 80000, '2024-07-01') RETURNING salary_history_id",
            (test_employee["emp_id"],)
        )
        sal_id = cur.fetchone()[0]

        cur.execute(
            "SELECT count(*) FROM audit_log WHERE table_name='salary_history' AND row_id=%s",
            (sal_id,)
        )
        assert cur.fetchone()[0] == 1


@requires_postgres
def test_salary_severity_is_warning(pg_conn, test_employee):
    """Step 2.C.3: Salary INSERT logs severity = 'WARNING'."""
    with pg_conn.cursor() as cur:
        set_actor(cur, test_employee["user_id"])

        cur.execute(
            "INSERT INTO salary_history (employee_id, amount, effective_date) "
            "VALUES (%s, 85000, '2024-08-01') RETURNING salary_history_id",
            (test_employee["emp_id"],)
        )
        sal_id = cur.fetchone()[0]

        cur.execute(
            "SELECT severity FROM audit_log WHERE table_name='salary_history' AND row_id=%s",
            (sal_id,)
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "WARNING", f"Expected WARNING for salary, got {row[0]}"


@requires_postgres
def test_cross_table_chain_is_unbroken(pg_conn, test_employee):
    """Step 2.B.3: Hash chain is unbroken across both employees and salary_history tables."""
    with pg_conn.cursor() as cur:
        set_actor(cur, test_employee["user_id"])

        # Employee update (INFO)
        cur.execute(
            "UPDATE employees SET full_name='Bob Jones Updated' WHERE employee_id=%s",
            (test_employee["emp_id"],)
        )

        # Salary insert (WARNING)
        cur.execute(
            "INSERT INTO salary_history (employee_id, amount, effective_date) "
            "VALUES (%s, 90000, '2024-09-01')",
            (test_employee["emp_id"],)
        )

        cur.execute(
            "SELECT sequence_id, entry_hash, previous_hash FROM audit_log ORDER BY sequence_id"
        )
        rows = cur.fetchall()

        for i in range(1, len(rows)):
            prev_hash = rows[i - 1][1]
            curr_prev = rows[i][2]
            assert prev_hash == curr_prev, (
                f"Cross-table chain break at sequence_id={rows[i][0]}: "
                f"expected previous_hash={prev_hash!r}, got {curr_prev!r}"
            )
