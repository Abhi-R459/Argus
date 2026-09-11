#!/usr/bin/env python3
"""BENCH-006: Parallel vs Sequential Verification at Scale for Argus.

Empirical evaluation comparing sequential chain verification against parallel
checkpoint-bounded segment verification (VERIFY-006) across varying worker counts
(e.g., 1, 2, 4, 8 workers) on large audit logs (e.g., 10,000 to 100,000+ entries).

Measures wall-clock time, verification throughput (entries/sec), parallel speedup,
and parallel efficiency.

Outputs detailed CSV metrics for Section 16 research write-up and plotting.

Usage::

    python -m db.bench.bench_parallel --db-url postgresql://… --workers 1 2 4 8 --runs 3
    python -m db.bench.bench_parallel --skip-seed  # run on existing data

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

logger = logging.getLogger("argus.bench.parallel")


def count_audit_entries(conn: Any) -> int:
    """Count total rows in audit_log.

    Args:
        conn: psycopg2 connection.

    Returns:
        Total row count.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM audit_log")
        return cur.fetchone()[0]


def ensure_checkpoints_exist(
    conn: Any,
    interval: int = 500,
    page_size: int = 500,
) -> int:
    """Ensure checkpoints exist in chain_checkpoints table.

    If none exist, walks the audit log and creates them at the specified interval.

    Args:
        conn: psycopg2 connection.
        interval: Checkpoint creation interval in entries.
        page_size: Batch size for pagination.

    Returns:
        Total count of checkpoints in database.
    """
    checkpoints = get_all_checkpoints(conn)
    if checkpoints:
        logger.info("Found %d existing checkpoints.", len(checkpoints))
        return len(checkpoints)

    logger.info("No checkpoints found. Creating checkpoints every %d entries …", interval)
    entry_hashes: list[str] = []
    created_count = 0
    last_seq_id = 0
    placeholder_sig = b"\x00" * 64

    for batch in walk_chain(conn, start_seq=0, page_size=page_size):
        for row in batch:
            entry_hashes.append(row["entry_hash"])
            last_seq_id = row["sequence_id"]

            if len(entry_hashes) >= interval:
                cp_hash = compute_checkpoint_hash(entry_hashes)
                store_checkpoint(conn, last_seq_id, cp_hash, placeholder_sig)
                created_count += 1
                entry_hashes = []

    if entry_hashes:
        cp_hash = compute_checkpoint_hash(entry_hashes)
        store_checkpoint(conn, last_seq_id, cp_hash, placeholder_sig)
        created_count += 1

    logger.info("Created %d checkpoints for parallel segmentation.", created_count)
    return created_count


