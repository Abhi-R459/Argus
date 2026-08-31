#!/usr/bin/env python3
"""BENCH-001: Pilot benchmark for Argus chain verification.

Runs the verification engine against a seeded database and records
wall-clock timing results.

Usage::

    python -m db.bench.pilot_benchmark --db-url postgresql://…

Prerequisites:
    Run ``python -m db.bench.seed`` first to populate the database.

"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from typing import Any

logger = logging.getLogger("argus.bench.pilot")


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


def count_audit_entries(conn: Any) -> int:
    """Count total audit log entries.

    Args:
        conn: psycopg2 connection.

    Returns:
        Total number of rows in audit_log.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM audit_log")
        return cur.fetchone()[0]


def run_sequential_verification(conn: Any, page_size: int = 500) -> dict:
    """Run sequential chain verification and measure timing.

    Args:
        conn: psycopg2 connection.
        page_size: Batch size for keyset pagination.

    Returns:
        Dict with timing and result summary.
    """
    try:
        from db.cli.hash_verifier import verify_chain
    except ImportError:
        from hash_verifier import verify_chain  # type: ignore[no-redef]

    t0 = time.time()
    result = verify_chain(conn, start_seq=0, page_size=page_size)
    elapsed = time.time() - t0

    return {
        "mode": "sequential",
        "total_entries": result.total_entries,
        "is_valid": result.is_valid,
        "mismatches": len(result.mismatches),
        "gaps": len(result.gaps),
        "orphans": len(result.orphans),
        "elapsed_seconds": round(elapsed, 3),
        "entries_per_second": round(result.total_entries / elapsed, 1) if elapsed > 0 else 0,
    }


def run_pilot_benchmark(db_url: str | None, output_path: str) -> int:
    """Execute the pilot benchmark and write results.

    Args:
        db_url: PostgreSQL connection string.
        output_path: Path to write results file.

    Returns:
        Exit code — 0 on success, 1 on failure.
    """
    conn = get_connection(db_url)

    try:
        # Count entries
        total = count_audit_entries(conn)
        if total == 0:
            logger.error(
                "No audit log entries found.  Run seed.py first."
            )
            return 1

        print(f"\n{'='*60}")
        print("ARGUS PILOT BENCHMARK")
        print(f"{'='*60}")
        print(f"Audit log entries  : {total}")
        print()

        # Sequential verification
        print("Running sequential verification …")
        seq_result = run_sequential_verification(conn)
        print(f"  Entries verified : {seq_result['total_entries']}")
        print(f"  Chain valid      : {'✅' if seq_result['is_valid'] else '❌'}")
        print(f"  Elapsed          : {seq_result['elapsed_seconds']}s")
        print(f"  Throughput       : {seq_result['entries_per_second']} entries/s")
        print()

        # Write results to file
        results_dir = os.path.dirname(output_path)
        if results_dir and not os.path.exists(results_dir):
            os.makedirs(results_dir, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("Argus Pilot Benchmark Results\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Total audit log entries: {total}\n\n")

            f.write("Sequential Verification\n")
            f.write("-" * 30 + "\n")
            for k, v in seq_result.items():
                f.write(f"  {k:25s}: {v}\n")
            f.write("\n")

            # Pass/fail summary
            if seq_result["elapsed_seconds"] < 30:
                f.write("RESULT: PASS — verification completed in < 30 seconds\n")
                print("RESULT: ✅ PASS — verification completed in < 30 seconds")
            else:
                f.write(
                    f"RESULT: SLOW — verification took "
                    f"{seq_result['elapsed_seconds']}s (target: < 30s)\n"
                )
                print(
                    f"RESULT: ⚠️  SLOW — verification took "
                    f"{seq_result['elapsed_seconds']}s (target: < 30s)"
                )

        print(f"\nResults written to: {output_path}")
        print(f"{'='*60}\n")

        return 0

    except Exception as exc:
        logger.error("Pilot benchmark failed: %s", exc)
        return 1
    finally:
        conn.close()


def main() -> int:
    """CLI entry point for the pilot benchmark.

    Returns:
        Exit code — 0 on success, 1 on failure.
    """
    parser = argparse.ArgumentParser(
        prog="argus-pilot-benchmark",
        description="Run the Argus pilot verification benchmark.",
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="PostgreSQL connection string (default: DATABASE_URL env var)",
    )
    parser.add_argument(
        "--output",
        default=os.path.join(
            os.path.dirname(__file__), "pilot_results.txt"
        ),
        help="Output file for results (default: db/bench/pilot_results.txt)",
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

    return run_pilot_benchmark(args.db_url, args.output)


if __name__ == "__main__":
    sys.exit(main())
