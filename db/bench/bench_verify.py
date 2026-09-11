#!/usr/bin/env python3
"""BENCH-004: Verification Latency Benchmarks for Argus.

Measures sequential hash-chain verification performance across different audit log
sizes (e.g., 100, 1,000, 10,000, 50,000, 100,000 entries).

Reports wall-clock verification time, throughput (entries/second), and chain validity.
Results are exported to a structured CSV file for research and complexity analysis.

Usage::

    python -m db.bench.bench_verify --db-url postgresql://… --sizes 100 1000 10000 --runs 3
    python -m db.bench.bench_verify --skip-seed  # verify existing database rows

"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
import time
from typing import Any

import psycopg2

from db.bench.seed import (
    _ensure_prerequisites,
    clear_data,
    get_connection,
    seed_employees,
    seed_salary_records,
)
from db.cli.hash_verifier import verify_chain

logger = logging.getLogger("argus.bench.verify")


def count_audit_entries(conn: Any) -> int:
    """Count total entries in the audit_log table.

    Args:
        conn: psycopg2 connection.

    Returns:
        Total number of rows.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM audit_log")
        return cur.fetchone()[0]


def run_verify_benchmarks(
    db_url: str | None,
    sizes: list[int],
    runs: int,
    page_size: int,
    output_path: str,
    skip_seed: bool = False,
) -> int:
    """Execute verification latency benchmarks across audit log sizes.

    Args:
        db_url: PostgreSQL connection string.
        sizes: Target audit log row count sizes.
        runs: Number of benchmark runs per size to average/median.
        page_size: Keyset pagination page size for chain walk.
        output_path: Path to CSV output file.
        skip_seed: If True, benchmark existing DB data only.

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    conn = get_connection(db_url)
    results: list[dict[str, Any]] = []

    try:
        print(f"\n{'='*70}")
        print("ARGUS VERIFICATION LATENCY BENCHMARK (BENCH-004)")
        print(f"{'='*70}")
        print(f"Target sizes    : {sizes if not skip_seed else ['current_db']}")
        print(f"Runs per size   : {runs}")
        print(f"Page size       : {page_size}")
        print(f"Output CSV path : {output_path}")
        print(f"{'='*70}\n")

        evaluation_sizes = sizes if not skip_seed else [0]

        for target_size in evaluation_sizes:
            if not skip_seed:
                print(f"\n--- Seeding for Target Size: ~{target_size:,} Audit Entries ---")
                clear_data(conn)
                dept_ids, role_ids, actor_user_id = _ensure_prerequisites(conn)

                # Each employee creates 1 audit entry; each salary record creates 1 audit entry.
                # Total audit entries = num_employees + num_salary_records.
                # We split ~35% employees, ~65% salaries.
                num_emp = max(10, int(target_size * 0.35))
                num_sal = max(0, target_size - num_emp)

                print(f"  Generating {num_emp:,} employees and {num_sal:,} salaries …")
                emp_ids = seed_employees(conn, num_emp, actor_user_id, role_ids, batch_size=1000)
                if num_sal > 0:
                    seed_salary_records(conn, emp_ids, num_sal, actor_user_id, batch_size=1000)

            actual_entries = count_audit_entries(conn)
            print(f"\nEvaluating verification on {actual_entries:,} audit_log entries …")

            run_times: list[float] = []

            for r in range(1, runs + 1):
                t0 = time.perf_counter()
                v_res = verify_chain(conn, start_seq=0, page_size=page_size)
                elapsed = time.perf_counter() - t0
                run_times.append(elapsed)

                throughput = (v_res.total_entries / elapsed) if elapsed > 0 else 0.0

                record = {
                    "target_entries": target_size if not skip_seed else actual_entries,
                    "actual_entries": v_res.total_entries,
                    "run": r,
                    "elapsed_seconds": round(elapsed, 4),
                    "entries_per_second": round(throughput, 1),
                    "is_valid": v_res.is_valid,
                    "mismatches": len(v_res.mismatches),
                    "gaps": len(v_res.gaps),
                    "orphans": len(v_res.orphans),
                }
                results.append(record)

                print(
                    f"  Run {r}/{runs}: {elapsed:.3f}s | "
                    f"{throughput:,.1f} entries/s | "
                    f"Valid: {'✅' if v_res.is_valid else '❌'}"
                )

            avg_time = sum(run_times) / len(run_times)
            avg_throughput = (actual_entries / avg_time) if avg_time > 0 else 0.0
            print(
                f"  Mean across {runs} runs: {avg_time:.3f}s "
                f"({avg_throughput:,.1f} entries/s)"
            )

        # Write results to CSV
        results_dir = os.path.dirname(output_path)
        if results_dir and not os.path.exists(results_dir):
            os.makedirs(results_dir, exist_ok=True)

        fieldnames = [
            "target_entries",
            "actual_entries",
            "run",
            "elapsed_seconds",
            "entries_per_second",
            "is_valid",
            "mismatches",
            "gaps",
            "orphans",
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
        logger.error("Verification benchmark execution failed: %s", exc)
        return 1
    finally:
        conn.close()


def main() -> int:
    """CLI entry point for BENCH-004."""
    parser = argparse.ArgumentParser(
        prog="argus-bench-verify",
        description="Run verification latency benchmarks across audit log sizes (BENCH-004).",
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="PostgreSQL connection string (default: DATABASE_URL env var)",
    )
    parser.add_argument(
        "--sizes",
        type=int,
        nargs="+",
        default=[100, 1000, 10000],
        help="Audit log entry sizes to evaluate (default: 100 1000 10000)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of verification runs per size (default: 3)",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=500,
        help="Keyset pagination page size (default: 500)",
    )
    parser.add_argument(
        "--output",
        default=os.path.join(
            os.path.dirname(__file__), "results", "verify_results.csv"
        ),
        help="Output CSV file path (default: db/bench/results/verify_results.csv)",
    )
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="Skip seeding; run benchmark against current DB rows",
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

    return run_verify_benchmarks(
        db_url=args.db_url,
        sizes=args.sizes,
        runs=args.runs,
        page_size=args.page_size,
        output_path=args.output,
        skip_seed=args.skip_seed,
    )


if __name__ == "__main__":
    sys.exit(main())
