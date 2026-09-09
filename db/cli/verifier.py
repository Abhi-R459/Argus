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
import hashlib
import json
import logging
import os
import sys
from typing import Any

import psycopg2
import psycopg2.extras

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
        logger.info(
            "Signed checkpoint %d (sig=%s…)",
            args.checkpoint_id,
            signature.hex()[:16],
        )

        # Update the signature in the database
        with conn.cursor() as cur:
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
        from db.cli.backup import dump_and_hash, record_backup, verify_backup
    except ImportError:
        from backup import dump_and_hash, record_backup, verify_backup  # type: ignore[no-redef]

    if args.backup_action == "dump":
        db_url: str = args.db_url or os.environ.get("DATABASE_URL", "")
        if not db_url:
            logger.error(
                "No database URL provided.  Use --db-url or set DATABASE_URL."
            )
            return 1

        output_path: str = args.output
        checkpoint_id = getattr(args, "checkpoint_id", None)

        try:
            logger.info("Starting backup dump to '%s' …", output_path)
            backup_hash = dump_and_hash(db_url, output_path)
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

            print(json.dumps({
                "event": "backup_created",
                "backup_id": backup_id,
                "backup_hash": backup_hash,
                "file_reference": os.path.abspath(output_path),
                "chain_checkpoint_id": checkpoint_id,
            }))
            return 0

        except FileNotFoundError as exc:
            logger.error("Backup failed: %s", exc)
            return 1
        except Exception as exc:
            logger.error("Backup failed: %s", exc)
            return 1

    elif args.backup_action == "verify":
        conn = get_connection(args.db_url)
        try:
            is_valid = verify_backup(conn, args.backup_id)
            status = "VALID" if is_valid else "TAMPERED"
            print(json.dumps({
                "event": "backup_verified",
                "backup_id": args.backup_id,
                "status": status,
            }))
            if is_valid:
                print(f"✅ Backup {args.backup_id} integrity verified.")
            else:
                print(f"❌ Backup {args.backup_id} integrity FAILED — file has been modified.")
            return 0 if is_valid else 1

        except ValueError as exc:
            logger.error("Verification failed: %s", exc)
            return 1
        except FileNotFoundError as exc:
            logger.error("Backup file missing: %s", exc)
            return 1
        except Exception as exc:
            logger.error("Verification failed: %s", exc)
            return 1
        finally:
            conn.close()

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

    # backup verify
    p_backup_verify = backup_sub.add_parser(
        "verify",
        help="Re-hash a stored backup and compare against stored hash",
    )
    p_backup_verify.add_argument(
        "--backup-id",
        type=int,
        required=True,
        help="ID of the backup record to verify",
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
