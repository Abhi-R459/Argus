#!/usr/bin/env python3
"""BENCH-001: Synthetic data seeding for Argus pilot benchmark.

Generates synthetic employees and salary records to populate the database
for benchmark testing.  Uses batch inserts for efficiency.

Usage::

    python -m db.bench.seed --db-url postgresql://… --employees 1000 --salary-records 3000
    python -m db.bench.seed --clear  # truncate and reseed

"""

from __future__ import annotations

import argparse
import logging
import os
import random
import string
import sys
import time
from typing import Any

logger = logging.getLogger("argus.bench.seed")


def _random_string(length: int = 10) -> str:
    """Generate a random alphanumeric string.

    Args:
        length: Number of characters.

    Returns:
        Random string of the specified length.
    """
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def _random_name() -> str:
    """Generate a random human-like name.

    Returns:
        A string in the format 'Firstname Lastname'.
    """
    first_names = [
        "Alice", "Bob", "Carol", "David", "Eve", "Frank", "Grace",
        "Hank", "Ivy", "Jack", "Karen", "Leo", "Mia", "Nate",
        "Olivia", "Paul", "Quinn", "Rita", "Sam", "Tina",
        "Uma", "Victor", "Wendy", "Xavier", "Yara", "Zane",
    ]
    last_names = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
        "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez",
        "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas",
        "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez",
        "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez",
    ]
    return f"{random.choice(first_names)} {random.choice(last_names)}"


def get_connection(db_url: str | None = None) -> Any:
    """Create a psycopg2 connection.

    Args:
        db_url: PostgreSQL connection string.  Falls back to DATABASE_URL env var.

    Returns:
        A psycopg2 connection object.

    Raises:
        SystemExit: If no database URL is available.
    """
    import psycopg2

    url = db_url or os.environ.get("DATABASE_URL")
    if not url:
        logger.error("No database URL.  Use --db-url or set DATABASE_URL.")
        sys.exit(1)

    try:
        conn = psycopg2.connect(url)
        return conn
    except Exception as exc:
        logger.error("Connection failed: %s", exc)
        sys.exit(1)


def _ensure_prerequisites(conn: Any) -> tuple[list[int], list[int], int]:
    """Ensure departments, roles, and a seed user exist.

    Creates minimal prerequisite data if missing and returns IDs needed
    for employee generation.

    Args:
        conn: psycopg2 connection.

    Returns:
        Tuple of (department_ids, role_ids, actor_user_id).
    """
    with conn.cursor() as cur:
        # --- Departments ---
        cur.execute("SELECT id FROM departments ORDER BY id")
        dept_rows = cur.fetchall()
        if dept_rows:
            dept_ids = [r[0] for r in dept_rows]
        else:
            dept_names = ["Engineering", "Finance", "HR", "Marketing", "Operations"]
            dept_ids = []
            for name in dept_names:
                cur.execute(
                    "INSERT INTO departments (name) VALUES (%s) RETURNING id",
                    (name,),
                )
                dept_ids.append(cur.fetchone()[0])

        # --- Roles ---
        cur.execute("SELECT role_id FROM roles ORDER BY role_id")
        role_rows = cur.fetchall()
        if role_rows:
            role_ids = [r[0] for r in role_rows]
        else:
            role_defs = [
                ("Junior Engineer", 40000, 70000),
                ("Senior Engineer", 70000, 120000),
                ("Manager", 80000, 150000),
                ("Analyst", 45000, 90000),
                ("Director", 100000, 200000),
            ]
            role_ids = []
            for title, min_sal, max_sal in role_defs:
                dept_id = random.choice(dept_ids)
                cur.execute(
                    "INSERT INTO roles (title, department_id, min_salary, max_salary) "
                    "VALUES (%s, %s, %s, %s) RETURNING role_id",
                    (title, dept_id, min_sal, max_sal),
                )
                role_ids.append(cur.fetchone()[0])

        # --- Seed user (actor for audit trail) ---
        cur.execute(
            "SELECT user_id FROM users WHERE clerk_user_id = %s",
            ("bench_seed_actor",),
        )
        row = cur.fetchone()
        if row:
            actor_user_id = row[0]
        else:
            cur.execute(
                "INSERT INTO users (clerk_user_id, email, role) "
                "VALUES (%s, %s, %s) RETURNING user_id",
                ("bench_seed_actor", "bench@argus.test", "hr_admin"),
            )
            actor_user_id = cur.fetchone()[0]

    conn.commit()
    return dept_ids, role_ids, actor_user_id


