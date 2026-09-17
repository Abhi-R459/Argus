"""
Tests for DB-012, DB-013, DB-014: Business Rule BEFORE Triggers.

DB-012: Salary Decrease >30% — blocks salary drops of >30% from current salary.
DB-013: National ID Immutability — blocks any UPDATE to national_id_encrypted.
DB-014: Self-Salary Modification Block — blocks employee from modifying own salary
        (enforced via argus.actor_employee_id session variable).

Requires live PostgreSQL. Set DATABASE_URL to run.
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
def business_test_data(pg_conn):
    """Seed minimal rows for business rule tests."""
    with pg_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO departments (name) VALUES ('Legal') "
            "ON CONFLICT (name) DO NOTHING RETURNING department_id"
        )
        row = cur.fetchone()
        dept_id = row[0] if row else None
        if dept_id is None:
            cur.execute("SELECT department_id FROM departments WHERE name='Legal'")
            dept_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO roles (title, department_id, salary_band_min, salary_band_max) "
            "VALUES ('Legal Analyst', %s, 60000, 130000) RETURNING role_id",
            (dept_id,)
        )
        role_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO users (clerk_user_id, full_name, email, role) "
            "VALUES ('clerk_biz_001', 'Biz HR', 'bizhr@test.com', 'hr_admin') "
            "ON CONFLICT (clerk_user_id) DO NOTHING RETURNING user_id"
        )
        row = cur.fetchone()
        user_id = row[0] if row else None
        if user_id is None:
            cur.execute("SELECT user_id FROM users WHERE clerk_user_id='clerk_biz_001'")
            user_id = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO employees
                (full_name, email, role_id, national_id_encrypted, contact_info_encrypted, date_hired)
            VALUES ('Carol White', 'carol@test.com', %s, %s, %s, '2023-03-15')
            ON CONFLICT (email) DO NOTHING
            RETURNING employee_id
            """,
            (role_id, b"\xAA\xBB\xCC", b"\xDD\xEE\xFF")
        )
        row = cur.fetchone()
        emp_id = row[0] if row else None
        if emp_id is None:
            cur.execute("SELECT employee_id FROM employees WHERE email='carol@test.com'")
            emp_id = cur.fetchone()[0]

        # Give Carol an initial salary of 100,000
        cur.execute(
            "SET LOCAL argus.actor_user_id = %s", (user_id,)
        )
        cur.execute(
            "INSERT INTO salary_history (employee_id, amount, effective_date) "
            "VALUES (%s, 100000, '2023-04-01') "
            "ON CONFLICT (employee_id, effective_date) DO NOTHING",
            (emp_id,)
        )
        pg_conn.commit()

    return {"emp_id": emp_id, "user_id": user_id, "role_id": role_id}


def set_actor(cur, user_id, employee_id=0):
    cur.execute(f"SET LOCAL argus.actor_user_id = {user_id}")
    cur.execute(f"SET LOCAL argus.actor_employee_id = {employee_id}")


# ---------------------------------------------------------------------------
# DB-012: Salary Decrease >30%
# ---------------------------------------------------------------------------
@requires_postgres
def test_salary_decrease_over_30_percent_blocked(pg_conn, business_test_data):
    """Step 2.F.1: A salary drop of 40% must raise 'salary_decrease_exceeded'."""
    import psycopg2

    with pg_conn.cursor() as cur:
        set_actor(cur, business_test_data["user_id"])
        # 100,000 → 60,000 = 40% decrease → MUST be blocked
        with pytest.raises((psycopg2.errors.RaiseException, psycopg2.Error)) as exc_info:
            cur.execute(
                "INSERT INTO salary_history (employee_id, amount, effective_date) "
                "VALUES (%s, 60000, '2024-01-01')",
                (business_test_data["emp_id"],)
            )
        assert "salary_decrease_exceeded" in str(exc_info.value)


@requires_postgres
def test_salary_decrease_under_30_percent_allowed(pg_conn, business_test_data):
    """Step 2.F.2: A salary drop of 29% must pass without error."""
    with pg_conn.cursor() as cur:
        set_actor(cur, business_test_data["user_id"])
        # 100,000 → 71,000 = 29% decrease → MUST pass
        cur.execute(
            "INSERT INTO salary_history (employee_id, amount, effective_date) "
            "VALUES (%s, 71000, '2024-02-01')",
            (business_test_data["emp_id"],)
        )
        # No exception means success


