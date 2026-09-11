#!/usr/bin/env python3
"""BENCH-005: Checkpoint-Interval Sweep Benchmark for Argus.

Evaluates the tradeoff between checkpoint creation frequency and verification performance.
Sweeps checkpoint intervals (e.g., 10, 25, 50, 100, 250, 500, 1000) over a fixed-size
audit log, measuring:
  1. Time to generate checkpoints and total checkpoints created.
  2. Sequential verification time (baseline).
  3. Parallel verification time using the checkpoint-derived segments.
  4. Parallel speedup ratio (sequential / parallel).

Results are exported to CSV for Pareto frontier and optimal interval analysis.

Usage::

    python -m db.bench.bench_checkpoint_sweep --db-url postgresql://… --intervals 10 25 50 100 250 500
    python -m db.bench.bench_checkpoint_sweep --skip-seed

"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import logging
import os
import sys
import time
from typing import Any

import psycopg2
import psycopg2.extras

from db.bench.seed import (
    _ensure_prerequisites,
    clear_data,
    get_connection,
    seed_employees,
    seed_salary_records,
)
from db.cli.chain_walker import walk_chain
from db.cli.checkpoint_store import (
    compute_checkpoint_hash,
    get_all_checkpoints,
    store_checkpoint,
)
from db.cli.hash_verifier import (
    VerificationResult,
    merge_results,
    verify_chain,
    verify_segment,
)
from db.cli.verifier import _build_segments

logger = logging.getLogger("argus.bench.checkpoint_sweep")


def count_audit_entries(conn: Any) -> int:
    """Count total rows in the audit_log table.

    Args:
        conn: psycopg2 connection.

    Returns:
        Total number of rows in audit_log.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM audit_log")
        return cur.fetchone()[0]


def clear_checkpoints(conn: Any) -> None:
    """Truncate the chain_checkpoints table.

    Args:
        conn: psycopg2 connection.
    """
    with conn.cursor() as cur:
        cur.execute("TRUNCATE chain_checkpoints CASCADE")
    conn.commit()


def create_checkpoints_for_interval(
    conn: Any,
    interval: int,
    page_size: int = 500,
) -> tuple[int, float]:
    """Create checkpoints across the entire audit log for a given interval.

    Args:
        conn: psycopg2 connection.
        interval: Checkpoint interval (number of entries per checkpoint).
        page_size: Page size for keyset pagination.

    Returns:
        Tuple of (number of checkpoints created, elapsed creation time in seconds).
    """
    clear_checkpoints(conn)

    entry_hashes: list[str] = []
    checkpoint_count = 0
    last_seq_id = 0
    placeholder_sig = b"\x00" * 64

    t0 = time.perf_counter()

    for batch in walk_chain(conn, start_seq=0, page_size=page_size):
        for row in batch:
            entry_hashes.append(row["entry_hash"])
            last_seq_id = row["sequence_id"]

            if len(entry_hashes) >= interval:
                cp_hash = compute_checkpoint_hash(entry_hashes)
                store_checkpoint(conn, last_seq_id, cp_hash, placeholder_sig)
                checkpoint_count += 1
                entry_hashes = []

    # Checkpoint remaining entries
    if entry_hashes:
        cp_hash = compute_checkpoint_hash(entry_hashes)
        store_checkpoint(conn, last_seq_id, cp_hash, placeholder_sig)
        checkpoint_count += 1

    elapsed = time.perf_counter() - t0
    return checkpoint_count, elapsed


