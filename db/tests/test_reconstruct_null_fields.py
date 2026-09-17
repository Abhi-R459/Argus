"""Targeted test suite for HARDEN-006A: JSONB NULL Merging in State Reconstruction.

Validates that:
1. When employee records or audit log payloads contain fields explicitly updated to NULL
   (e.g., reports_to := NULL or termination_date := NULL), the PL/pgSQL function
   reconstruct_employee_state(p_employee_id, p_as_of) properly preserves the key
   with a JSON null value.
2. The key is NOT silently dropped from the reconstructed dictionary.
3. The stale prior value is NOT resurrected or preserved after the NULL update.
4. Subsequent updates to unrelated fields maintain the explicit NULL status of previously
   nullified fields across successive delta merges.
5. Point-in-time time-travel correctly yields the historical non-null value before the update
   and the explicit NULL value after the update.
"""

import os
import json
import time
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine, text

POSTGRES_AVAILABLE = bool(os.environ.get("DATABASE_URL"))
requires_postgres = pytest.mark.skipif(
    not POSTGRES_AVAILABLE,
    reason="PostgreSQL not available — skipping live state reconstruction tests",
)


def get_db_url():
    return os.environ.get("DATABASE_URL", "postgresql://postgres:password@localhost:5433/argus")


@pytest.fixture(scope="module")
def pg_conn():
    """Return a live connection to PostgreSQL."""
    if not POSTGRES_AVAILABLE:
        pytest.skip("DATABASE_URL not set")
    import psycopg2
    conn = psycopg2.connect(get_db_url())
    conn.autocommit = False
    yield conn
    conn.rollback()
    conn.close()


@pytest.fixture(autouse=True)
def rollback_each_test(pg_conn):
    """Ensure clean transaction state for each test."""
    yield
    pg_conn.rollback()


