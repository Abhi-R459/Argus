#!/usr/bin/env python3
"""BENCH-003: Insert/Update/Delete Latency Benchmarks for Argus.

Measures transaction latency (P50, P95, P99, mean, min, max) for individual
INSERT, UPDATE, and DELETE operations on audited tables across various database
scales (e.g., 100, 1,000, 10,000, 100,000 rows).

Each operation triggers the full AFTER hash-chaining logic and singleton row lock
in PostgreSQL, measuring real-world overhead of the tamper-evident audit system.

Outputs results to CSV format for plotting and academic analysis.

Usage::

    python -m db.bench.bench_latency --db-url postgresql://… --levels 100 1000 10000 --samples 50
    python -m db.bench.bench_latency --output db/bench/results/latency_results.csv

"""

from __future__ import annotations

import argparse
import csv
import logging
import math
import os
import random
import sys
import time
from typing import Any

import psycopg2
from dotenv import load_dotenv
from db.crypto.pii import prepare_employee_pii, validate_employee_pii_config

from db.bench.seed import (
    _ensure_prerequisites,
    _random_name,
    clear_data,
    get_connection,
    seed_employees,
    seed_salary_records,
)

logger = logging.getLogger("argus.bench.latency")


def _percentile(values: list[float], p: float) -> float:
    """Calculate the p-th percentile from a sorted list of floats.

    Args:
        values: Sorted list of floating point values.
        p: Percentile between 0.0 and 100.0.

    Returns:
        The calculated percentile value.
    """
    if not values:
        return 0.0
    k = (len(values) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return values[int(k)]
    d0 = values[int(f)] * (c - k)
    d1 = values[int(c)] * (k - f)
    return d0 + d1


def compute_statistics(samples: list[float]) -> dict[str, float]:
    """Compute summary statistics for a list of latency samples (in milliseconds).

    Args:
        samples: List of measured latency values in milliseconds.

    Returns:
        Dict with count, min, max, mean, p50, p95, p99, and stddev.
    """
    if not samples:
        return {
            "samples": 0,
            "min_ms": 0.0,
            "max_ms": 0.0,
            "mean_ms": 0.0,
            "p50_ms": 0.0,
            "p95_ms": 0.0,
            "p99_ms": 0.0,
            "stddev_ms": 0.0,
        }

    sorted_samples = sorted(samples)
    n = len(sorted_samples)
    mean_val = sum(sorted_samples) / n
    variance = sum((x - mean_val) ** 2 for x in sorted_samples) / n if n > 1 else 0.0
    stddev = math.sqrt(variance)

    return {
        "samples": n,
        "min_ms": round(sorted_samples[0], 3),
        "max_ms": round(sorted_samples[-1], 3),
        "mean_ms": round(mean_val, 3),
        "p50_ms": round(_percentile(sorted_samples, 50.0), 3),
        "p95_ms": round(_percentile(sorted_samples, 95.0), 3),
        "p99_ms": round(_percentile(sorted_samples, 99.0), 3),
        "stddev_ms": round(stddev, 3),
    }


def measure_insert_latency(
    conn: Any,
    role_ids: list[int],
    actor_user_id: int,
    num_samples: int,
) -> tuple[list[float], list[int]]:
    """Measure single-row INSERT latency on the audited employees table.

    Args:
        conn: psycopg2 connection.
        role_ids: List of available role IDs.
        actor_user_id: Actor user ID for the session context.
        num_samples: Number of INSERT operations to measure.

    Returns:
        Tuple of (list of latency values in ms, list of newly inserted employee IDs).
    """
    latencies: list[float] = []
    inserted_ids: list[int] = []

    with conn.cursor() as cur:
        cur.execute("SET argus.actor_employee_id = '0'")
        cur.execute("SET argus.actor_user_id = %s", (str(actor_user_id),))

        for _ in range(num_samples):
            name = _random_name()
            role_id = random.choice(role_ids)
            national_id = f"LATENCY-{os.urandom(16).hex()}"
            contact_info = f"Benchmark contact {os.urandom(16).hex()}"
            encrypted_nid, encrypted_contact = prepare_employee_pii(cur, national_id, contact_info)

            t0 = time.perf_counter()
            cur.execute(
                "INSERT INTO employees "
                "(full_name, role_id, national_id_encrypted, contact_info_encrypted) "
                "VALUES (%s, %s, %s, %s) RETURNING employee_id",
                (name, role_id, encrypted_nid, encrypted_contact),
            )
            emp_id = cur.fetchone()[0]
            conn.commit()
            t1 = time.perf_counter()

            latencies.append((t1 - t0) * 1000.0)
            inserted_ids.append(emp_id)

    return latencies, inserted_ids


def measure_update_latency(
    conn: Any,
    employee_ids: list[int],
    actor_user_id: int,
    num_samples: int,
) -> list[float]:
    """Measure single-row UPDATE latency on the audited employees table.

    Args:
        conn: psycopg2 connection.
        employee_ids: Pool of existing employee IDs to pick from.
        actor_user_id: Actor user ID for the session context.
        num_samples: Number of UPDATE operations to measure.

    Returns:
        List of measured latencies in milliseconds.
    """
    if not employee_ids:
        return []

    latencies: list[float] = []
    target_ids = [random.choice(employee_ids) for _ in range(num_samples)]

    with conn.cursor() as cur:
        cur.execute("SET argus.actor_employee_id = '0'")
        cur.execute("SET argus.actor_user_id = %s", (str(actor_user_id),))

        for emp_id in target_ids:
            updated_name = _random_name() + " (Updated)"

            t0 = time.perf_counter()
            cur.execute(
                "UPDATE employees SET full_name = %s WHERE employee_id = %s",
                (updated_name, emp_id),
            )
            conn.commit()
            t1 = time.perf_counter()

            latencies.append((t1 - t0) * 1000.0)

    return latencies


def measure_delete_latency(
    conn: Any,
    employee_ids: list[int],
    actor_user_id: int,
    num_samples: int,
) -> list[float]:
    """Measure single-row DELETE latency on the audited employees table.

    Args:
        conn: psycopg2 connection.
        employee_ids: Pool of employee IDs available for deletion.
        actor_user_id: Actor user ID for session context.
        num_samples: Number of DELETE operations to measure.

    Returns:
        List of measured latencies in milliseconds.
    """
    if not employee_ids:
        return []

    num_to_delete = min(num_samples, len(employee_ids))
    targets_to_delete = [employee_ids.pop() for _ in range(num_to_delete)]
    latencies: list[float] = []

    with conn.cursor() as cur:
        cur.execute("SET argus.actor_employee_id = '0'")
        cur.execute("SET argus.actor_user_id = %s", (str(actor_user_id),))

        for emp_id in targets_to_delete:
            # First remove any child salary_history records to satisfy FK
            cur.execute("DELETE FROM salary_history WHERE employee_id = %s", (emp_id,))

            t0 = time.perf_counter()
            cur.execute("DELETE FROM employees WHERE employee_id = %s", (emp_id,))
            conn.commit()
            t1 = time.perf_counter()

            latencies.append((t1 - t0) * 1000.0)

    return latencies


def run_latency_benchmarks(
    db_url: str | None,
    levels: list[int],
    num_samples: int,
    output_path: str,
    skip_seed: bool = False,
    clear_between: bool = True,
) -> int:
    """Run latency benchmarks for INSERT, UPDATE, and DELETE at specified scales.

    Args:
        db_url: PostgreSQL connection string.
        levels: Target employee row count levels (e.g. [100, 1000, 10000]).
        num_samples: Number of operations measured per type per scale.
        output_path: Path to CSV output file.
        skip_seed: If True, skip seeding and measure against existing database.
        clear_between: If True, clear and reseed for each level.

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    load_dotenv()
    # The run always measures INSERTs, including --skip-seed runs. Validate
    # before connecting because the later setup may clear seeded tables.
    validate_employee_pii_config()
    conn = get_connection(db_url)
    results: list[dict[str, Any]] = []

    try:
        dept_ids, role_ids, actor_user_id = _ensure_prerequisites(conn)

        print(f"\n{'='*70}")
        print("ARGUS INSERT/UPDATE/DELETE LATENCY BENCHMARK (BENCH-003)")
        print(f"{'='*70}")
        print(f"Row count levels : {levels}")
        print(f"Samples per test : {num_samples}")
        print(f"Output CSV path  : {output_path}")
        print(f"{'='*70}\n")

        for level in levels:
            print(f"\n--- Benchmark Level: {level:,} Initial Rows ---")

            if not skip_seed:
                if clear_between:
                    clear_data(conn)
                    dept_ids, role_ids, actor_user_id = _ensure_prerequisites(conn)

                # Seed base rows for this scale
                print(f"Seeding {level:,} employees and {level * 2:,} salary records …")
                emp_ids = seed_employees(
                    conn,
                    level,
                    actor_user_id,
                    role_ids,
                    batch_size=min(1000, max(100, level // 10)),
                )
                seed_salary_records(
                    conn,
                    emp_ids,
                    level * 2,
                    actor_user_id,
                    batch_size=min(1000, max(100, level // 10)),
                )
            else:
                with conn.cursor() as cur:
                    cur.execute("SELECT employee_id FROM employees LIMIT %s", (level,))
                    emp_ids = [r[0] for r in cur.fetchall()]

            # 1. Measure INSERT
            print(f"  Measuring {num_samples} INSERTs …")
            insert_lats, new_ids = measure_insert_latency(
                conn, role_ids, actor_user_id, num_samples
            )
            emp_ids.extend(new_ids)
            insert_stats = compute_statistics(insert_lats)
            results.append({"level": level, "operation": "INSERT", **insert_stats})
            print(
                f"    INSERT P50: {insert_stats['p50_ms']}ms | "
                f"P95: {insert_stats['p95_ms']}ms | "
                f"P99: {insert_stats['p99_ms']}ms | "
                f"Mean: {insert_stats['mean_ms']}ms"
            )

            # 2. Measure UPDATE
            print(f"  Measuring {num_samples} UPDATEs …")
            update_lats = measure_update_latency(
                conn, emp_ids, actor_user_id, num_samples
            )
            update_stats = compute_statistics(update_lats)
            results.append({"level": level, "operation": "UPDATE", **update_stats})
            print(
                f"    UPDATE P50: {update_stats['p50_ms']}ms | "
                f"P95: {update_stats['p95_ms']}ms | "
                f"P99: {update_stats['p99_ms']}ms | "
                f"Mean: {update_stats['mean_ms']}ms"
            )

            # 3. Measure DELETE
            print(f"  Measuring {num_samples} DELETEs …")
            delete_lats = measure_delete_latency(
                conn, emp_ids, actor_user_id, num_samples
            )
            delete_stats = compute_statistics(delete_lats)
            results.append({"level": level, "operation": "DELETE", **delete_stats})
            print(
                f"    DELETE P50: {delete_stats['p50_ms']}ms | "
                f"P95: {delete_stats['p95_ms']}ms | "
                f"P99: {delete_stats['p99_ms']}ms | "
                f"Mean: {delete_stats['mean_ms']}ms"
            )

        # Write results to CSV
        results_dir = os.path.dirname(output_path)
        if results_dir and not os.path.exists(results_dir):
            os.makedirs(results_dir, exist_ok=True)

        fieldnames = [
            "level",
            "operation",
            "samples",
            "p50_ms",
            "p95_ms",
            "p99_ms",
            "mean_ms",
            "min_ms",
            "max_ms",
            "stddev_ms",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                writer.writerow(row)

        print(f"\n{'='*70}")
        print(f"Benchmark completed successfully! Results written to:")
        print(f"  {os.path.abspath(output_path)}")
        print(f"{'='*70}\n")
        return 0

    except Exception as exc:
        logger.error("Latency benchmark execution failed: %s", exc)
        return 1
    finally:
        conn.close()


def main() -> int:
    """CLI entry point for BENCH-003."""
    parser = argparse.ArgumentParser(
        prog="argus-bench-latency",
        description="Run insert/update/delete latency benchmarks across database scales (BENCH-003).",
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="PostgreSQL connection string (default: DATABASE_URL env var)",
    )
    parser.add_argument(
        "--levels",
        type=int,
        nargs="+",
        default=[100, 1000, 10000],
        help="Row count scale levels to evaluate (default: 100 1000 10000)",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=50,
        help="Number of latency samples measured per operation per level (default: 50)",
    )
    parser.add_argument(
        "--output",
        default=os.path.join(
            os.path.dirname(__file__), "results", "latency_results.csv"
        ),
        help="Output CSV file path (default: db/bench/results/latency_results.csv)",
    )
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="Skip seeding; run benchmark against current DB rows",
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Do not clear between levels (accumulate data instead)",
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

    return run_latency_benchmarks(
        db_url=args.db_url,
        levels=args.levels,
        num_samples=args.samples,
        output_path=args.output,
        skip_seed=args.skip_seed,
        clear_between=not args.no_clear,
    )


if __name__ == "__main__":
    sys.exit(main())
