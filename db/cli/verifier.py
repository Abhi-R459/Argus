#!/usr/bin/env python3
"""Argus Verification Engine CLI.

VERIFY-001: CLI skeleton with argparse subcommands.
VERIFY-004: Checkpoint creation with configurable interval.

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

def _cmd_verify_chain(args: argparse.Namespace) -> int:
    """Handle the ``verify-chain`` subcommand.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code — 0 for clean chain, 1 for anomalies detected.
    """
    # Lazy imports so the CLI skeleton loads quickly and --help is instant.
    try:
        from db.cli.hash_verifier import verify_chain, VerificationResult
    except ImportError:
        from hash_verifier import verify_chain, VerificationResult  # type: ignore[no-redef]

    conn = get_connection(args.db_url)
    try:
        # Dry-run: just check if there are any entries
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

        logger.info("Starting chain verification …")
        result: VerificationResult = verify_chain(
            conn,
            start_seq=args.start_seq,
            page_size=args.page_size,
        )

        # Print summary
        print(f"\n{'='*60}")
        print("ARGUS CHAIN VERIFICATION REPORT")
        print(f"{'='*60}")
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
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