class TestReconstructNullFieldsDirectAuditLog:
    """Validates reconstruct_employee_state() behavior against audit_log entries containing NULL fields."""

    def test_null_merging_preserves_null_and_overwrites_stale_value(self, pg_conn):
        """Assert that an UPDATE setting a field to null overwrites the prior value and keeps the key."""
        with pg_conn.cursor() as cur:
            synthetic_emp_id = 888801
            now = datetime.now(timezone.utc)
            t1 = now - timedelta(seconds=30)
            t2 = now - timedelta(seconds=20)
            t3 = now - timedelta(seconds=10)

            # Insert initial state at t1: reports_to is 10, termination_date is '2026-12-31'
            cur.execute(
                """
                INSERT INTO audit_log (
                    sequence_id, table_name, row_id, action, actor_user_id,
                    old_value, new_value, previous_hash, entry_hash, severity, created_at
                ) VALUES (
                    (SELECT COALESCE(MAX(sequence_id), 0) + 1 FROM audit_log),
                    'employees', %s, 'INSERT', 1,
                    NULL,
                    %s::jsonb,
                    '0000000000000000000000000000000000000000000000000000000000000000',
                    '1111111111111111111111111111111111111111111111111111111111111111',
                    'INFO', %s
                )
                """,
                (
                    synthetic_emp_id,
                    json.dumps({
                        "employee_id": synthetic_emp_id,
                        "full_name": "Alice NullTest",
                        "email": "alice.nulltest@argus.internal",
                        "reports_to": 10,
                        "termination_date": "2026-12-31",
                        "role_id": 1,
                    }),
                    t1,
                ),
            )

            # Reconstruct at t1: verify fields exist with initial values
            cur.execute(
                "SELECT reconstruct_employee_state(%s, %s)",
                (synthetic_emp_id, t1 + timedelta(seconds=1)),
            )
            state_t1 = cur.fetchone()[0]
            assert state_t1 is not None, "State at t1 should exist"
            assert state_t1["reports_to"] == 10
            assert state_t1["termination_date"] == "2026-12-31"

            # Update at t2: set reports_to to NULL while leaving termination_date untouched
            cur.execute(
                """
                INSERT INTO audit_log (
                    sequence_id, table_name, row_id, action, actor_user_id,
                    old_value, new_value, previous_hash, entry_hash, severity, created_at
                ) VALUES (
                    (SELECT COALESCE(MAX(sequence_id), 0) + 1 FROM audit_log),
                    'employees', %s, 'UPDATE', 1,
                    %s::jsonb,
                    %s::jsonb,
                    '1111111111111111111111111111111111111111111111111111111111111111',
                    '2222222222222222222222222222222222222222222222222222222222222222',
                    'INFO', %s
                )
                """,
                (
                    synthetic_emp_id,
                    json.dumps({"reports_to": 10}),
                    json.dumps({"reports_to": None}),
                    t2,
                ),
            )

            # Reconstruct at t2: verify reports_to is None (JSON null), NOT 10, and key is preserved
            cur.execute(
                "SELECT reconstruct_employee_state(%s, %s)",
                (synthetic_emp_id, t2 + timedelta(seconds=1)),
            )
            state_t2 = cur.fetchone()[0]
            assert state_t2 is not None
            assert "reports_to" in state_t2, "Key 'reports_to' must not be dropped"
            assert state_t2["reports_to"] is None, "Stale value 10 must be overwritten by null"
            assert state_t2["termination_date"] == "2026-12-31", "Unchanged fields must be preserved"

            # Update at t3: set termination_date to NULL and modify email
            cur.execute(
                """
                INSERT INTO audit_log (
                    sequence_id, table_name, row_id, action, actor_user_id,
                    old_value, new_value, previous_hash, entry_hash, severity, created_at
                ) VALUES (
                    (SELECT COALESCE(MAX(sequence_id), 0) + 1 FROM audit_log),
                    'employees', %s, 'UPDATE', 1,
                    %s::jsonb,
                    %s::jsonb,
                    '2222222222222222222222222222222222222222222222222222222222222222',
                    '3333333333333333333333333333333333333333333333333333333333333333',
                    'INFO', %s
                )
                """,
                (
                    synthetic_emp_id,
                    json.dumps({"termination_date": "2026-12-31", "email": "alice.nulltest@argus.internal"}),
                    json.dumps({"termination_date": None, "email": "alice.promoted@argus.internal"}),
                    t3,
                ),
            )

            # Reconstruct at t3: verify both reports_to and termination_date are None
            cur.execute(
                "SELECT reconstruct_employee_state(%s, %s)",
                (synthetic_emp_id, t3 + timedelta(seconds=1)),
            )
            state_t3 = cur.fetchone()[0]
            assert state_t3 is not None
            assert "reports_to" in state_t3, "Key 'reports_to' must still be present"
            assert state_t3["reports_to"] is None, "reports_to must remain null across subsequent deltas"
            assert "termination_date" in state_t3, "Key 'termination_date' must not be dropped"
            assert state_t3["termination_date"] is None, "termination_date must be explicitly null"
            assert state_t3["email"] == "alice.promoted@argus.internal"

            # Verify historical point-in-time query at t1 is unaffected (immutability of history)
            cur.execute(
                "SELECT reconstruct_employee_state(%s, %s)",
                (synthetic_emp_id, t1 + timedelta(seconds=1)),
            )
            state_historical = cur.fetchone()[0]
            assert state_historical["reports_to"] == 10
            assert state_historical["termination_date"] == "2026-12-31"

    def test_reconstruct_state_reviving_value_after_null(self, pg_conn):
        """Assert that a field previously set to NULL can later be updated back to a non-null value."""
        with pg_conn.cursor() as cur:
            synthetic_emp_id = 888802
            now = datetime.now(timezone.utc)
            t1 = now - timedelta(seconds=30)
            t2 = now - timedelta(seconds=20)
            t3 = now - timedelta(seconds=10)

            # Insert: reports_to = 50
            cur.execute(
                """
                INSERT INTO audit_log (sequence_id, table_name, row_id, action, actor_user_id, old_value, new_value, previous_hash, entry_hash, severity, created_at)
                VALUES ((SELECT COALESCE(MAX(sequence_id), 0) + 1 FROM audit_log), 'employees', %s, 'INSERT', 1, NULL, %s::jsonb, '0' * 64, '1' * 64, 'INFO', %s)
                """,
                (synthetic_emp_id, json.dumps({"employee_id": synthetic_emp_id, "reports_to": 50}), t1)
            )

            # Update to NULL
            cur.execute(
                """
                INSERT INTO audit_log (sequence_id, table_name, row_id, action, actor_user_id, old_value, new_value, previous_hash, entry_hash, severity, created_at)
                VALUES ((SELECT COALESCE(MAX(sequence_id), 0) + 1 FROM audit_log), 'employees', %s, 'UPDATE', 1, %s::jsonb, %s::jsonb, '1' * 64, '2' * 64, 'INFO', %s)
                """,
                (synthetic_emp_id, json.dumps({"reports_to": 50}), json.dumps({"reports_to": None}), t2)
            )

            # Update back to 75
            cur.execute(
                """
                INSERT INTO audit_log (sequence_id, table_name, row_id, action, actor_user_id, old_value, new_value, previous_hash, entry_hash, severity, created_at)
                VALUES ((SELECT COALESCE(MAX(sequence_id), 0) + 1 FROM audit_log), 'employees', %s, 'UPDATE', 1, %s::jsonb, %s::jsonb, '2' * 64, '3' * 64, 'INFO', %s)
                """,
                (synthetic_emp_id, json.dumps({"reports_to": None}), json.dumps({"reports_to": 75}), t3)
            )

            # Reconstruct at t2: must be None
            cur.execute("SELECT reconstruct_employee_state(%s, %s)", (synthetic_emp_id, t2 + timedelta(seconds=1)))
            state_t2 = cur.fetchone()[0]
            assert state_t2["reports_to"] is None

            # Reconstruct at t3: must be 75 (not stuck on None)
            cur.execute("SELECT reconstruct_employee_state(%s, %s)", (synthetic_emp_id, t3 + timedelta(seconds=1)))
            state_t3 = cur.fetchone()[0]
            assert state_t3["reports_to"] == 75

    def test_reconstruct_state_after_deletion_returns_null(self, pg_conn):
        """Assert that a DELETE action clears the reconstructed state to NULL."""
        with pg_conn.cursor() as cur:
            synthetic_emp_id = 888803
            now = datetime.now(timezone.utc)
            t1 = now - timedelta(seconds=20)
            t2 = now - timedelta(seconds=10)

            # Insert
            cur.execute(
                """
                INSERT INTO audit_log (sequence_id, table_name, row_id, action, actor_user_id, old_value, new_value, previous_hash, entry_hash, severity, created_at)
                VALUES ((SELECT COALESCE(MAX(sequence_id), 0) + 1 FROM audit_log), 'employees', %s, 'INSERT', 1, NULL, %s::jsonb, '0' * 64, '1' * 64, 'INFO', %s)
                """,
                (synthetic_emp_id, json.dumps({"employee_id": synthetic_emp_id, "full_name": "Deleted Person"}), t1)
            )

            # Delete
            cur.execute(
                """
                INSERT INTO audit_log (sequence_id, table_name, row_id, action, actor_user_id, old_value, new_value, previous_hash, entry_hash, severity, created_at)
                VALUES ((SELECT COALESCE(MAX(sequence_id), 0) + 1 FROM audit_log), 'employees', %s, 'DELETE', 1, %s::jsonb, NULL, '1' * 64, '2' * 64, 'CRITICAL', %s)
                """,
                (synthetic_emp_id, json.dumps({"employee_id": synthetic_emp_id, "full_name": "Deleted Person"}), t2)
            )

            # Reconstruct before delete: state exists
            cur.execute("SELECT reconstruct_employee_state(%s, %s)", (synthetic_emp_id, t1 + timedelta(seconds=1)))
            assert cur.fetchone()[0] is not None

            # Reconstruct after delete: state is NULL
            cur.execute("SELECT reconstruct_employee_state(%s, %s)", (synthetic_emp_id, t2 + timedelta(seconds=1)))
            assert cur.fetchone()[0] is None

    def test_reconstruct_nonexistent_employee_returns_null(self, pg_conn):
        """Assert that querying an unknown employee ID yields NULL state."""
        with pg_conn.cursor() as cur:
            cur.execute("SELECT reconstruct_employee_state(%s, NOW())", (999999999,))
            assert cur.fetchone()[0] is None



