#!/usr/bin/env python3
"""BENCH-001 / BENCH-002: Synthetic data seeding for Argus benchmark suite.

Generates synthetic employees and salary records to populate the database.
Salary rows are batched; employee rows are inserted individually so each
employee receives the matching transaction-local audit blind index.

Usage::

    python -m db.bench.seed --db-url postgresql://… --employees 1000 --salary-records 3000
    python -m db.bench.seed --employees 100000 --salary-records 300000 --batch-size 1000
    python -m db.bench.seed --clear  # truncate and reset chain_state

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

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from db.crypto.pii import prepare_employee_pii, validate_employee_pii_config

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
        db_url: PostgreSQL connection string. Falls back to DATABASE_URL env var.

    Returns:
        A psycopg2 connection object.

    Raises:
        SystemExit: If no database URL is available.
    """
    url = db_url or os.environ.get("DATABASE_URL")
    if not url:
        logger.error("No database URL. Use --db-url or set DATABASE_URL.")
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
        cur.execute("SELECT department_id FROM departments ORDER BY department_id")
        dept_rows = cur.fetchall()
        if dept_rows:
            dept_ids = [r[0] for r in dept_rows]
        else:
            dept_names = ["Engineering", "Finance", "HR", "Marketing", "Operations"]
            dept_ids = []
            for name in dept_names:
                cur.execute(
                    "INSERT INTO departments (name) VALUES (%s) RETURNING department_id",
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
                    "INSERT INTO roles (title, department_id, salary_band_min, salary_band_max) "
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
                "INSERT INTO users (clerk_user_id, full_name, email, role) "
                "VALUES (%s, %s, %s, %s) RETURNING user_id",
                ("bench_seed_actor", "Benchmark Seed Actor", "bench@argus.test", "hr_admin"),
            )
            actor_user_id = cur.fetchone()[0]

    conn.commit()
    return dept_ids, role_ids, actor_user_id


def seed_employees(
    conn: Any,
    num_employees: int,
    actor_user_id: int,
    role_ids: list[int],
    batch_size: int = 1000,
) -> list[int]:
    """Insert encrypted synthetic employees, committing every batch_size rows.

    Args:
        conn: psycopg2 connection.
        num_employees: Number of employees to create.
        actor_user_id: User ID to set as the session actor for triggers.
        role_ids: Available role IDs to assign randomly.
        batch_size: Number of rows per batch insert.

    Returns:
        List of created employee IDs.
    """
    if num_employees <= 0:
        return []
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    employee_ids: list[int] = []
    logger.info("Inserting %d employees (commit interval=%d) …", num_employees, batch_size)

    with conn.cursor() as cur:
        # Set session variable for triggers across transactions
        cur.execute("SET argus.actor_employee_id = '0'")
        cur.execute("SET argus.actor_user_id = %s", (str(actor_user_id),))

        from datetime import date, timedelta
        for i in range(num_employees):
            name = _random_name()
            email = f"{name.lower().replace(' ', '.')}.{i}_{os.urandom(4).hex()}@argus.test"
            role_id = random.choice(role_ids)
            national_id = f"BENCH-{i:08d}-{os.urandom(4).hex()}"
            contact_info = f"Benchmark contact {os.urandom(8).hex()}"
            date_hired = date(2023, 1, 1) + timedelta(days=random.randint(0, 700))
            encrypted_nid, encrypted_contact = prepare_employee_pii(cur, national_id, contact_info)
            cur.execute(
                "INSERT INTO employees "
                "(full_name, email, role_id, national_id_encrypted, contact_info_encrypted, date_hired) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING employee_id",
                (name, email, role_id, encrypted_nid, encrypted_contact, date_hired),
            )
            employee_ids.append(cur.fetchone()[0])
            if (i + 1) % batch_size == 0 or i == num_employees - 1:
                conn.commit()

                if len(employee_ids) % (batch_size * 5) == 0 or len(employee_ids) == num_employees:
                    logger.info(
                        "  Progress: %d / %d employees inserted (%.1f%%)",
                        len(employee_ids),
                        num_employees,
                        (len(employee_ids) / num_employees) * 100,
                    )

    logger.info("Successfully inserted %d employees.", len(employee_ids))
    return employee_ids