def seed_employees(
    conn: Any,
    num_employees: int,
    actor_user_id: int,
    role_ids: list[int],
    batch_size: int = 500,
) -> list[int]:
    """Insert synthetic employees in batches.

    Args:
        conn: psycopg2 connection.
        num_employees: Number of employees to create.
        actor_user_id: User ID to set as the session actor for triggers.
        role_ids: Available role IDs to assign randomly.
        batch_size: Number of rows per INSERT batch.

    Returns:
        List of created employee IDs.
    """
    import psycopg2.extras

    employee_ids: list[int] = []
    logger.info("Inserting %d employees …", num_employees)

    with conn.cursor() as cur:
        # Set session variable for self-salary-modification trigger
        cur.execute("SET LOCAL argus.actor_employee_id = '0'")

        batch: list[tuple] = []
        for i in range(num_employees):
            name = _random_name()
            role_id = random.choice(role_ids)
            national_id = os.urandom(16)  # simulated encrypted bytes
            contact_info = os.urandom(16)

            batch.append((
                name,
                role_id,
                national_id,
                contact_info,
            ))

            if len(batch) >= batch_size or i == num_employees - 1:
                # Use execute_values for efficient batch insert
                query = (
                    "INSERT INTO employees "
                    "(full_name, role_id, national_id_encrypted, contact_info_encrypted) "
                    "VALUES %s RETURNING employee_id"
                )
                template = "(%s, %s, %s, %s)"
                # execute_values doesn't support RETURNING well, so use individual inserts
                for row in batch:
                    cur.execute(
                        "INSERT INTO employees "
                        "(full_name, role_id, national_id_encrypted, contact_info_encrypted) "
                        "VALUES (%s, %s, %s, %s) RETURNING employee_id",
                        row,
                    )
                    employee_ids.append(cur.fetchone()[0])

                conn.commit()
                logger.debug(
                    "  Inserted batch: %d/%d employees",
                    len(employee_ids),
                    num_employees,
                )
                batch = []

    logger.info("Inserted %d employees.", len(employee_ids))
    return employee_ids