@requires_postgres
def test_first_salary_insert_always_allowed(pg_conn, business_test_data):
    """Step 2.F.3: First salary record (no previous) always passes."""
    with pg_conn.cursor() as cur:
        set_actor(cur, business_test_data["user_id"])

        # Insert a new employee with no salary history
        cur.execute(
            """
            INSERT INTO employees
                (full_name, email, role_id, national_id_encrypted, contact_info_encrypted, date_hired)
            VALUES ('Dan New', 'dan@test.com', %s, %s, %s, '2024-01-15')
            RETURNING employee_id
            """,
            (business_test_data["role_id"], b"\x11\x22\x33", b"\x44\x55\x66")
        )
        new_emp_id = cur.fetchone()[0]

        # Even a very low first salary should be allowed
        cur.execute(
            "INSERT INTO salary_history (employee_id, amount, effective_date) "
            "VALUES (%s, 30000, '2024-02-01')",
            (new_emp_id,)
        )


# ---------------------------------------------------------------------------
# DB-013: National ID Immutability
# ---------------------------------------------------------------------------
@requires_postgres
def test_national_id_change_blocked(pg_conn, business_test_data):
    """Step 2.G.1: Changing national_id_encrypted must raise 'national_id_immutable'."""
    import psycopg2

    with pg_conn.cursor() as cur:
        set_actor(cur, business_test_data["user_id"])
        with pytest.raises(psycopg2.errors.RaiseException) as exc_info:
            cur.execute(
                "UPDATE employees SET national_id_encrypted = %s WHERE employee_id = %s",
                (b"\xFF\xFF\xFF", business_test_data["emp_id"])
            )
        assert "national_id_immutable" in str(exc_info.value)


@requires_postgres
def test_other_fields_update_allowed(pg_conn, business_test_data):
    """Step 2.G.2: Updating non-NID fields must succeed without error."""
    with pg_conn.cursor() as cur:
        set_actor(cur, business_test_data["user_id"])
        cur.execute(
            "UPDATE employees SET full_name = 'Carol White Updated' WHERE employee_id = %s",
            (business_test_data["emp_id"],)
        )


# ---------------------------------------------------------------------------
# DB-014: Self-Salary Modification Block
# ---------------------------------------------------------------------------
@requires_postgres
def test_self_salary_modification_blocked(pg_conn, business_test_data):
    """Step 2.H.1: Employee modifying their own salary must raise 'self_modification_blocked'."""
    import psycopg2

    with pg_conn.cursor() as cur:
        emp_id = business_test_data["emp_id"]
        user_id = business_test_data["user_id"]

        # Set actor as the employee themselves
        cur.execute(f"SET LOCAL argus.actor_user_id = {user_id}")
        cur.execute(f"SET LOCAL argus.actor_employee_id = {emp_id}")

        with pytest.raises((psycopg2.errors.RaiseException, psycopg2.Error)) as exc_info:
            cur.execute(
                "INSERT INTO salary_history (employee_id, amount, effective_date) "
                "VALUES (%s, 95000, '2024-03-01')",
                (emp_id,)
            )
        assert "self_modification_blocked" in str(exc_info.value)


@requires_postgres
def test_hr_modifying_other_employee_salary_allowed(pg_conn, business_test_data):
    """Step 2.H.2: HR Admin modifying a different employee's salary must pass."""
    with pg_conn.cursor() as cur:
        emp_id = business_test_data["emp_id"]
        user_id = business_test_data["user_id"]

        # Actor is user (hr_admin) but actor_employee_id is different from target
        cur.execute(f"SET LOCAL argus.actor_user_id = {user_id}")
        cur.execute("SET LOCAL argus.actor_employee_id = 9999")  # Different employee

        cur.execute(
            "INSERT INTO salary_history (employee_id, amount, effective_date) "
            "VALUES (%s, 95000, '2024-04-01')",
            (emp_id,)
        )