def execute_parallel_verification(
    conn: Any,
    db_url: str,
    checkpoints: list[dict],
    max_workers: int,
    page_size: int = 500,
    start_seq: int = 0,
) -> tuple[VerificationResult, float]:
    """Execute parallel chain verification using checkpoint segment boundaries.

    Args:
        conn: Parent psycopg2 connection for boundary checks.
        db_url: Database connection string for worker processes.
        checkpoints: List of checkpoint dicts.
        max_workers: Number of concurrent worker processes.
        page_size: Page size for keyset pagination.
        start_seq: Global sequence start offset.

    Returns:
        Tuple of (merged VerificationResult, elapsed seconds).
    """
    segments = _build_segments(checkpoints, start_seq=start_seq)
    num_segments = len(segments)
    actual_workers = min(num_segments, max_workers)

    t0 = time.perf_counter()
    segment_results: list[VerificationResult] = [None] * num_segments  # type: ignore[list-item]

    with concurrent.futures.ProcessPoolExecutor(max_workers=actual_workers) as executor:
        future_to_idx = {
            executor.submit(
                verify_segment,
                db_url,
                seg_start,
                seg_end,
                "0" * 64 if seg_start == start_seq else "",
                page_size,
            ): idx
            for idx, (seg_start, seg_end) in enumerate(segments)
        }

        for future in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                segment_results[idx] = future.result()
            except Exception as exc:
                seg_start, _ = segments[idx]
                segment_results[idx] = VerificationResult(
                    is_valid=False,
                    total_entries=0,
                    orphans=[{
                        "sequence_id": seg_start,
                        "expected_prev": "(unknown)",
                        "actual_prev": f"worker_error: {exc}",
                    }],
                )

    # Cross-segment continuity check
    cross_segment_orphans: list[dict] = []
    for i in range(1, len(segment_results)):
        prev_res = segment_results[i - 1]
        curr_res = segment_results[i]
        if (
            prev_res.last_sequence_id >= 0
            and curr_res.last_sequence_id >= 0
            and curr_res.total_entries > 0
        ):
            seg_start_seq, _ = segments[i]
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT sequence_id, previous_hash FROM audit_log "
                    "WHERE sequence_id > %s ORDER BY sequence_id LIMIT 1",
                    (seg_start_seq,),
                )
                first_row = cur.fetchone()

            if first_row and first_row["previous_hash"] != prev_res.last_computed_hash:
                cross_segment_orphans.append({
                    "sequence_id": first_row["sequence_id"],
                    "expected_prev": prev_res.last_computed_hash,
                    "actual_prev": first_row["previous_hash"],
                    "note": "cross-segment boundary break",
                })

    merged = merge_results(segment_results)
    if cross_segment_orphans:
        merged.orphans.extend(cross_segment_orphans)
        merged.orphans.sort(key=lambda x: x.get("sequence_id", 0))
        merged.is_valid = False

    elapsed = time.perf_counter() - t0
    return merged, elapsed