def seed_salary_records(
    conn: Any,
    employee_ids: list[int],
    num_records: int,
    actor_user_id: int,
) -> int:
    """Insert synthetic salary history records.

    Distributes records across employees.  Each employee gets at least one
    salary record, and the remaining records are distributed randomly.
    Salary values stay within a reasonable range to avoid triggering the
    >30% decrease business rule.

    Args:
        conn: psycopg2 connection.
        employee_ids: List of employee IDs to attach salaries to.
        num_records: Total number of salary records to create.
        actor_user_id: User ID for the session actor variable.

    Returns:
        Number of salary records actually inserted.
    """
    from datetime import date, timedelta

    logger.info("Inserting %d salary records …", num_records)
    inserted = 0

    # Track last salary per employee to avoid >30% decrease trigger
    last_salary: dict[int, float] = {}
    base_date = date(2024, 1, 1)

    with conn.cursor() as cur:
        # Set session variable so self-modification trigger doesn't block
        cur.execute(
            "SET LOCAL argus.actor_employee_id = %s",
            (str(actor_user_id),),
        )

        # Build assignment: each employee gets ceil(num_records / len(employee_ids)) records
        assignments: list[int] = []
        per_employee = max(1, num_records // len(employee_ids))
        for emp_id in employee_ids:
            count = min(per_employee, num_records - len(assignments))
            assignments.extend([emp_id] * count)
            if len(assignments) >= num_records:
                break

        # Fill remaining slots randomly
        while len(assignments) < num_records:
            assignments.append(random.choice(employee_ids))

        random.shuffle(assignments)

        # Group by employee for sequential date generation
        emp_record_counts: dict[int, int] = {}
        for emp_id in assignments:
            emp_record_counts[emp_id] = emp_record_counts.get(emp_id, 0) + 1

        for emp_id, count in emp_record_counts.items():
            salary = random.uniform(40000, 150000)
            for j in range(count):
                effective_date = base_date + timedelta(days=j * 30)

                # Gentle random walk: ±15% max to stay within 30% rule
                change = random.uniform(-0.10, 0.15)
                salary = max(30000, salary * (1 + change))

                try:
                    cur.execute(
                        "INSERT INTO salary_history "
                        "(employee_id, amount, effective_date) "
                        "VALUES (%s, %s, %s)",
                        (emp_id, round(salary, 2), effective_date),
                    )
                    inserted += 1
                    last_salary[emp_id] = salary
                except Exception as exc:
                    # Some inserts may fail due to unique constraints or
                    # business rules — log and continue
                    conn.rollback()
                    logger.debug(
                        "Skipped salary record for emp %d: %s", emp_id, exc
                    )
                else:
                    conn.commit()

                if inserted % 500 == 0 and inserted > 0:
                    logger.debug("  Inserted %d/%d salary records", inserted, num_records)

    logger.info("Inserted %d salary records.", inserted)
    return inserted


def clear_data(conn: Any) -> None:
    """Truncate all seeded data tables in dependency order.

    Args:
        conn: psycopg2 connection.
    """
    logger.warning("Clearing all data …")
    with conn.cursor() as cur:
        # Disable triggers temporarily for clean truncation
        cur.execute("SET session_replication_role = 'replica'")
        cur.execute("TRUNCATE salary_history CASCADE")
        cur.execute("TRUNCATE employees CASCADE")
        cur.execute("TRUNCATE audit_log CASCADE")
        cur.execute("TRUNCATE chain_checkpoints CASCADE")
        cur.execute("TRUNCATE suspicious_activity_flags CASCADE")
        cur.execute("TRUNCATE backups CASCADE")
        # Reset chain_state
        cur.execute(
            "UPDATE chain_state SET tail_hash = %s, tail_sequence_id = 0, "
            "last_checkpoint_sequence_id = 0 WHERE id = 1",
            ("0" * 64,),
        )
        cur.execute("SET session_replication_role = 'origin'")
    conn.commit()
    logger.info("All data cleared.")


def main() -> int:
    """CLI entry point for the seed script.

    Returns:
        Exit code — 0 on success, 1 on failure.
    """
    parser = argparse.ArgumentParser(
        prog="argus-seed",
        description="Seed the Argus database with synthetic benchmark data.",
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="PostgreSQL connection string (default: DATABASE_URL env var)",
    )
    parser.add_argument(
        "--employees",
        type=int,
        default=1000,
        help="Number of employees to create (default: 1000)",
    )
    parser.add_argument(
        "--salary-records",
        type=int,
        default=3000,
        help="Number of salary records to create (default: 3000)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Truncate all data before seeding",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    conn = get_connection(args.db_url)
    try:
        if args.clear:
            clear_data(conn)

        t0 = time.time()

        dept_ids, role_ids, actor_user_id = _ensure_prerequisites(conn)
        employee_ids = seed_employees(
            conn, args.employees, actor_user_id, role_ids,
        )
        num_salary = seed_salary_records(
            conn, employee_ids, args.salary_records, actor_user_id,
        )

        elapsed = time.time() - t0
        print(f"\n{'='*50}")
        print(f"SEED COMPLETE")
        print(f"{'='*50}")
        print(f"Employees created  : {len(employee_ids)}")
        print(f"Salary records     : {num_salary}")
        print(f"Elapsed time       : {elapsed:.1f}s")
        print(f"{'='*50}\n")

        return 0

    except Exception as exc:
        logger.error("Seeding failed: %s", exc)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