class TestReconstructNullFieldsLiveTrigger:
    """Validates transactional trigger execution when table has a nullable column set to NULL."""

    def test_live_table_null_column_mutation_reconstruction(self, pg_conn):
        """Add a temporary nullable column, insert with value, update to NULL, and reconstruct."""
        import uuid
        unique_email = f"null.col.{uuid.uuid4().hex[:8]}@test.internal"
        pg_conn.autocommit = True
        cur = pg_conn.cursor()
        emp_id = None
        try:
            # Set actor for trigger session variable
            cur.execute("SET argus.actor_user_id = 1")

            # Add a temporary nullable column to employees
            cur.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS reports_to INT NULL")

            # Ensure prerequisite role and department exist
            cur.execute("SELECT role_id FROM roles LIMIT 1")
            role_row = cur.fetchone()
            if not role_row:
                cur.execute("INSERT INTO departments (name) VALUES ('Test Dept') RETURNING department_id")
                dept_id = cur.fetchone()[0]
                cur.execute(
                    "INSERT INTO roles (title, department_id, salary_band_min, salary_band_max) "
                    "VALUES ('Tester', %s, 40000, 80000) RETURNING role_id",
                    (dept_id,),
                )
                role_id = cur.fetchone()[0]
            else:
                role_id = role_row[0]

            # Insert an employee with reports_to = 99
            cur.execute(
                """
                INSERT INTO employees (
                    full_name, email, role_id, national_id_encrypted,
                    contact_info_encrypted, date_hired, reports_to
                ) VALUES (
                    'Null Column Employee', %s, %s,
                    '\\x1234'::bytea, '\\x5678'::bytea, '2025-01-01', 99
                ) RETURNING employee_id
                """,
                (unique_email, role_id),
            )
            emp_id = cur.fetchone()[0]

            # Fetch exact timestamp of the INSERT audit record
            cur.execute(
                "SELECT created_at FROM audit_log WHERE table_name = 'employees' AND row_id = %s AND action = 'INSERT'",
                (emp_id,),
            )
            t_insert = cur.fetchone()[0]

            # Reconstruct after insert: reports_to should be 99
            cur.execute(
                "SELECT reconstruct_employee_state(%s, %s)",
                (emp_id, t_insert),
            )
            state_inserted = cur.fetchone()[0]
            assert state_inserted is not None
            assert state_inserted["reports_to"] == 99

            # Small delay so next transaction gets a strictly later timestamp
            time.sleep(0.05)

            # Update reports_to to NULL in a new transaction
            cur.execute("SET argus.actor_user_id = 1")
            cur.execute(
                "UPDATE employees SET reports_to = NULL WHERE employee_id = %s",
                (emp_id,),
            )

            # Fetch exact timestamp of the UPDATE audit record
            cur.execute(
                "SELECT created_at FROM audit_log WHERE table_name = 'employees' AND row_id = %s AND action = 'UPDATE'",
                (emp_id,),
            )
            t_update = cur.fetchone()[0]
            assert t_update > t_insert, "Update timestamp must be strictly later than insert timestamp"

            # Reconstruct after update: reports_to must be None (JSON null) and key preserved
            cur.execute(
                "SELECT reconstruct_employee_state(%s, %s)",
                (emp_id, t_update),
            )
            state_updated = cur.fetchone()[0]
            assert state_updated is not None
            assert "reports_to" in state_updated, "Key 'reports_to' must be present in JSONB"
            assert state_updated["reports_to"] is None, "reports_to must be None after update to NULL"

            # Point-in-time check before update: reports_to should still be 99
            cur.execute(
                "SELECT reconstruct_employee_state(%s, %s)",
                (emp_id, t_insert),
            )
            state_historical = cur.fetchone()[0]
            assert state_historical is not None
            assert state_historical["reports_to"] == 99, f"Historical state before update must be 99, got {state_historical['reports_to']}"

        finally:
            # Drop the temporary test column from employees
            cur.execute("ALTER TABLE employees DROP COLUMN IF EXISTS reports_to")
            cur.close()
            pg_conn.autocommit = False