def execute_parallel_verification(
    conn: Any,
    db_url: str,
    checkpoints: list[dict],
    max_workers: int,
    page_size: int = 500,
    start_seq: int = 0,
) -> tuple[VerificationResult, float]:
    """Execute parallel chain verification with a fixed worker pool size.

    Args:
        conn: Parent psycopg2 connection for boundary orphan check.
        db_url: Database connection string for child worker processes.
        checkpoints: List of checkpoint dicts defining segment boundaries.
        max_workers: Process pool size.
        page_size: Pagination page size.
        start_seq: Start sequence offset.

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


def run_parallel_benchmarks(
    db_url: str | None,
    worker_counts: list[int],
    runs: int,
    checkpoint_interval: int,
    target_entries: int,
    page_size: int,
    output_path: str,
    skip_seed: bool = False,
) -> int:
    """Run sequential vs parallel verification benchmarks across worker counts.

    Args:
        db_url: PostgreSQL connection string.
        worker_counts: List of worker counts to test for parallel mode (e.g. [1, 2, 4, 8]).
        runs: Number of benchmark runs per configuration.
        checkpoint_interval: Interval for checkpoints.
        target_entries: Rows to seed if not skipping seed.
        page_size: Batch size for pagination.
        output_path: Path to CSV output file.
        skip_seed: If True, do not seed.

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

        num_checkpoints = ensure_checkpoints_exist(
            conn, interval=checkpoint_interval, page_size=page_size
        )
        checkpoints = get_all_checkpoints(conn)

        print(f"\n{'='*75}")
        print("ARGUS PARALLEL VS SEQUENTIAL VERIFICATION AT SCALE (BENCH-006)")
        print(f"{'='*75}")
        print(f"Total audit entries : {total_entries:,}")
        print(f"Checkpoints created : {num_checkpoints:,} (interval={checkpoint_interval})")
        print(f"Worker configs      : {worker_counts}")
        print(f"Runs per config     : {runs}")
        print(f"Output CSV path     : {output_path}")
        print(f"{'='*75}\n")

        # ------------------------------------------------------------------
        # Phase 1: Sequential Verification Baseline
        # ------------------------------------------------------------------
        print("--- Running Sequential Verification (Single Process Baseline) ---")
        seq_times: list[float] = []
        for r in range(1, runs + 1):
            t0 = time.perf_counter()
            seq_res = verify_chain(conn, start_seq=0, page_size=page_size)
            elapsed = time.perf_counter() - t0
            seq_times.append(elapsed)

            throughput = (seq_res.total_entries / elapsed) if elapsed > 0 else 0.0
            print(
                f"  Run {r}/{runs}: {elapsed:.3f}s | "
                f"{throughput:,.1f} entries/s | "
                f"Valid: {'✅' if seq_res.is_valid else '❌'}"
            )
            results.append({
                "mode": "sequential",
                "workers": 1,
                "run": r,
                "audit_entries": total_entries,
                "elapsed_seconds": round(elapsed, 4),
                "entries_per_second": round(throughput, 1),
                "speedup_vs_seq": 1.0,
                "is_valid": seq_res.is_valid,
            })

        baseline_median_seq = sorted(seq_times)[len(seq_times) // 2]
        print(f"  Sequential Median Time: {baseline_median_seq:.3f}s\n")

        # ------------------------------------------------------------------
        # Phase 2: Parallel Verification Sweeps
        # ------------------------------------------------------------------
        summary_rows: list[tuple[str, int, float, float, float]] = [
            ("sequential", 1, baseline_median_seq, total_entries / baseline_median_seq, 1.0)
        ]

        for w in worker_counts:
            print(f"--- Running Parallel Verification: {w} Worker(s) ---")
            par_times: list[float] = []

            for r in range(1, runs + 1):
                par_res, elapsed = execute_parallel_verification(
                    conn,
                    resolved_db_url,
                    checkpoints,
                    max_workers=w,
                    page_size=page_size,
                )
                par_times.append(elapsed)
                speedup = (baseline_median_seq / elapsed) if elapsed > 0 else 0.0
                throughput = (par_res.total_entries / elapsed) if elapsed > 0 else 0.0

                print(
                    f"  Run {r}/{runs}: {elapsed:.3f}s | "
                    f"{throughput:,.1f} entries/s | "
                    f"Speedup: {speedup:.2f}x | "
                    f"Valid: {'✅' if par_res.is_valid else '❌'}"
                )

                results.append({
                    "mode": "parallel",
                    "workers": w,
                    "run": r,
                    "audit_entries": total_entries,
                    "elapsed_seconds": round(elapsed, 4),
                    "entries_per_second": round(throughput, 1),
                    "speedup_vs_seq": round(speedup, 2),
                    "is_valid": par_res.is_valid,
                })

            median_par = sorted(par_times)[len(par_times) // 2]
            overall_speedup = (baseline_median_seq / median_par) if median_par > 0 else 0.0
            overall_throughput = total_entries / median_par if median_par > 0 else 0.0
            summary_rows.append(("parallel", w, median_par, overall_throughput, overall_speedup))
            print(
                f"  {w} Worker(s) Median: {median_par:.3f}s | "
                f"Speedup: {overall_speedup:.2f}x\n"
            )

        # Print Comparison Summary Table
        print(f"{'='*70}")
        print("PARALLEL VS SEQUENTIAL VERIFICATION SUMMARY TABLE")
        print(f"{'='*70}")
        print(f"{'Mode':<14} | {'Workers':<8} | {'Median Time':<12} | {'Throughput':<16} | {'Speedup':<8}")
        print(f"{'-'*14}-+-{'-'*8}-+-{'-'*12}-+-{'-'*16}-+-{'-'*8}")
        for mode, w, m_time, t_put, spd in summary_rows:
            print(f"{mode:<14} | {w:<8} | {m_time:>9.3f}s  | {t_put:>12,.1f} e/s | {spd:>6.2f}x")
        print(f"{'='*70}\n")

        # Write results to CSV
        results_dir = os.path.dirname(output_path)
        if results_dir and not os.path.exists(results_dir):
            os.makedirs(results_dir, exist_ok=True)

        fieldnames = [
            "mode",
            "workers",
            "run",
            "audit_entries",
            "elapsed_seconds",
            "entries_per_second",
            "speedup_vs_seq",
            "is_valid",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                writer.writerow(row)

        print(f"Detailed CSV results written to:\n  {os.path.abspath(output_path)}\n")
        return 0

    except Exception as exc:
        logger.error("Parallel benchmark run failed: %s", exc)
        return 1
    finally:
        conn.close()


def main() -> int:
    """CLI entry point for BENCH-006."""
    parser = argparse.ArgumentParser(
        prog="argus-bench-parallel",
        description="Compare sequential vs parallel verification at scale across worker counts (BENCH-006).",
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="PostgreSQL connection string (default: DATABASE_URL env var)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        nargs="+",
        default=[1, 2, 4, 8],
        help="Worker process pool sizes to evaluate (default: 1 2 4 8)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Benchmark repetitions per configuration (default: 3)",
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=500,
        help="Checkpoint interval for segment partitioning (default: 500)",
    )
    parser.add_argument(
        "--target-entries",
        type=int,
        default=10000,
        help="Number of audit rows to seed if not skipping seed (default: 10000)",
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
            os.path.dirname(__file__), "results", "parallel_results.csv"
        ),
        help="Output CSV file path (default: db/bench/results/parallel_results.csv)",
    )
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="Skip seeding; benchmark against current database audit_log rows",
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

    return run_parallel_benchmarks(
        db_url=args.db_url,
        worker_counts=args.workers,
        runs=args.runs,
        checkpoint_interval=args.checkpoint_interval,
        target_entries=args.target_entries,
        page_size=args.page_size,
        output_path=args.output,
        skip_seed=args.skip_seed,
    )


if __name__ == "__main__":
    sys.exit(main())