def seed_salary_records(
    conn: Any,
    employee_ids: list[int],
    num_records: int,
    actor_user_id: int,
    batch_size: int = 1000,
) -> int:
    """Insert synthetic salary history records in batches.

    Distributes records across employees. Each employee gets at least one
    salary record, and the remaining records are distributed randomly.
    Salary values stay within a reasonable range to avoid triggering the
    >30% decrease business rule (DB-012).

    Args:
        conn: psycopg2 connection.
        employee_ids: List of employee IDs to attach salaries to.
        num_records: Total number of salary records to create.
        actor_user_id: User ID for the session actor variable.
        batch_size: Number of records per batch insert.

    Returns:
        Number of salary records actually inserted.
    """
    from datetime import date, timedelta

    if not employee_ids or num_records <= 0:
        return 0

    logger.info("Inserting %d salary records (batch_size=%d) …", num_records, batch_size)
    inserted = 0
    base_date = date(2024, 1, 1)

    with conn.cursor() as cur:
        # Set session variables so business triggers don't block
        cur.execute("SET argus.actor_employee_id = '0'")
        cur.execute("SET argus.actor_user_id = %s", (str(actor_user_id),))

        # Assign records per employee
        assignments: list[int] = []
        per_employee = max(1, num_records // len(employee_ids))
        for emp_id in employee_ids:
            count = min(per_employee, num_records - len(assignments))
            assignments.extend([emp_id] * count)
            if len(assignments) >= num_records:
                break

        while len(assignments) < num_records:
            assignments.append(random.choice(employee_ids))

        random.shuffle(assignments)

        # Group by employee for sequential date generation
        emp_record_counts: dict[int, int] = {}
        for emp_id in assignments:
            emp_record_counts[emp_id] = emp_record_counts.get(emp_id, 0) + 1

        batch: list[tuple] = []
        for emp_id, count in emp_record_counts.items():
            salary = random.uniform(40000, 150000)
            for j in range(count):
                effective_date = base_date + timedelta(days=j * 30)

                # Gentle random walk: -10% to +15% to strictly avoid >30% drop
                change = random.uniform(-0.10, 0.15)
                salary = max(30000.0, salary * (1 + change))

                batch.append((emp_id, round(salary, 2), effective_date))

                if len(batch) >= batch_size:
                    query = (
                        "INSERT INTO salary_history "
                        "(employee_id, amount, effective_date) "
                        "VALUES %s"
                    )
                    psycopg2.extras.execute_values(cur, query, batch)
                    conn.commit()
                    inserted += len(batch)
                    if inserted % (batch_size * 5) == 0 or inserted >= num_records:
                        logger.info(
                            "  Progress: %d / %d salary records inserted (%.1f%%)",
                            inserted,
                            num_records,
                            (inserted / num_records) * 100,
                        )
                    batch = []

        if batch:
            query = (
                "INSERT INTO salary_history "
                "(employee_id, amount, effective_date) "
                "VALUES %s"
            )
            psycopg2.extras.execute_values(cur, query, batch)
            conn.commit()
            inserted += len(batch)

    logger.info("Successfully inserted %d salary records.", inserted)
    return inserted


def clear_data(conn: Any) -> None:
    """Truncate all seeded data tables in dependency order and reset chain_state.

    Args:
        conn: psycopg2 connection.
    """
    logger.warning("Clearing all seeded data and resetting chain_state …")
    with conn.cursor() as cur:
        # Disable foreign keys / triggers temporarily for clean truncation
        cur.execute("SET session_replication_role = 'replica'")
        cur.execute("TRUNCATE salary_history CASCADE")
        cur.execute("TRUNCATE employees CASCADE")
        cur.execute("TRUNCATE audit_log CASCADE")
        cur.execute("TRUNCATE chain_checkpoints CASCADE")
        cur.execute("TRUNCATE suspicious_activity_flags CASCADE")
        cur.execute("TRUNCATE backups CASCADE")
        # Reset chain_state singleton to genesis
        cur.execute(
            "UPDATE chain_state SET tail_hash = %s, tail_sequence_id = 0, "
            "last_checkpoint_sequence_id = 0 WHERE id = 1",
            ("0" * 64,),
        )
        cur.execute("SET session_replication_role = 'origin'")
    conn.commit()
    logger.info("All tables truncated and chain_state reset to genesis.")


def main() -> int:
    """CLI entry point for the synthetic benchmark data seeding script.

    Returns:
        Exit code — 0 on success, 1 on failure.
    """
    parser = argparse.ArgumentParser(
        prog="argus-seed",
        description="Seed the Argus database with synthetic benchmark data (BENCH-002).",
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
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for INSERT operations and commits (default: 1000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible generation",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Truncate all tables and reset chain_state before seeding",
    )
    parser.add_argument(
        "--clear-only",
        action="store_true",
        help="Only truncate all tables and reset chain_state without inserting new rows",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO)",
    )

    args = parser.parse_args()
    load_dotenv()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    if args.seed is not None:
        random.seed(args.seed)
        logger.info("Random seed initialized to: %d", args.seed)

    # Fail before database setup/clear so an invalid key cannot produce a
    # partially reset database or allow plaintext fallback.
    if not args.clear_only:
        validate_employee_pii_config()

    conn = get_connection(args.db_url)
    try:
        if args.clear or args.clear_only:
            clear_data(conn)
            if args.clear_only:
                return 0

        t0 = time.time()

        dept_ids, role_ids, actor_user_id = _ensure_prerequisites(conn)
        employee_ids = seed_employees(
            conn,
            args.employees,
            actor_user_id,
            role_ids,
            batch_size=args.batch_size,
        )
        num_salary = seed_salary_records(
            conn,
            employee_ids,
            args.salary_records,
            actor_user_id,
            batch_size=args.batch_size,
        )

        elapsed = time.time() - t0
        total_rows = len(employee_ids) + num_salary
        throughput = (total_rows / elapsed) if elapsed > 0 else 0

        print(f"\n{'='*55}")
        print("ARGUS BENCHMARK SEED COMPLETE")
        print(f"{'='*55}")
        print(f"Employees created    : {len(employee_ids):,}")
        print(f"Salary records       : {num_salary:,}")
        print(f"Total rows inserted  : {total_rows:,}")
        print(f"Elapsed time         : {elapsed:.2f}s")
        print(f"Throughput           : {throughput:.1f} rows/s")
        print(f"{'='*55}\n")

        return 0

    except Exception as exc:
        logger.error("Seeding failed: %s", exc)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