def run_checkpoint_sweep(
    db_url: str | None,
    intervals: list[int],
    target_entries: int,
    workers: int,
    page_size: int,
    output_path: str,
    skip_seed: bool = False,
) -> int:
    """Run the checkpoint interval sweep benchmark.

    Args:
        db_url: PostgreSQL connection string.
        intervals: List of checkpoint interval sizes to sweep.
        target_entries: Number of audit entries to seed if not skipping seed.
        workers: Parallel workers for verification.
        page_size: Batch size for queries.
        output_path: Path to CSV output file.
        skip_seed: If True, do not seed data; use existing audit log entries.

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    resolved_db_url = db_url or os.environ.get("DATABASE_URL")
    if not resolved_db_url:
        logger.error("No database URL provided.")
        return 1

    conn = get_connection(resolved_db_url)
    results: list[dict[str, Any]] = []

    try:
        if not skip_seed:
            print(f"\n--- Seeding Database with ~{target_entries:,} Audit Entries ---")
            clear_data(conn)
            dept_ids, role_ids, actor_user_id = _ensure_prerequisites(conn)
            num_emp = max(10, int(target_entries * 0.35))
            num_sal = max(0, target_entries - num_emp)
            emp_ids = seed_employees(conn, num_emp, actor_user_id, role_ids, batch_size=1000)
            if num_sal > 0:
                seed_salary_records(conn, emp_ids, num_sal, actor_user_id, batch_size=1000)

        total_entries = count_audit_entries(conn)
        if total_entries == 0:
            logger.error("No audit entries found. Run with seeding first.")
            return 1

        print(f"\n{'='*75}")
        print("ARGUS CHECKPOINT INTERVAL SWEEP BENCHMARK (BENCH-005)")
        print(f"{'='*75}")
        print(f"Total audit entries : {total_entries:,}")
        print(f"Intervals to test   : {intervals}")
        print(f"Parallel workers    : {workers}")
        print(f"Output CSV path     : {output_path}")
        print(f"{'='*75}\n")

        # Baseline: Run sequential verification once
        print("Measuring baseline sequential verification time …")
        t_seq_start = time.perf_counter()
        seq_result = verify_chain(conn, start_seq=0, page_size=page_size)
        seq_time = time.perf_counter() - t_seq_start
        print(
            f"Sequential baseline: {seq_time:.3f}s | "
            f"{(total_entries / seq_time):,.1f} entries/s | "
            f"Valid: {'✅' if seq_result.is_valid else '❌'}\n"
        )

        for interval in intervals:
            print(f"--- Evaluating Checkpoint Interval: {interval:,} entries ---")

            # 1. Create checkpoints
            cp_count, create_time = create_checkpoints_for_interval(
                conn, interval, page_size=page_size
            )
            print(f"  Checkpoints created : {cp_count:,} in {create_time:.3f}s")

            # 2. Parallel verification
            checkpoints = get_all_checkpoints(conn)
            par_result, par_time = execute_parallel_verification(
                conn,
                resolved_db_url,
                checkpoints,
                max_workers=workers,
                page_size=page_size,
            )

            speedup = (seq_time / par_time) if par_time > 0 else 0.0
            print(
                f"  Parallel verify time: {par_time:.3f}s | "
                f"Speedup vs sequential: {speedup:.2f}x | "
                f"Valid: {'✅' if par_result.is_valid else '❌'}"
            )

            record = {
                "interval": interval,
                "audit_entries": total_entries,
                "num_checkpoints": cp_count,
                "create_seconds": round(create_time, 4),
                "verify_sequential_seconds": round(seq_time, 4),
                "verify_parallel_seconds": round(par_time, 4),
                "parallel_speedup": round(speedup, 2),
                "is_valid": par_result.is_valid,
            }
            results.append(record)

        # Write results to CSV
        results_dir = os.path.dirname(output_path)
        if results_dir and not os.path.exists(results_dir):
            os.makedirs(results_dir, exist_ok=True)

        fieldnames = [
            "interval",
            "audit_entries",
            "num_checkpoints",
            "create_seconds",
            "verify_sequential_seconds",
            "verify_parallel_seconds",
            "parallel_speedup",
            "is_valid",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                writer.writerow(row)

        print(f"\n{'='*75}")
        print("Checkpoint sweep completed! Results written to:")
        print(f"  {os.path.abspath(output_path)}")
        print(f"{'='*75}\n")
        return 0

    except Exception as exc:
        logger.error("Checkpoint sweep failed: %s", exc)
        return 1
    finally:
        conn.close()


def main() -> int:
    """CLI entry point for BENCH-005."""
    parser = argparse.ArgumentParser(
        prog="argus-bench-checkpoint-sweep",
        description="Sweep checkpoint intervals to evaluate tradeoff between checkpoint frequency and verification performance (BENCH-005).",
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="PostgreSQL connection string (default: DATABASE_URL env var)",
    )
    parser.add_argument(
        "--intervals",
        type=int,
        nargs="+",
        default=[10, 25, 50, 100, 250, 500, 1000],
        help="Checkpoint intervals to evaluate (default: 10 25 50 100 250 500 1000)",
    )
    parser.add_argument(
        "--target-entries",
        type=int,
        default=5000,
        help="Target audit entries to seed if not using --skip-seed (default: 5000)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of worker processes for parallel verification (default: 4)",
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
            os.path.dirname(__file__), "results", "checkpoint_sweep_results.csv"
        ),
        help="Output CSV file path (default: db/bench/results/checkpoint_sweep_results.csv)",
    )
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="Skip seeding; evaluate against current audit log rows",
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

    return run_checkpoint_sweep(
        db_url=args.db_url,
        intervals=args.intervals,
        target_entries=args.target_entries,
        workers=args.workers,
        page_size=args.page_size,
        output_path=args.output,
        skip_seed=args.skip_seed,
    )


if __name__ == "__main__":
    sys.exit(main())
