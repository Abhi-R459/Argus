#!/usr/bin/env python3
"""Argus Verification Engine CLI.

VERIFY-001: CLI skeleton with argparse subcommands.
VERIFY-004: Checkpoint creation with configurable interval.
VERIFY-006: Parallel checkpoint verification engine.

This standalone tool walks the audit_log hash chain, recomputes every hash,
detects tampering/gaps/orphans, creates and stores signed checkpoints, and
anchors them externally.  It is intentionally decoupled from the FastAPI
application (Decision #5) so that a compromise of the app cannot compromise
the verifier.

Usage::

    python -m db.cli.verifier verify-chain --db-url postgresql://…
    python -m db.cli.verifier create-checkpoint --checkpoint-interval 25
    python -m db.cli.verifier sign-checkpoint --checkpoint-id 1
    python -m db.cli.verifier anchor --type local --path ./anchors
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import hashlib
import json
import logging
import os
import sys
import time
from typing import Any

import psycopg2
import psycopg2.extras

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logger = logging.getLogger("argus.verifier")


def _configure_logging(level_name: str) -> None:
    """Configure root logger with the given level.

    Args:
        level_name: One of DEBUG, INFO, WARNING, ERROR.
    """
    numeric = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )


# ---------------------------------------------------------------------------
# Database connection helper
# ---------------------------------------------------------------------------
def get_connection(db_url: str | None = None) -> Any:
    """Create a psycopg2 connection from a URL.

    Args:
        db_url: PostgreSQL connection string.  Falls back to the
            ``DATABASE_URL`` environment variable when *None*.

    Returns:
        A ``psycopg2`` connection object.

    Raises:
        SystemExit: If no database URL is available.
    """
    url = db_url or os.environ.get("DATABASE_URL")
    if not url:
        logger.error(
            "No database URL provided.  Use --db-url or set DATABASE_URL."
        )
        sys.exit(1)

    logger.debug("Connecting to database …")
    try:
        conn = psycopg2.connect(url)
        logger.debug("Connected successfully.")
        return conn
    except psycopg2.Error as exc:
        logger.error("Database connection failed: %s", exc)
        sys.exit(1)


# ===================================================================
# Subcommand handlers
# ===================================================================

def _build_segments(
    checkpoints: list[dict], start_seq: int
) -> list[tuple[int, int | None]]:
    """Builds (start_seq, end_seq) segment tuples from checkpoint boundaries.

    Each tuple is an exclusive-lower / inclusive-upper pair that maps directly
    onto ``verify_chain(start_seq=…, end_seq=…)``.

    Args:
        checkpoints: Ordered list of checkpoint dicts (each has 'sequence_id').
        start_seq: The global start sequence (usually 0).

    Returns:
        List of (start_seq, end_seq) tuples covering the full chain.  The
        last tuple always has ``end_seq=None`` so that any rows appended after
        the last checkpoint are still verified.
    """
    segments: list[tuple[int, int | None]] = []
    prev = start_seq
    for cp in checkpoints:
        cp_seq = cp['sequence_id']
        if cp_seq > prev:
            segments.append((prev, cp_seq))
            prev = cp_seq
    # Final open-ended segment covers rows beyond the last checkpoint.
    segments.append((prev, None))
    return segments


def _print_verification_report(
    result: Any,
    mode: str = "sequential",
    num_segments: int = 1,
    workers_used: int = 1,
) -> None:
    """Prints the standard chain verification report to stdout."""
    print(f"\n{'='*60}")
    print("ARGUS CHAIN VERIFICATION REPORT")
    print(f"{'='*60}")
    print(f"Mode                   : {mode}")
    if mode == "parallel":
        print(f"Segments               : {num_segments}")
        print(f"Workers                : {workers_used}")
    print(f"Total entries verified : {result.total_entries}")
    print(f"Hash mismatches        : {len(result.mismatches)}")
    print(f"Sequence gaps          : {len(result.gaps)}")
    print(f"Orphaned entries       : {len(result.orphans)}")
    print(f"Chain status           : {'✅ VALID' if result.is_valid else '❌ TAMPERED'}")
    print(f"{'='*60}\n")

    if result.mismatches:
        print("HASH MISMATCHES:")
        for m in result.mismatches:
            print(f"  seq={m['sequence_id']}: expected={m['expected'][:16]}… actual={m['actual'][:16]}…")

    if result.gaps:
        print("SEQUENCE GAPS:")
        for g in result.gaps:
            print(f"  expected seq={g['expected_seq']}, found seq={g['actual_seq']}")

    if result.orphans:
        print("ORPHANED ENTRIES:")
        for o in result.orphans:
            print(f"  seq={o['sequence_id']}: expected_prev={o['expected_prev'][:16]}… actual_prev={o['actual_prev'][:16]}…")


def _cmd_verify_chain(args: argparse.Namespace) -> int:
    """Handle the ``verify-chain`` subcommand (VERIFY-001 / VERIFY-006).

    Supports both sequential (default) and parallel modes.

    In **sequential** mode the chain is walked in a single process exactly as
    before (backward-compatible).

    In **parallel** mode (``--parallel``):
    1. Checkpoint boundaries are fetched from ``chain_checkpoints``.
    2. The audit_log is split into segments by those boundaries.
    3. ``verify_segment()`` is dispatched per segment via
       ``ProcessPoolExecutor``.
    4. Results are merged with ``merge_results()``.
    5. Cross-segment boundary orphan checks are run sequentially after all
       workers finish to catch hash-link breaks at segment joins.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code — 0 for clean chain, 1 for anomalies detected.
    """
    # Lazy imports so the CLI skeleton loads quickly and --help is instant.
    try:
        from db.cli.hash_verifier import (
            verify_chain,
            verify_segment,
            merge_results,
            VerificationResult,
        )
        from db.cli.checkpoint_store import get_all_checkpoints
    except ImportError:
        from hash_verifier import (  # type: ignore[no-redef]
            verify_chain,
            verify_segment,
            merge_results,
            VerificationResult,
        )
        from checkpoint_store import get_all_checkpoints  # type: ignore[no-redef]

    conn = get_connection(args.db_url)
    try:
        # ------------------------------------------------------------------
        # Dry-run: just count entries and exit.
        # ------------------------------------------------------------------
        if args.dry_run:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM audit_log")
                count = cur.fetchone()[0]
            if count == 0:
                print("No entries found")
                return 0
            else:
                print(f"Found {count} audit log entries (dry-run, skipping verification)")
                return 0

        # ------------------------------------------------------------------
        # Determine mode: parallel when --parallel is set AND checkpoints exist.
        # ------------------------------------------------------------------
        use_parallel = getattr(args, 'parallel', False) and not getattr(args, 'sequential', False)

        if use_parallel:
            checkpoints = get_all_checkpoints(conn)
            if not checkpoints:
                logger.warning(
                    "No checkpoints found — parallel mode requires checkpoints. "
                    "Falling back to sequential verification."
                )
                use_parallel = False

        # ------------------------------------------------------------------
        # Sequential path (default / fallback).
        # ------------------------------------------------------------------
        if not use_parallel:
            logger.info("Starting sequential chain verification …")
            result: VerificationResult = verify_chain(
                conn,
                start_seq=args.start_seq,
                page_size=args.page_size,
            )
            _print_verification_report(result, mode="sequential")
            return 0 if result.is_valid else 1

        # ------------------------------------------------------------------
        # Parallel path.
        # ------------------------------------------------------------------
        db_url: str = args.db_url or os.environ.get("DATABASE_URL", "")
        max_workers: int = args.workers if args.workers > 0 else None  # type: ignore[assignment]
        page_size: int = args.page_size

        segments = _build_segments(checkpoints, start_seq=args.start_seq)
        num_segments = len(segments)
        actual_workers = min(
            num_segments,
            max_workers if max_workers is not None else os.cpu_count() or 1,
        )

        logger.info(
            "Starting parallel chain verification: %d segment(s) across up to %d worker(s) …",
            num_segments,
            actual_workers,
        )

        # Submit all segments concurrently.  Each worker opens its own
        # DB connection (psycopg2 connections are not process-safe).
        # We intentionally do NOT pass the seed hash at dispatch time — each
        # segment is verified internally first; cross-segment continuity is
        # checked sequentially after all workers finish (see below).
        segment_results: list[VerificationResult] = [None] * num_segments  # type: ignore[list-item]

        with concurrent.futures.ProcessPoolExecutor(max_workers=actual_workers) as executor:
            future_to_idx = {
                executor.submit(
                    verify_segment,
                    db_url,
                    seg_start,
                    seg_end,
                    '0' * 64 if seg_start == args.start_seq else '',  # seed bootstrapped internally
                    page_size,
                ): idx
                for idx, (seg_start, seg_end) in enumerate(segments)
            }

            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    segment_results[idx] = future.result()
                    logger.debug(
                        "Segment %d/%d complete: %d entries, valid=%s",
                        idx + 1,
                        num_segments,
                        segment_results[idx].total_entries,
                        segment_results[idx].is_valid,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error("Segment %d worker raised: %s", idx + 1, exc)
                    # Return a synthetic failed result so merging still works.
                    seg_start, seg_end = segments[idx]
                    segment_results[idx] = VerificationResult(
                        is_valid=False,
                        total_entries=0,
                        orphans=[{
                            'sequence_id': seg_start,
                            'expected_prev': '(unknown)',
                            'actual_prev': f'worker_error: {exc}',
                        }],
                    )

        # ------------------------------------------------------------------
        # Cross-segment continuity check.
        # After all workers finish, verify that each segment's last hash
        # matches the next segment's first row's previous_hash.
        # This is done sequentially in the parent process using the
        # last_computed_hash carried back from each worker.
        # ------------------------------------------------------------------
        cross_segment_orphans: list[dict] = []
        for i in range(1, len(segment_results)):
            prev_result = segment_results[i - 1]
            curr_result = segment_results[i]
            if (
                prev_result.last_sequence_id >= 0
                and curr_result.last_sequence_id >= 0
                and curr_result.total_entries > 0
            ):
                # Fetch the first row of the current segment to get its previous_hash.
                seg_start_seq, _ = segments[i]
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        "SELECT sequence_id, previous_hash FROM audit_log "
                        "WHERE sequence_id > %s ORDER BY sequence_id LIMIT 1",
                        (seg_start_seq,),
                    )
                    first_row = cur.fetchone()

                if first_row and first_row['previous_hash'] != prev_result.last_computed_hash:
                    cross_segment_orphans.append({
                        'sequence_id': first_row['sequence_id'],
                        'expected_prev': prev_result.last_computed_hash,
                        'actual_prev': first_row['previous_hash'],
                        'note': 'cross-segment boundary break',
                    })

        # Merge all segment results into a unified report.
        result = merge_results(segment_results)

        # Fold in any cross-segment boundary orphans.
        if cross_segment_orphans:
            result.orphans.extend(cross_segment_orphans)
            result.orphans.sort(key=lambda x: x.get('sequence_id', 0))
            result.is_valid = False

        _print_verification_report(
            result,
            mode="parallel",
            num_segments=num_segments,
            workers_used=actual_workers,
        )
        return 0 if result.is_valid else 1

    finally:
        conn.close()


def _cmd_create_checkpoint(args: argparse.Namespace) -> int:
    """Handle the ``create-checkpoint`` subcommand (VERIFY-004).

    Walks the chain and creates checkpoints at every N entries, computing
    ``checkpoint_hash = sha256(concat of entry_hashes in range)``.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code — 0 on success, 1 on error.
    """
    try:
        from db.cli.chain_walker import walk_chain
        from db.cli.checkpoint_store import store_checkpoint, compute_checkpoint_hash
    except ImportError:
        from chain_walker import walk_chain  # type: ignore[no-redef]
        from checkpoint_store import store_checkpoint, compute_checkpoint_hash  # type: ignore[no-redef]

    conn = get_connection(args.db_url)
    interval = args.checkpoint_interval

    try:
        logger.info(
            "Creating checkpoints every %d entries …", interval
        )

        entry_hashes: list[str] = []
        checkpoint_count = 0
        last_seq_id = 0

        for batch in walk_chain(conn, start_seq=0, page_size=args.page_size):
            for row in batch:
                entry_hashes.append(row["entry_hash"])
                last_seq_id = row["sequence_id"]

                if len(entry_hashes) >= interval:
                    # Compute checkpoint
                    cp_hash = compute_checkpoint_hash(entry_hashes)

                    # Placeholder signature (unsigned) — sign-checkpoint
                    # must be run separately to sign stored checkpoints.
                    placeholder_sig = b"\x00" * 64

                    stored = store_checkpoint(
                        conn, last_seq_id, cp_hash, placeholder_sig
                    )
                    checkpoint_count += 1

                    # Emit JSON event to stdout
                    event = {
                        "event": "checkpoint_created",
                        "checkpoint_sequence_id": last_seq_id,
                        "checkpoint_hash": cp_hash,
                        "entries_in_range": len(entry_hashes),
                        "newly_stored": stored,
                    }
                    print(json.dumps(event))
                    logger.debug("Checkpoint at seq=%d: %s", last_seq_id, cp_hash)

                    entry_hashes = []

        # Handle remaining entries (partial interval)
        if entry_hashes:
            cp_hash = compute_checkpoint_hash(entry_hashes)
            placeholder_sig = b"\x00" * 64
            stored = store_checkpoint(conn, last_seq_id, cp_hash, placeholder_sig)
            checkpoint_count += 1

            event = {
                "event": "checkpoint_created",
                "checkpoint_sequence_id": last_seq_id,
                "checkpoint_hash": cp_hash,
                "entries_in_range": len(entry_hashes),
                "newly_stored": stored,
                "partial": True,
            }
            print(json.dumps(event))

        logger.info("Created %d checkpoint(s).", checkpoint_count)
        return 0

    except Exception as exc:
        logger.error("Checkpoint creation failed: %s", exc)
        return 1
    finally:
        conn.close()


def _cmd_auto_checkpoint(args: argparse.Namespace) -> int:
    """Handle the ``auto-checkpoint`` subcommand (HARDEN-007).

    Runs a continuous daemon or one-shot evaluation of dual-trigger checkpointing.
    A checkpoint is triggered whenever:
    - N entries accumulate (default: 25) OR
    - T seconds elapse (default: 60s)

    Quantifies T=60s as the explicit upper bound on the maximum undetectable tampering
    window against an administrative adversary (A_DBA).

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code — 0 on success, 1 on error.
    """
    try:
        from db.cli.checkpoint_store import (
            create_dual_trigger_checkpoint,
            DEFAULT_MAX_ENTRIES,
            DEFAULT_MAX_SECONDS,
            MAX_UNDETECTABLE_TAMPERING_WINDOW_SECONDS,
        )
    except ImportError:
        from checkpoint_store import (  # type: ignore[no-redef]
            create_dual_trigger_checkpoint,
            DEFAULT_MAX_ENTRIES,
            DEFAULT_MAX_SECONDS,
            MAX_UNDETECTABLE_TAMPERING_WINDOW_SECONDS,
        )

    db_url = args.db_url or os.environ.get("DATABASE_URL", "")
    if not db_url:
        logger.error("No database URL provided. Use --db-url or set DATABASE_URL.")
        return 1

    max_entries = getattr(args, "max_entries", None) or DEFAULT_MAX_ENTRIES
    max_seconds = getattr(args, "max_seconds", None) or DEFAULT_MAX_SECONDS
    poll_interval = getattr(args, "poll_interval", 5.0)
    run_once = getattr(args, "run_once", False)
    sign_checkpoints = getattr(args, "sign", False)
    key_path = getattr(args, "key_path", None)
    anchor_checkpoints = getattr(args, "anchor", False)

    signer = None
    key_id = getattr(args, "key_id", "local:ed25519:v1")
    if sign_checkpoints or key_path:
        try:
            from db.cli.keygen import load_private_key, get_default_key_dir
            from db.cli.signer import LocalFileSigner
        except ImportError:
            from keygen import load_private_key, get_default_key_dir  # type: ignore[no-redef]
            from signer import LocalFileSigner  # type: ignore[no-redef]

        actual_key_path = key_path or os.path.join(get_default_key_dir(), "signing_key.pem")
        if not os.path.exists(actual_key_path):
            logger.error("Signing requested but private key not found at '%s'", actual_key_path)
            return 1
        priv_key = load_private_key(actual_key_path)
        signer = LocalFileSigner(private_key=priv_key, key_id=key_id)

    logger.info(
        "Auto-checkpoint service started: N=%d entries, T=%.1fs elapsed (Max Undetectable Tampering Window = %.1fs)",
        max_entries,
        max_seconds,
        max_seconds,
    )

    def _process_tick() -> dict | None:
        conn = get_connection(db_url)
        try:
            res = create_dual_trigger_checkpoint(
                conn,
                max_entries=max_entries,
                max_seconds=max_seconds,
                signer=signer,
                key_id=key_id,
            )
            if res is not None and anchor_checkpoints:
                try:
                    from db.cli.anchor_store import get_anchor_store
                    anchor_cfg = {"type": getattr(args, "anchor_type", "local")}
                    if anchor_cfg["type"] == "local":
                        anchor_cfg["path"] = getattr(args, "anchor_path", "./anchors")
                    anchor_store = get_anchor_store(anchor_cfg)
                    payload = json.dumps({
                        "checkpoint_id": res["checkpoint_id"],
                        "sequence_id": res["checkpoint_sequence_id"],
                        "checkpoint_hash": res["checkpoint_hash"],
                        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    })
                    ref = anchor_store.push(res["checkpoint_id"] or 0, payload)
                    res["anchor_reference"] = ref
                except Exception as a_exc:
                    logger.warning("Failed to anchor checkpoint: %s", a_exc)

            return res
        finally:
            conn.close()

    try:
        if run_once:
            result = _process_tick()
            if result:
                print(json.dumps(result))
                print(f"✅ Checkpoint created at sequence_id={result['checkpoint_sequence_id']} (Reason: {result['trigger_reason']})")
            else:
                print(json.dumps({
                    "event": "checkpoint_skipped",
                    "status": "threshold_not_reached",
                    "max_entries": max_entries,
                    "max_seconds": max_seconds,
                }))
                print(f"ℹ️ Checkpoint skipped: thresholds not reached (N={max_entries}, T={max_seconds}s).")
            return 0

        # Continuous daemon loop
        import signal
        running = True

        def _handle_signal(sig, frame):
            nonlocal running
            logger.info("Received termination signal, stopping auto-checkpoint daemon...")
            running = False

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

        while running:
            try:
                result = _process_tick()
                if result:
                    print(json.dumps(result))
                    logger.info("Checkpoint created at seq %d (%s)", result["checkpoint_sequence_id"], result["trigger_reason"])
            except Exception as loop_exc:
                logger.error("Error in auto-checkpoint evaluation: %s", loop_exc)

            for _ in range(int(poll_interval * 10)):
                if not running:
                    break
                time.sleep(0.1)

        logger.info("Auto-checkpoint daemon shut down cleanly.")
        return 0

    except KeyboardInterrupt:
        logger.info("Auto-checkpoint daemon interrupted by user.")
        return 0
    except Exception as exc:
        logger.error("Auto-checkpoint daemon failed: %s", exc)
        return 1


def _cmd_sign_checkpoint(args: argparse.Namespace) -> int:
    """Handle the ``sign-checkpoint`` subcommand (CRYPTO-002 integration).

    Signs an existing checkpoint in chain_checkpoints using the Ed25519
    private key.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code — 0 on success, 1 on error.
    """
    try:
        from db.cli.keygen import load_private_key, get_default_key_dir
        from db.cli.signer import sign_checkpoint
        from db.cli.checkpoint_store import get_checkpoint
    except ImportError:
        from keygen import load_private_key, get_default_key_dir  # type: ignore[no-redef]
        from signer import sign_checkpoint  # type: ignore[no-redef]
        from checkpoint_store import get_checkpoint  # type: ignore[no-redef]

    conn = get_connection(args.db_url)

    try:
        # Load private key
        key_path = args.key_path or os.path.join(
            get_default_key_dir(), "signing_key.pem"
        )
        logger.info("Loading signing key from %s", key_path)
        private_key = load_private_key(key_path)

        # Fetch checkpoint
        checkpoint = get_checkpoint(conn, args.checkpoint_id)
        if checkpoint is None:
            logger.error(
                "Checkpoint %d not found.", args.checkpoint_id
            )
            return 1

        # Sign
        signature = sign_checkpoint(private_key, checkpoint["checkpoint_hash"])
        key_id = getattr(args, "key_id", "local:ed25519:v1")
        logger.info(
            "Signed checkpoint %d with key_id='%s' (sig=%s…)",
            args.checkpoint_id,
            key_id,
            signature.hex()[:16],
        )

        # Update the signature and key_id in the database
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "UPDATE chain_checkpoints SET signature = %s, key_id = %s "
                    "WHERE checkpoint_id = %s",
                    (psycopg2.Binary(signature), key_id, args.checkpoint_id),
                )
            except Exception:
                conn.rollback()
                cur.execute(
                    "UPDATE chain_checkpoints SET signature = %s "
                    "WHERE checkpoint_id = %s",
                    (psycopg2.Binary(signature), args.checkpoint_id),
                )
        conn.commit()

        print(json.dumps({
            "event": "checkpoint_signed",
            "checkpoint_id": args.checkpoint_id,
            "checkpoint_hash": checkpoint["checkpoint_hash"],
            "key_id": key_id,
            "signature_hex": signature.hex(),
        }))
        return 0

    except FileNotFoundError:
        logger.error(
            "Signing key not found at %s.  Run keygen first.",
            key_path,  # noqa: F821
        )
        return 1
    except Exception as exc:
        logger.error("Signing failed: %s", exc)
        return 1
    finally:
        conn.close()


def _cmd_anchor(args: argparse.Namespace) -> int:
    """Handle the ``anchor`` subcommand (CRYPTO-003–005 integration).

    Pushes a signed checkpoint to an external anchor store.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code — 0 on success, 1 on error.
    """
    try:
        from db.cli.anchor_store import get_anchor_store
        from db.cli.checkpoint_store import get_checkpoint
        from db.cli.keygen import load_public_key, get_default_key_dir
        from db.cli.signer import verify_signature
    except ImportError:
        from anchor_store import get_anchor_store  # type: ignore[no-redef]
        from checkpoint_store import get_checkpoint  # type: ignore[no-redef]
        from keygen import load_public_key, get_default_key_dir  # type: ignore[no-redef]
        from signer import verify_signature  # type: ignore[no-redef]

    conn = get_connection(args.db_url)

    try:
        # Fetch checkpoint
        checkpoint = get_checkpoint(conn, args.checkpoint_id)
        if checkpoint is None:
            logger.error(
                "Checkpoint %d not found.", args.checkpoint_id
            )
            return 1

        # Verify the checkpoint is signed (not placeholder)
        sig = bytes(checkpoint["signature"])
        if sig == b"\x00" * 64:
            logger.error(
                "Checkpoint %d has not been signed yet.  "
                "Run sign-checkpoint first.",
                args.checkpoint_id,
            )
            return 1

        # Optionally verify signature before anchoring
        if args.verify_sig:
            pub_path = args.public_key_path or os.path.join(
                get_default_key_dir(), "public_key.pem"
            )
            pub_key = load_public_key(pub_path)
            if not verify_signature(
                pub_key, checkpoint["checkpoint_hash"], sig
            ):
                logger.error("Signature verification failed — aborting anchor.")
                return 1
            logger.info("Signature verified before anchoring.")

        # Build anchor store config
        config: dict[str, Any] = {"type": args.type}
        if args.type == "local":
            config["path"] = args.path or "./anchors"
        elif args.type == "github":
            config["repo"] = args.repo
            config["token"] = args.token or os.environ.get("GITHUB_TOKEN", "")
            config["branch"] = args.branch
            config["path_prefix"] = args.path_prefix

        store = get_anchor_store(config)

        # Build anchor payload
        payload = json.dumps({
            "checkpoint_id": checkpoint["checkpoint_id"],
            "sequence_id": checkpoint["sequence_id"],
            "checkpoint_hash": checkpoint["checkpoint_hash"],
            "signature_hex": sig.hex(),
            "created_at": str(checkpoint["created_at"]),
        })

        ref = store.push(checkpoint["checkpoint_id"], payload)
        logger.info("Anchored checkpoint %d → %s", args.checkpoint_id, ref)

        print(json.dumps({
            "event": "checkpoint_anchored",
            "checkpoint_id": args.checkpoint_id,
            "anchor_type": args.type,
            "reference": ref,
        }))
        return 0

    except Exception as exc:
        logger.error("Anchoring failed: %s", exc)
        return 1
    finally:
        conn.close()


def _cmd_backup(args: argparse.Namespace) -> int:
    """Handle the ``backup`` subcommand (VERIFY-007/008 + DB-017).

    Supports two actions:
    - ``dump``: Run pg_dump, compute SHA-256, and record in the backups table.
    - ``verify``: Re-hash a stored backup and compare against the stored hash.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code — 0 on success, 1 on failure.
    """
    try:
        from db.cli.backup import (
            dump_and_hash,
            export_backup_manifest,
            record_backup,
            verify_backup,
            verify_backup_manifest,
        )
    except ImportError:
        from backup import (  # type: ignore[no-redef]
            dump_and_hash,
            export_backup_manifest,
            record_backup,
            verify_backup,
            verify_backup_manifest,
        )

    if args.backup_action == "dump":
        db_url: str = args.db_url or os.environ.get("DATABASE_URL", "")
        if not db_url:
            logger.error(
                "No database URL provided.  Use --db-url or set DATABASE_URL."
            )
            return 1

        output_path: str = args.output
        checkpoint_id = getattr(args, "checkpoint_id", None)
        manifest_path = getattr(args, "manifest_path", None)

        try:
            logger.info("Starting backup dump to '%s' …", output_path)
            backup_hash = dump_and_hash(db_url, output_path, manifest_path=manifest_path)
            logger.info("Dump complete.  SHA-256: %s", backup_hash)

            # Record in the backups table
            conn = get_connection(db_url)
            try:
                backup_id = record_backup(
                    conn,
                    backup_hash=backup_hash,
                    file_reference=os.path.abspath(output_path),
                    chain_checkpoint_id=checkpoint_id,
                )
            finally:
                conn.close()

            payload = {
                "event": "backup_created",
                "backup_id": backup_id,
                "backup_hash": backup_hash,
                "file_reference": os.path.abspath(output_path),
                "chain_checkpoint_id": checkpoint_id,
            }
            if manifest_path is not None:
                payload["manifest_path"] = os.path.abspath(manifest_path)

            print(json.dumps(payload))
            return 0

        except FileNotFoundError as exc:
            logger.error("Backup failed: %s", exc)
            return 1
        except Exception as exc:
            logger.error("Backup failed: %s", exc)
            return 1

    elif args.backup_action == "verify":
        manifest_path = getattr(args, "manifest_path", None)
        backup_id = getattr(args, "backup_id", None)
        file_path = getattr(args, "file", None)

        if backup_id is None and (not file_path or not manifest_path):
            logger.error("Must provide either --backup-id or both --file and --manifest-path")
            return 1

        if backup_id is not None:
            conn = get_connection(args.db_url)
            try:
                is_valid = verify_backup(conn, backup_id, manifest_path=manifest_path)
                status = "VALID" if is_valid else "TAMPERED"
                res_payload = {
                    "event": "backup_verified",
                    "backup_id": backup_id,
                    "status": status,
                }
                if manifest_path:
                    res_payload["manifest_path"] = os.path.abspath(manifest_path)
                print(json.dumps(res_payload))
                if is_valid:
                    print(f"✅ Backup {backup_id} integrity verified{' (cross-verified with off-host manifest)' if manifest_path else ''}.")
                else:
                    print(f"❌ Backup {backup_id} integrity FAILED — hash mismatch or file modified.")
                return 0 if is_valid else 1

            except ValueError as exc:
                logger.error("Verification failed: %s", exc)
                return 1
            except FileNotFoundError as exc:
                logger.error("Backup file or manifest missing: %s", exc)
                return 1
            except Exception as exc:
                logger.error("Verification failed: %s", exc)
                return 1
            finally:
                conn.close()
        else:
            # Standalone off-host manifest verification without database connection
            try:
                is_valid = verify_backup_manifest(file_path, manifest_path)
                status = "VALID" if is_valid else "TAMPERED"
                print(json.dumps({
                    "event": "backup_manifest_verified",
                    "file": os.path.abspath(file_path),
                    "manifest_path": os.path.abspath(manifest_path),
                    "status": status,
                }))
                if is_valid:
                    print(f"✅ Backup file '{file_path}' verified against off-host manifest '{manifest_path}'.")
                else:
                    print(f"❌ Backup file '{file_path}' integrity FAILED against manifest '{manifest_path}'.")
                return 0 if is_valid else 1
            except Exception as exc:
                logger.error("Manifest verification failed: %s", exc)
                return 1

    else:
        logger.error("Unknown backup action: %s", args.backup_action)
        return 1


# ===================================================================
# Argument parser
# ===================================================================

def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser with all subcommands.

    Returns:
        Configured ``ArgumentParser`` instance.
    """
    parser = argparse.ArgumentParser(
        prog="argus-verifier",
        description=(
            "Argus Verification Engine — standalone tool for auditing "
            "the integrity of the tamper-evident hash chain."
        ),
    )

    # Global arguments
    parser.add_argument(
        "--db-url",
        default=None,
        help=(
            "PostgreSQL connection string "
            "(default: DATABASE_URL environment variable)"
        ),
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO)",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
        description="Available verification commands",
    )

    # ---- verify-chain ----
    p_verify = subparsers.add_parser(
        "verify-chain",
        help="Walk the audit log and verify hash chain integrity",
    )
    p_verify.add_argument(
        "--dry-run",
        action="store_true",
        help='Print "No entries found" on empty DB and exit',
    )
    p_verify.add_argument(
        "--start-seq",
        type=int,
        default=0,
        help="Starting sequence_id for verification (default: 0)",
    )
    p_verify.add_argument(
        "--page-size",
        type=int,
        default=500,
        help="Batch size for keyset pagination (default: 500)",
    )

    # VERIFY-006: parallel / sequential mode flags
    mode_group = p_verify.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--parallel",
        action="store_true",
        default=False,
        help=(
            "Verify segments in parallel using ProcessPoolExecutor, "
            "bounded by checkpoint boundaries (requires checkpoints to exist)."
        ),
    )
    mode_group.add_argument(
        "--sequential",
        action="store_true",
        default=False,
        help="Force sequential verification even when checkpoints exist (default).",
    )
    p_verify.add_argument(
        "--workers",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Maximum number of worker processes for --parallel mode. "
            "0 (default) uses os.cpu_count()."
        ),
    )

    # ---- create-checkpoint ----
    p_checkpoint = subparsers.add_parser(
        "create-checkpoint",
        help="Walk the chain and create checkpoints at regular intervals",
    )
    p_checkpoint.add_argument(
        "--checkpoint-interval",
        type=int,
        default=25,
        help="Create a checkpoint every N entries (default: 25)",
    )
    p_checkpoint.add_argument(
        "--page-size",
        type=int,
        default=500,
        help="Batch size for keyset pagination (default: 500)",
    )

    # ---- auto-checkpoint ----
    p_auto = subparsers.add_parser(
        "auto-checkpoint",
        help="Run dual-trigger checkpoint daemon (bounds tampering window T to 60s)",
    )
    p_auto.add_argument(
        "--db-url",
        default=None,
        help="PostgreSQL connection string (default: DATABASE_URL env var)",
    )
    p_auto.add_argument(
        "--max-entries",
        type=int,
        default=25,
        help="Threshold of uncheckpointed entries before firing (default: 25)",
    )
    p_auto.add_argument(
        "--max-seconds",
        type=float,
        default=60.0,
        help=(
            "Maximum elapsed seconds before firing checkpoint (default: 60.0). "
            "Quantifies the maximum undetectable tampering window against A_DBA."
        ),
    )
    p_auto.add_argument(
        "--poll-interval",
        type=float,
        default=5.0,
        help="Seconds between dual-trigger evaluation cycles (default: 5.0)",
    )
    p_auto.add_argument(
        "--run-once",
        action="store_true",
        help="Evaluate dual-trigger condition once and exit (for cron or batch runs)",
    )
    p_auto.add_argument(
        "--sign",
        action="store_true",
        help="Automatically sign created checkpoints using Ed25519 private key",
    )
    p_auto.add_argument(
        "--key-path",
        default=None,
        help="Path to Ed25519 private key PEM file for signing",
    )
    p_auto.add_argument(
        "--anchor",
        action="store_true",
        help="Automatically push created checkpoint to external anchor store",
    )
    p_auto.add_argument(
        "--anchor-type",
        choices=["local", "github"],
        default="local",
        help="External anchor store type (default: local)",
    )
    p_auto.add_argument(
        "--anchor-path",
        default="./anchors",
        help="Directory path for local anchor store (default: ./anchors)",
    )
    p_auto.add_argument(
        "--key-id",
        default="local:ed25519:v1",
        help="Key identifier string for key rotation tracking (default: local:ed25519:v1)",
    )

    # ---- sign-checkpoint ----
    p_sign = subparsers.add_parser(
        "sign-checkpoint",
        help="Sign a stored checkpoint with Ed25519",
    )
    p_sign.add_argument(
        "--checkpoint-id",
        type=int,
        required=True,
        help="ID of the checkpoint to sign",
    )
    p_sign.add_argument(
        "--key-path",
        default=None,
        help="Path to Ed25519 private key PEM (default: ~/.argus/signing_key.pem)",
    )
    p_sign.add_argument(
        "--key-id",
        default="local:ed25519:v1",
        help="Key identifier string for key rotation tracking (default: local:ed25519:v1)",
    )

    # ---- anchor ----
    p_anchor = subparsers.add_parser(
        "anchor",
        help="Push a signed checkpoint to an external anchor store",
    )
    p_anchor.add_argument(
        "--checkpoint-id",
        type=int,
        required=True,
        help="ID of the checkpoint to anchor",
    )
    p_anchor.add_argument(
        "--type",
        choices=["local", "github"],
        default="local",
        help="Anchor store type (default: local)",
    )
    p_anchor.add_argument(
        "--path",
        default=None,
        help="Base directory for local anchor store (default: ./anchors)",
    )
    p_anchor.add_argument(
        "--repo",
        default=None,
        help="GitHub repository (owner/repo) for GitHub anchor store",
    )
    p_anchor.add_argument(
        "--token",
        default=None,
        help="GitHub personal access token (default: GITHUB_TOKEN env var)",
    )
    p_anchor.add_argument(
        "--branch",
        default="main",
        help="GitHub branch for anchor store (default: main)",
    )
    p_anchor.add_argument(
        "--path-prefix",
        default="anchors",
        help="Path prefix in GitHub repo (default: anchors)",
    )
    p_anchor.add_argument(
        "--verify-sig",
        action="store_true",
        help="Verify checkpoint signature before anchoring",
    )
    p_anchor.add_argument(
        "--public-key-path",
        default=None,
        help="Path to Ed25519 public key PEM for signature verification",
    )

    # ---- backup ----
    p_backup = subparsers.add_parser(
        "backup",
        help="Dump database and verify backup integrity",
    )
    backup_sub = p_backup.add_subparsers(
        dest="backup_action",
        title="backup actions",
        description="Available backup actions",
    )

    # backup dump
    p_backup_dump = backup_sub.add_parser(
        "dump",
        help="Run pg_dump, compute SHA-256, and record in backups table",
    )
    p_backup_dump.add_argument(
        "--output",
        required=True,
        help="Output file path for the SQL dump",
    )
    p_backup_dump.add_argument(
        "--checkpoint-id",
        type=int,
        default=None,
        help="Optional checkpoint ID to associate with this backup",
    )
    p_backup_dump.add_argument(
        "--manifest-path",
        default=None,
        help="Optional path to export off-host backup verification manifest",
    )
    p_backup_dump.add_argument(
        "--db-url",
        default=None,
        help="PostgreSQL connection string (default: DATABASE_URL env var)",
    )

    # backup verify
    p_backup_verify = backup_sub.add_parser(
        "verify",
        help="Re-hash a stored backup and compare against stored hash or off-host manifest",
    )
    p_backup_verify.add_argument(
        "--db-url",
        default=None,
        help="PostgreSQL connection string (default: DATABASE_URL env var)",
    )
    p_backup_verify.add_argument(
        "--backup-id",
        type=int,
        default=None,
        help="ID of the backup record to verify (in database)",
    )
    p_backup_verify.add_argument(
        "--file",
        default=None,
        help="Path to backup file (for standalone off-host manifest verification)",
    )
    p_backup_verify.add_argument(
        "--manifest-path",
        default=None,
        help="Optional path to off-host manifest for external integrity verification",
    )

    return parser


# ===================================================================
# Entry point
# ===================================================================

def main() -> int:
    """Parse arguments and dispatch to the appropriate subcommand.

    Returns:
        Exit code — 0 for success, 1 for failure.
    """
    parser = build_parser()
    args = parser.parse_args()

    _configure_logging(args.log_level)

    if args.command is None:
        parser.print_help()
        return 0

    dispatch = {
        "verify-chain": _cmd_verify_chain,
        "create-checkpoint": _cmd_create_checkpoint,
        "auto-checkpoint": _cmd_auto_checkpoint,
        "sign-checkpoint": _cmd_sign_checkpoint,
        "anchor": _cmd_anchor,
        "backup": _cmd_backup,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
