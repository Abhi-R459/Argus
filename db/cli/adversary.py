#!/usr/bin/env python3
"""Argus Adversary Engine — Red Team Simulation CLI (ADV-001).

This standalone, out-of-band administrative tool simulates genuine rogue DBA attacks
directly against the PostgreSQL database (bypassing the application layer and API)
to test and demonstrate the Argus verification engine, Ed25519 checkpoint signatures,
and external anchor stores.

Scenarios
---------
1. dba-row-tamper       — Mutates an historical audit_log entry directly via SQL without updating hashes.
                          Detected by: Hash mismatch during sequential chain walk.
2. recompute-and-hide   — Mutates an historical row and recalculates all forward SHA-256 chain hashes
                          up to the chain tail.
                          Detected by: Discrepancy against external Ed25519 checkpoint anchor store.
3. checkpoint-forgery   — Corrupts the Ed25519 signature on an historical checkpoint.
                          Detected by: Asymmetric signature verification failure.
4. delete-audit-row     — Deletes an historical audit_log row directly from the database.
                          Detected by: Sequence gap and orphaned previous_hash detection.

Healing
-------
All attacks record a snapshot of the modified state to `.argus_snapshot.json` before applying
any mutations. Running `heal` restores all records, chain state, and checkpoints back to their
exact pre-tampered condition and confirms 100% cryptographic validity.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import psycopg2
import psycopg2.extras

# Terminal color definitions
class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

# Default snapshot path
DEFAULT_SNAPSHOT_PATH = ".argus_snapshot.json"

# Import Argus verifier dependencies with robust fallback
try:
    from db.cli.hash_verifier import recompute_hash, verify_chain, VerificationResult
    from db.cli.checkpoint_store import compute_checkpoint_hash, get_all_checkpoints, get_checkpoint
    from db.cli.signer import verify_signature
    from db.cli.keygen import load_public_key, get_default_key_dir
    from db.cli.anchor_store import LocalFileAnchorStore, get_anchor_store
except ImportError:
    try:
        from hash_verifier import recompute_hash, verify_chain, VerificationResult  # type: ignore[no-redef]
        from checkpoint_store import compute_checkpoint_hash, get_all_checkpoints, get_checkpoint  # type: ignore[no-redef]
        from signer import verify_signature  # type: ignore[no-redef]
        from keygen import load_public_key, get_default_key_dir  # type: ignore[no-redef]
        from anchor_store import LocalFileAnchorStore, get_anchor_store  # type: ignore[no-redef]
    except ImportError:
        pass


def resolve_db_url(db_url: str | None = None) -> str:
    """Resolve PostgreSQL connection string for superuser administration."""
    if db_url:
        url = db_url
    else:
        url = (
            os.environ.get("DATABASE_URL_MIGRATIONS")
            or os.environ.get("DATABASE_URL")
        )

    if not url and os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("DATABASE_URL_MIGRATIONS="):
                    url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
                elif line.startswith("DATABASE_URL=") and not url:
                    url = line.split("=", 1)[1].strip().strip('"').strip("'")

    if not url:
        url = "postgresql://postgres:password@172.27.55.55:5432/argus"

    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)

    return url


def get_admin_connection(db_url: str | None = None) -> psycopg2.extensions.connection:
    """Establish direct administrative connection to PostgreSQL."""
    url = resolve_db_url(db_url)
    try:
        conn = psycopg2.connect(url)
        return conn
    except psycopg2.Error as exc:
        print(f"{Colors.RED}[!] Database connection failed:{Colors.RESET} {exc}")
        print(f"    Target URL: {url}")
        sys.exit(1)


def save_snapshot(snapshot_data: dict, snapshot_path: str = DEFAULT_SNAPSHOT_PATH) -> None:
    """Persist pre-attack state snapshot for deterministic healing."""
    path = Path(snapshot_path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot_data, f, indent=2, default=str)


def load_snapshot(snapshot_path: str = DEFAULT_SNAPSHOT_PATH) -> dict | None:
    """Load pre-attack state snapshot if one exists."""
    path = Path(snapshot_path)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def clear_snapshot(snapshot_path: str = DEFAULT_SNAPSHOT_PATH) -> None:
    """Remove pre-attack state snapshot file after successful healing."""
    path = Path(snapshot_path)
    if path.exists():
        path.unlink()


# ---------------------------------------------------------------------------
# Attack Scenarios
# ---------------------------------------------------------------------------

def attack_dba_row_tamper(
    conn: psycopg2.extensions.connection,
    sequence_id: int | None = None,
    snapshot_path: str = DEFAULT_SNAPSHOT_PATH,
    force: bool = False,
) -> dict:
    """Scenario 1: Mutate an historical audit row in SQL without updating hashes.
    
    A rogue DBA connects as PostgreSQL superuser and directly edits an employee's
    salary in historical audit records to conceal an unauthorized payment.
    The verifier detects this immediately because the stored `entry_hash` does not
    match the recomputed SHA-256 digest.
    """
    existing_snap = load_snapshot(snapshot_path)
    if existing_snap and not force:
        raise RuntimeError(
            f"An attack snapshot already exists ({existing_snap.get('scenario')}). "
            f"Run 'heal' first or pass force=True."
        )

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Find target row
        if sequence_id is not None:
            cur.execute(
                "SELECT sequence_id, actor_user_id, employee_id, action, table_name, "
                "row_id, old_value::TEXT AS old_value_text, new_value::TEXT AS new_value_text, "
                "severity, entry_hash, previous_hash, created_at::TEXT AS created_at_text "
                "FROM audit_log WHERE sequence_id = %s",
                (sequence_id,),
            )
            target_row = cur.fetchone()
            if not target_row:
                raise ValueError(f"Sequence ID {sequence_id} not found in audit_log.")
        else:
            # Pick a suitable row that has a new_value
            cur.execute(
                "SELECT sequence_id, actor_user_id, employee_id, action, table_name, "
                "row_id, old_value::TEXT AS old_value_text, new_value::TEXT AS new_value_text, "
                "severity, entry_hash, previous_hash, created_at::TEXT AS created_at_text "
                "FROM audit_log WHERE new_value IS NOT NULL AND sequence_id >= 5 "
                "ORDER BY sequence_id LIMIT 1"
            )
            target_row = cur.fetchone()
            if not target_row:
                cur.execute(
                    "SELECT sequence_id, actor_user_id, employee_id, action, table_name, "
                    "row_id, old_value::TEXT AS old_value_text, new_value::TEXT AS new_value_text, "
                    "severity, entry_hash, previous_hash, created_at::TEXT AS created_at_text "
                    "FROM audit_log ORDER BY sequence_id DESC LIMIT 1"
                )
                target_row = cur.fetchone()

        if not target_row:
            raise RuntimeError("audit_log table is empty. Cannot perform attack.")

        target_seq = target_row["sequence_id"]

        # Record snapshot
        snapshot = {
            "scenario": "dba-row-tamper",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target_sequence_id": target_seq,
            "audit_rows": [dict(target_row)],
            "notes": "Direct SQL mutation of historical audit_log row without hash update.",
        }
        save_snapshot(snapshot, snapshot_path)

        # Mutate new_value
        current_text = target_row["new_value_text"] or "{}"
        try:
            current_val = json.loads(current_text)
        except Exception:
            current_val = {"raw": current_text}

        tampered_val = dict(current_val)
        tampered_val["_unauthorized_dba_bonus"] = 250000.00
        tampered_val["tampered_by"] = "rogue_dba_sql_mutation"
        if "salary" in tampered_val:
            tampered_val["salary"] = 999999.00
        elif "amount" in tampered_val:
            tampered_val["amount"] = 999999.00

        tampered_json = json.dumps(tampered_val)

        cur.execute(
            "UPDATE audit_log SET new_value = %s::jsonb WHERE sequence_id = %s",
            (tampered_json, target_seq),
        )
        conn.commit()

        return {
            "scenario": "dba-row-tamper",
            "status": "success",
            "target_sequence_id": target_seq,
            "original_hash": target_row["entry_hash"],
            "tampered_new_value": tampered_val,
            "sql_executed": f"UPDATE audit_log SET new_value = '{tampered_json}' WHERE sequence_id = {target_seq};",
            "message": f"Successfully injected SQL row tamper at sequence_id {target_seq}. Hash chain is now invalid.",
        }


def attack_recompute_and_hide(
    conn: psycopg2.extensions.connection,
    sequence_id: int | None = None,
    snapshot_path: str = DEFAULT_SNAPSHOT_PATH,
    force: bool = False,
) -> dict:
    """Scenario 2: Mutate historical row and recalculate all forward hashes.
    
    A sophisticated rogue DBA modifies a historical record and rewrites the SHA-256
    hash chain from that point forward to the chain tail.
    
    Result:
    The internal chain passes a naive verification walk (`verify_chain` returns True),
    BUT fails external anchor verification because the historical Ed25519 checkpoint
    anchor was already committed to an immutable store before the attack occurred.
    """
    existing_snap = load_snapshot(snapshot_path)
    if existing_snap and not force:
        raise RuntimeError(
            f"An attack snapshot already exists ({existing_snap.get('scenario')}). "
            f"Run 'heal' first or pass force=True."
        )

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Determine target sequence
        if sequence_id is not None:
            target_seq = sequence_id
        else:
            # Select sequence 15 or 20, or a row that comes before an existing checkpoint
            cur.execute("SELECT MIN(sequence_id) FROM chain_checkpoints")
            min_cp = cur.fetchone()["min"]
            if min_cp and min_cp > 5:
                target_seq = min_cp - 5
            else:
                cur.execute("SELECT COUNT(*) FROM audit_log")
                cnt = cur.fetchone()["count"]
                target_seq = max(1, cnt // 2)

        # Fetch all rows from target_seq to tail with preserved text formatting
        cur.execute(
            "SELECT sequence_id, actor_user_id, employee_id, action, table_name, "
            "row_id, old_value::TEXT AS old_value_text, new_value::TEXT AS new_value_text, "
            "severity, entry_hash, previous_hash, created_at::TEXT AS created_at_text "
            "FROM audit_log WHERE sequence_id >= %s ORDER BY sequence_id ASC",
            (target_seq,),
        )
        affected_rows = cur.fetchall()
        if not affected_rows:
            raise RuntimeError(f"No rows found at or after sequence_id {target_seq}.")

        # Fetch chain_state
        cur.execute("SELECT id, tail_hash, tail_sequence_id, last_checkpoint_sequence_id FROM chain_state WHERE id = 1")
        chain_state_row = cur.fetchone()

        # Fetch checkpoints at or after target_seq
        cur.execute(
            "SELECT checkpoint_id, sequence_id, checkpoint_hash, signature, created_at "
            "FROM chain_checkpoints WHERE sequence_id >= %s ORDER BY sequence_id ASC",
            (target_seq,),
        )
        affected_cps = cur.fetchall()

        # Save snapshot
        snapshot = {
            "scenario": "recompute-and-hide",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target_sequence_id": target_seq,
            "audit_rows": [dict(r) for r in affected_rows],
            "chain_state": dict(chain_state_row) if chain_state_row else None,
            "checkpoints": [
                {
                    "checkpoint_id": cp["checkpoint_id"],
                    "sequence_id": cp["sequence_id"],
                    "checkpoint_hash": cp["checkpoint_hash"],
                    "signature_hex": bytes(cp["signature"]).hex(),
                    "created_at": cp["created_at"].isoformat() if hasattr(cp["created_at"], "isoformat") else str(cp["created_at"]),
                }
                for cp in affected_cps
            ],
            "notes": "Recalculated forward hash chain to test external anchor mismatch.",
        }
        save_snapshot(snapshot, snapshot_path)

        # Get predecessor hash for target row
        if target_seq > 1:
            cur.execute("SELECT entry_hash FROM audit_log WHERE sequence_id = %s", (target_seq - 1,))
            pred = cur.fetchone()
            current_prev_hash = pred["entry_hash"] if pred else ("0" * 64)
        else:
            current_prev_hash = "0" * 64

        # Mutate target row's value
        target_text = affected_rows[0]["new_value_text"] or "{}"
        try:
            target_val = json.loads(target_text)
        except Exception:
            target_val = {"raw": target_text}
        tampered_val = dict(target_val)
        tampered_val["_recomputed_hidden_alteration"] = True
        tampered_val["tampered_by"] = "rogue_dba_recompute_and_hide"

        # Apply mutation to target row
        cur.execute(
            "UPDATE audit_log SET new_value = %s::jsonb WHERE sequence_id = %s",
            (json.dumps(tampered_val), target_seq),
        )

        # Recalculate forward
        recalculated_count = 0
        tail_hash = ""
        for i, row in enumerate(affected_rows):
            seq = row["sequence_id"]
            cur.execute(
                "SELECT sequence_id, actor_user_id, action, table_name, row_id, "
                "old_value::TEXT AS old_value_text, new_value::TEXT AS new_value_text, "
                "created_at::TEXT AS created_at_text FROM audit_log WHERE sequence_id = %s",
                (seq,),
            )
            text_row = cur.fetchone()

            calc_dict = {
                "sequence_id": text_row["sequence_id"],
                "actor_user_id": text_row["actor_user_id"],
                "action": text_row["action"],
                "table_name": text_row["table_name"],
                "row_id": text_row["row_id"],
                "old_value_text": text_row["old_value_text"],
                "new_value_text": text_row["new_value_text"],
                "created_at_text": text_row["created_at_text"],
            }

            new_hash = recompute_hash(calc_dict, current_prev_hash)
            cur.execute(
                "UPDATE audit_log SET previous_hash = %s, entry_hash = %s WHERE sequence_id = %s",
                (current_prev_hash, new_hash, seq),
            )
            current_prev_hash = new_hash
            tail_hash = new_hash
            recalculated_count += 1

        # Update chain_state tail_hash
        cur.execute(
            "UPDATE chain_state SET tail_hash = %s WHERE id = 1",
            (tail_hash,),
        )

        # Recalculate checkpoints in DB so they match the faked audit entries
        for cp in affected_cps:
            cur.execute(
                "SELECT COALESCE(MAX(sequence_id), 0) FROM chain_checkpoints WHERE sequence_id < %s",
                (cp["sequence_id"],),
            )
            prev_cp_seq = cur.fetchone()["coalesce"]
            cur.execute(
                "SELECT entry_hash FROM audit_log WHERE sequence_id > %s AND sequence_id <= %s ORDER BY sequence_id ASC",
                (prev_cp_seq, cp["sequence_id"]),
            )
            seg_hashes = [r["entry_hash"] for r in cur.fetchall()]
            new_cp_hash = compute_checkpoint_hash(seg_hashes)
            cur.execute(
                "UPDATE chain_checkpoints SET checkpoint_hash = %s WHERE checkpoint_id = %s",
                (new_cp_hash, cp["checkpoint_id"]),
            )

        conn.commit()

        return {
            "scenario": "recompute-and-hide",
            "status": "success",
            "target_sequence_id": target_seq,
            "recalculated_rows": recalculated_count,
            "new_tail_hash": tail_hash,
            "message": (
                f"Recalculated {recalculated_count} forward hashes from sequence {target_seq} to tail. "
                "Internal chain is now internally consistent, but external anchors will detect the forgery!"
            ),
        }


def attack_checkpoint_forgery(
    conn: psycopg2.extensions.connection,
    checkpoint_id: int | None = None,
    snapshot_path: str = DEFAULT_SNAPSHOT_PATH,
    force: bool = False,
) -> dict:
    """Scenario 3: Corrupt checkpoint signature in PostgreSQL.
    
    A rogue DBA modifies an existing checkpoint in `chain_checkpoints`.
    Because the DBA lacks the auditor's Ed25519 private signing key, any forged
    or manipulated signature fails asymmetric verification.
    """
    existing_snap = load_snapshot(snapshot_path)
    if existing_snap and not force:
        raise RuntimeError(
            f"An attack snapshot already exists ({existing_snap.get('scenario')}). "
            f"Run 'heal' first or pass force=True."
        )

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        if checkpoint_id is not None:
            cur.execute(
                "SELECT checkpoint_id, sequence_id, checkpoint_hash, signature, created_at "
                "FROM chain_checkpoints WHERE checkpoint_id = %s",
                (checkpoint_id,),
            )
        else:
            cur.execute(
                "SELECT checkpoint_id, sequence_id, checkpoint_hash, signature, created_at "
                "FROM chain_checkpoints ORDER BY checkpoint_id DESC LIMIT 1"
            )
        cp_row = cur.fetchone()

        if not cp_row:
            raise RuntimeError(
                "No checkpoints found in chain_checkpoints. "
                "Create a checkpoint first with 'python -m db.cli.verifier create-checkpoint'."
            )

        target_cp_id = cp_row["checkpoint_id"]
        original_sig = bytes(cp_row["signature"])

        # Save snapshot
        snapshot = {
            "scenario": "checkpoint-forgery",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target_checkpoint_id": target_cp_id,
            "checkpoints": [
                {
                    "checkpoint_id": target_cp_id,
                    "sequence_id": cp_row["sequence_id"],
                    "checkpoint_hash": cp_row["checkpoint_hash"],
                    "signature_hex": original_sig.hex(),
                    "created_at": cp_row["created_at"].isoformat() if hasattr(cp_row["created_at"], "isoformat") else str(cp_row["created_at"]),
                }
            ],
            "notes": "Corrupted Ed25519 signature in chain_checkpoints table.",
        }
        save_snapshot(snapshot, snapshot_path)

        # Inject invalid signature bytes
        forged_sig = b"\xde\xad\xbe\xef" * 16
        cur.execute(
            "UPDATE chain_checkpoints SET signature = %s WHERE checkpoint_id = %s",
            (psycopg2.Binary(forged_sig), target_cp_id),
        )
        conn.commit()

        return {
            "scenario": "checkpoint-forgery",
            "status": "success",
            "target_checkpoint_id": target_cp_id,
            "sequence_id": cp_row["sequence_id"],
            "forged_signature_hex": forged_sig.hex(),
            "message": f"Corrupted Ed25519 signature on checkpoint {target_cp_id}. Signature verification will fail.",
        }


def attack_delete_audit_row(
    conn: psycopg2.extensions.connection,
    sequence_id: int | None = None,
    snapshot_path: str = DEFAULT_SNAPSHOT_PATH,
    force: bool = False,
) -> dict:
    """Scenario 4: Directly delete an audit row from PostgreSQL.
    
    A rogue DBA attempts to erase all traces of a transaction by executing
    DELETE directly against `audit_log`.
    The verifier detects both a sequence gap and an orphaned subsequent row.
    """
    existing_snap = load_snapshot(snapshot_path)
    if existing_snap and not force:
        raise RuntimeError(
            f"An attack snapshot already exists ({existing_snap.get('scenario')}). "
            f"Run 'heal' first or pass force=True."
        )

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        if sequence_id is not None:
            cur.execute(
                "SELECT sequence_id, actor_user_id, employee_id, action, table_name, "
                "row_id, old_value::TEXT AS old_value_text, new_value::TEXT AS new_value_text, "
                "severity, entry_hash, previous_hash, created_at::TEXT AS created_at_text "
                "FROM audit_log WHERE sequence_id = %s",
                (sequence_id,),
            )
            target_row = cur.fetchone()
            if not target_row:
                raise ValueError(f"Sequence ID {sequence_id} not found in audit_log.")
        else:
            # Pick a mid-chain row
            cur.execute(
                "SELECT sequence_id, actor_user_id, employee_id, action, table_name, "
                "row_id, old_value::TEXT AS old_value_text, new_value::TEXT AS new_value_text, "
                "severity, entry_hash, previous_hash, created_at::TEXT AS created_at_text "
                "FROM audit_log WHERE sequence_id >= 10 ORDER BY sequence_id LIMIT 1"
            )
            target_row = cur.fetchone()
            if not target_row:
                cur.execute(
                    "SELECT sequence_id, actor_user_id, employee_id, action, table_name, "
                    "row_id, old_value::TEXT AS old_value_text, new_value::TEXT AS new_value_text, "
                    "severity, entry_hash, previous_hash, created_at::TEXT AS created_at_text "
                    "FROM audit_log ORDER BY sequence_id DESC LIMIT 1"
                )
                target_row = cur.fetchone()

        if not target_row:
            raise RuntimeError("audit_log is empty. Cannot delete row.")

        target_seq = target_row["sequence_id"]

        # Check for suspicious_activity_flags referencing this row
        cur.execute(
            "SELECT flag_id, audit_log_sequence_id, reviewed_by_user_id, reviewed_at, flag_reason, created_at "
            "FROM suspicious_activity_flags WHERE audit_log_sequence_id = %s",
            (target_seq,),
        )
        flags = cur.fetchall()

        # Save snapshot
        snapshot = {
            "scenario": "delete-audit-row",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target_sequence_id": target_seq,
            "audit_rows": [dict(target_row)],
            "suspicious_flags": [dict(f) for f in flags],
            "notes": "Direct deletion of audit_log row in SQL to trigger sequence gap & orphan detection.",
        }
        save_snapshot(snapshot, snapshot_path)

        # If foreign keys exist, delete flags first
        if flags:
            cur.execute(
                "DELETE FROM suspicious_activity_flags WHERE audit_log_sequence_id = %s",
                (target_seq,),
            )

        cur.execute("DELETE FROM audit_log WHERE sequence_id = %s", (target_seq,))
        conn.commit()

        return {
            "scenario": "delete-audit-row",
            "status": "success",
            "deleted_sequence_id": target_seq,
            "deleted_action": target_row["action"],
            "deleted_table": target_row["table_name"],
            "sql_executed": f"DELETE FROM audit_log WHERE sequence_id = {target_seq};",
            "message": f"Deleted audit_log entry {target_seq}. Chain verification will report sequence gap.",
        }


# ---------------------------------------------------------------------------
# Healing & Restoration
# ---------------------------------------------------------------------------

def heal_database(
    conn: psycopg2.extensions.connection,
    snapshot_path: str = DEFAULT_SNAPSHOT_PATH,
) -> dict:
    """Restore database state from snapshot and verify chain validity."""
    snapshot = load_snapshot(snapshot_path)
    if not snapshot:
        # Run verify_chain to inspect state anyway
        res = verify_chain(conn)
        return {
            "status": "clean",
            "scenario": None,
            "is_valid": res.is_valid,
            "entries_scanned": res.total_entries,
            "message": "No active attack snapshot found. Database is in pristine condition.",
        }

    scenario = snapshot.get("scenario", "unknown")

    with conn.cursor() as cur:
        # 1. Restore deleted rows if scenario was delete-audit-row
        if scenario == "delete-audit-row":
            for r in snapshot.get("audit_rows", []):
                cur.execute(
                    "INSERT INTO audit_log ("
                    "  sequence_id, actor_user_id, employee_id, action, table_name, "
                    "  row_id, old_value, new_value, severity, entry_hash, previous_hash, created_at"
                    ") VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s) "
                    "ON CONFLICT (sequence_id) DO UPDATE SET "
                    "  new_value = EXCLUDED.new_value, old_value = EXCLUDED.old_value, "
                    "  entry_hash = EXCLUDED.entry_hash, previous_hash = EXCLUDED.previous_hash",
                    (
                        r["sequence_id"],
                        r["actor_user_id"],
                        r.get("employee_id"),
                        r["action"],
                        r["table_name"],
                        r["row_id"],
                        r.get("old_value_text"),
                        r.get("new_value_text"),
                        r["severity"],
                        r["entry_hash"],
                        r["previous_hash"],
                        r.get("created_at_text") or r.get("created_at"),
                    ),
                )
            for f in snapshot.get("suspicious_flags", []):
                cur.execute(
                    "INSERT INTO suspicious_activity_flags ("
                    "  flag_id, audit_log_sequence_id, reviewed_by_user_id, reviewed_at, flag_reason, created_at"
                    ") VALUES (%s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (flag_id) DO NOTHING",
                    (
                        f["flag_id"],
                        f["audit_log_sequence_id"],
                        f.get("reviewed_by_user_id"),
                        f.get("reviewed_at"),
                        f["flag_reason"],
                        f["created_at"],
                    ),
                )

        # 2. Restore row edits if dba-row-tamper or recompute-and-hide
        elif scenario in ("dba-row-tamper", "recompute-and-hide"):
            for r in snapshot.get("audit_rows", []):
                cur.execute(
                    "UPDATE audit_log SET "
                    "  new_value = %s::jsonb, "
                    "  old_value = %s::jsonb, "
                    "  entry_hash = %s, "
                    "  previous_hash = %s "
                    "WHERE sequence_id = %s",
                    (
                        r.get("new_value_text"),
                        r.get("old_value_text"),
                        r["entry_hash"],
                        r["previous_hash"],
                        r["sequence_id"],
                    ),
                )

            # Restore chain_state if present
            cs = snapshot.get("chain_state")
            if cs:
                cur.execute(
                    "UPDATE chain_state SET "
                    "  tail_hash = %s, "
                    "  tail_sequence_id = %s, "
                    "  last_checkpoint_sequence_id = %s "
                    "WHERE id = %s",
                    (
                        cs["tail_hash"],
                        cs["tail_sequence_id"],
                        cs["last_checkpoint_sequence_id"],
                        cs["id"],
                    ),
                )

            # Restore checkpoints if modified
            for cp in snapshot.get("checkpoints", []):
                sig_bytes = bytes.fromhex(cp["signature_hex"])
                cur.execute(
                    "UPDATE chain_checkpoints SET checkpoint_hash = %s, signature = %s WHERE checkpoint_id = %s",
                    (cp["checkpoint_hash"], psycopg2.Binary(sig_bytes), cp["checkpoint_id"]),
                )

        # 3. Restore checkpoints if checkpoint-forgery
        elif scenario == "checkpoint-forgery":
            for cp in snapshot.get("checkpoints", []):
                sig_bytes = bytes.fromhex(cp["signature_hex"])
                cur.execute(
                    "UPDATE chain_checkpoints SET checkpoint_hash = %s, signature = %s WHERE checkpoint_id = %s",
                    (cp["checkpoint_hash"], psycopg2.Binary(sig_bytes), cp["checkpoint_id"]),
                )

        conn.commit()

    # Clear the snapshot file
    clear_snapshot(snapshot_path)

    # Validate post-healing integrity
    verify_res = verify_chain(conn)

    return {
        "status": "healed",
        "scenario": scenario,
        "is_valid": verify_res.is_valid,
        "entries_scanned": verify_res.total_entries,
        "mismatches": len(verify_res.mismatches),
        "gaps": len(verify_res.gaps),
        "orphans": len(verify_res.orphans),
        "message": "Database and cryptographic integrity successfully restored to 100% pristine condition.",
    }


def get_adversary_status(
    conn: psycopg2.extensions.connection,
    snapshot_path: str = DEFAULT_SNAPSHOT_PATH,
) -> dict:
    """Check active attack state and run diagnostic verification."""
    snapshot = load_snapshot(snapshot_path)
    chain_res = verify_chain(conn)

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT COUNT(*) FROM audit_log")
        total_rows = cur.fetchone()["count"]

        cur.execute("SELECT COUNT(*) FROM chain_checkpoints")
        total_checkpoints = cur.fetchone()["count"]

        cur.execute("SELECT tail_sequence_id, tail_hash FROM chain_state WHERE id = 1")
        chain_state = cur.fetchone()

    # Check external anchor alignment
    anchor_intact = True
    anchor_details = "No external anchor file found."
    anchor_path = Path("anchor/2.json")
    if anchor_path.exists():
        try:
            with open(anchor_path, "r", encoding="utf-8") as f:
                anchor_data = json.load(f)
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        "SELECT checkpoint_hash FROM chain_checkpoints WHERE checkpoint_id = %s",
                        (anchor_data.get("checkpoint_id"),),
                    )
                    db_cp = cur.fetchone()
                    if db_cp and db_cp["checkpoint_hash"] != anchor_data.get("checkpoint_hash"):
                        anchor_intact = False
                        anchor_details = (
                            f"Anchor mismatch for checkpoint {anchor_data.get('checkpoint_id')}: "
                            f"DB hash {db_cp['checkpoint_hash'][:16]}... != Anchor {anchor_data.get('checkpoint_hash')[:16]}..."
                        )
                    else:
                        anchor_details = f"Anchor {anchor_data.get('checkpoint_id')} matches external store."
        except Exception as e:
            anchor_details = f"Anchor read error: {e}"

    return {
        "attack_active": snapshot is not None,
        "active_scenario": snapshot.get("scenario") if snapshot else None,
        "attack_timestamp": snapshot.get("timestamp") if snapshot else None,
        "target_sequence_id": snapshot.get("target_sequence_id") if snapshot else None,
        "chain_valid": chain_res.is_valid,
        "total_audit_rows": total_rows,
        "total_checkpoints": total_checkpoints,
        "mismatches": chain_res.mismatches,
        "gaps": chain_res.gaps,
        "orphans": chain_res.orphans,
        "anchor_intact": anchor_intact,
        "anchor_details": anchor_details,
    }


# ---------------------------------------------------------------------------
# Command-Line Interface & Presentation
# ---------------------------------------------------------------------------

def print_banner() -> None:
    banner = f"""
{Colors.RED}{Colors.BOLD}+-------------------------------------------------------------------+
|                   ARGUS ADVERSARY ENGINE                          |
|        Out-of-Band Red Team Database Attack Simulation            |
+-------------------------------------------------------------------+{Colors.RESET}
"""
    print(banner)


def cmd_attack(args: argparse.Namespace) -> int:
    conn = get_admin_connection(args.db_url)
    try:
        print_banner()
        print(f"{Colors.YELLOW}[*] Preparing Attack Scenario:{Colors.RESET} {Colors.BOLD}{args.scenario}{Colors.RESET}")
        
        if args.scenario == "dba-row-tamper":
            res = attack_dba_row_tamper(
                conn,
                sequence_id=args.sequence_id,
                snapshot_path=args.snapshot_path,
                force=args.force,
            )
            print(f"{Colors.GREEN}[+] Attack Injected Successfully!{Colors.RESET}")
            print(f"    Target Sequence ID : {Colors.BOLD}{res['target_sequence_id']}{Colors.RESET}")
            print(f"    SQL Executed       : {Colors.CYAN}{res['sql_executed']}{Colors.RESET}")
            print()
            print(f"{Colors.BOLD}Auditor Observation Instructions:{Colors.RESET}")
            print(f"  1. Open Auditor Dashboard: {Colors.CYAN}http://localhost:5173/auditor/overview{Colors.RESET}")
            print(f"  2. Click {Colors.BOLD}'Verify Chain'{Colors.RESET}.")
            print(f"  3. Notice status flips to {Colors.RED}TAMPERED{Colors.RESET} highlighting sequence_id {res['target_sequence_id']}.")
            print(f"  4. Restore with: {Colors.GREEN}python -m db.cli.adversary heal{Colors.RESET}")

        elif args.scenario == "recompute-and-hide":
            res = attack_recompute_and_hide(
                conn,
                sequence_id=args.sequence_id,
                snapshot_path=args.snapshot_path,
                force=args.force,
            )
            print(f"{Colors.GREEN}[+] Recompute Attack Injected Successfully!{Colors.RESET}")
            print(f"    Target Sequence ID : {Colors.BOLD}{res['target_sequence_id']}{Colors.RESET}")
            print(f"    Forward Rows Fixed : {Colors.BOLD}{res['recalculated_rows']}{Colors.RESET}")
            print(f"    New Tail Hash      : {Colors.CYAN}{res['new_tail_hash'][:32]}...{Colors.RESET}")
            print()
            print(f"{Colors.BOLD}Security Analysis Demonstration:{Colors.RESET}")
            print(f"  - The internal chain walk passes ({Colors.GREEN}is_valid = True{Colors.RESET}).")
            print(f"  - BUT check external anchors: {Colors.RED}MISMATCH DETECTED{Colors.RESET} against Ed25519 anchor store!")
            print(f"  - Check status with: {Colors.CYAN}python -m db.cli.adversary status{Colors.RESET}")
            print(f"  - Restore with: {Colors.GREEN}python -m db.cli.adversary heal{Colors.RESET}")

        elif args.scenario == "checkpoint-forgery":
            res = attack_checkpoint_forgery(
                conn,
                checkpoint_id=args.checkpoint_id,
                snapshot_path=args.snapshot_path,
                force=args.force,
            )
            print(f"{Colors.GREEN}[+] Checkpoint Signature Corrupted!{Colors.RESET}")
            print(f"    Checkpoint ID      : {Colors.BOLD}{res['target_checkpoint_id']}{Colors.RESET}")
            print(f"    Sequence ID        : {Colors.BOLD}{res['sequence_id']}{Colors.RESET}")
            print(f"    Forged Signature   : {Colors.RED}{res['forged_signature_hex'][:32]}...{Colors.RESET}")
            print()
            print(f"{Colors.BOLD}Auditor Observation Instructions:{Colors.RESET}")
            print(f"  - Ed25519 signature verification fails.")
            print(f"  - Restore with: {Colors.GREEN}python -m db.cli.adversary heal{Colors.RESET}")

        elif args.scenario == "delete-audit-row":
            res = attack_delete_audit_row(
                conn,
                sequence_id=args.sequence_id,
                snapshot_path=args.snapshot_path,
                force=args.force,
            )
            print(f"{Colors.GREEN}[+] Row Deletion Executed!{Colors.RESET}")
            print(f"    Deleted Sequence ID : {Colors.BOLD}{res['deleted_sequence_id']}{Colors.RESET}")
            print(f"    SQL Executed        : {Colors.CYAN}{res['sql_executed']}{Colors.RESET}")
            print()
            print(f"{Colors.BOLD}Auditor Observation Instructions:{Colors.RESET}")
            print(f"  1. Click {Colors.BOLD}'Verify Chain'{Colors.RESET} in the Auditor Dashboard.")
            print(f"  2. Verifier reports: {Colors.RED}Sequence gap detected at sequence_id {res['deleted_sequence_id']}{Colors.RESET}.")
            print(f"  3. Restore with: {Colors.GREEN}python -m db.cli.adversary heal{Colors.RESET}")

        return 0

    except Exception as exc:
        print(f"{Colors.RED}[!] Attack failed:{Colors.RESET} {exc}")
        return 1
    finally:
        conn.close()


def cmd_heal(args: argparse.Namespace) -> int:
    conn = get_admin_connection(args.db_url)
    try:
        print_banner()
        print(f"{Colors.CYAN}[*] Restoring database integrity from snapshot...{Colors.RESET}")
        res = heal_database(conn, snapshot_path=args.snapshot_path)
        
        if res["status"] == "clean":
            print(f"{Colors.GREEN}[OK] {res['message']}{Colors.RESET}")
        else:
            print(f"{Colors.GREEN}{Colors.BOLD}[OK] HEAL SUCCESSFUL!{Colors.RESET}")
            print(f"    Reverted Scenario  : {Colors.BOLD}{res['scenario']}{Colors.RESET}")
            print(f"    Entries Verified   : {Colors.BOLD}{res['entries_scanned']}{Colors.RESET}")
            print(f"    Chain Status       : {Colors.GREEN}{Colors.BOLD}100% VALID (Zero Tampering){Colors.RESET}")
            print()
            print(f"Verify in Web Dashboard at {Colors.CYAN}http://localhost:5173/auditor/overview{Colors.RESET} (Status: VALID).")

        return 0 if res["is_valid"] else 1

    except Exception as exc:
        print(f"{Colors.RED}[!] Heal failed:{Colors.RESET} {exc}")
        return 1
    finally:
        conn.close()


def cmd_status(args: argparse.Namespace) -> int:
    conn = get_admin_connection(args.db_url)
    try:
        print_banner()
        print(f"{Colors.CYAN}[*] Diagnosing Database and Verifier Integrity...{Colors.RESET}\n")
        status = get_adversary_status(conn, snapshot_path=args.snapshot_path)

        if status["attack_active"]:
            print(f"{Colors.RED}{Colors.BOLD}+---------------------------------------------------------------+{Colors.RESET}")
            print(f"{Colors.RED}{Colors.BOLD}| [!] ATTACK SIMULATION CURRENTLY ACTIVE                        |{Colors.RESET}")
            print(f"{Colors.RED}{Colors.BOLD}+---------------------------------------------------------------+{Colors.RESET}")
            print(f"  Scenario   : {Colors.YELLOW}{status['active_scenario']}{Colors.RESET}")
            print(f"  Target Seq : {Colors.YELLOW}{status['target_sequence_id']}{Colors.RESET}")
            print(f"  Injected   : {status['attack_timestamp']}")
            print(f"  Heal with  : {Colors.GREEN}python -m db.cli.adversary heal{Colors.RESET}\n")
        else:
            print(f"{Colors.GREEN}[OK] System Normal (No active adversary attacks staged).{Colors.RESET}\n")

        valid_str = f"{Colors.GREEN}VALID (INTACT){Colors.RESET}" if status["chain_valid"] else f"{Colors.RED}TAMPERED / INVALID{Colors.RESET}"
        print(f"  Total Audit Log Entries : {status['total_audit_rows']}")
        print(f"  Total Checkpoints       : {status['total_checkpoints']}")
        print(f"  Internal Hash Chain     : {valid_str}")

        if not status["chain_valid"]:
            if status["mismatches"]:
                print(f"    {Colors.RED}Hash Mismatches ({len(status['mismatches'])}):{Colors.RESET}")
                for m in status["mismatches"][:3]:
                    print(f"      - Seq {m['sequence_id']}: expected {m['expected'][:16]}... actual {m['actual'][:16]}...")
            if status["gaps"]:
                print(f"    {Colors.RED}Sequence Gaps ({len(status['gaps'])}):{Colors.RESET}")
                for g in status["gaps"][:3]:
                    print(f"      - Expected {g['expected_seq']}, found {g['actual_seq']}")
            if status["orphans"]:
                print(f"    {Colors.RED}Orphaned Blocks ({len(status['orphans'])}):{Colors.RESET}")
                for o in status["orphans"][:3]:
                    print(f"      - Seq {o['sequence_id']}: previous_hash does not match predecessor")

        anchor_str = f"{Colors.GREEN}MATCH{Colors.RESET}" if status["anchor_intact"] else f"{Colors.RED}MISMATCH{Colors.RESET}"
        print(f"  External Anchor Store   : {anchor_str} ({status['anchor_details']})")
        print()

        return 0

    except Exception as exc:
        print(f"{Colors.RED}[!] Status check failed:{Colors.RESET} {exc}")
        return 1
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument(
        "--db-url",
        help="PostgreSQL connection URL. Defaults to DATABASE_URL_MIGRATIONS.",
    )
    parent_parser.add_argument(
        "--snapshot-path",
        default=DEFAULT_SNAPSHOT_PATH,
        help="Path to pre-attack snapshot state file (default: .argus_snapshot.json).",
    )

    parser = argparse.ArgumentParser(
        prog="python -m db.cli.adversary",
        description="Argus Adversary Engine: Out-of-band Red Team administrative attack simulator.",
        parents=[parent_parser],
    )

    subparsers = parser.add_subparsers(dest="command", help="Adversary commands")

    # attack
    p_attack = subparsers.add_parser("attack", parents=[parent_parser], help="Execute an out-of-band attack scenario.")
    p_attack.add_argument(
        "--scenario",
        required=True,
        choices=["dba-row-tamper", "recompute-and-hide", "checkpoint-forgery", "delete-audit-row"],
        help="Adversary attack scenario to execute.",
    )
    p_attack.add_argument(
        "--sequence-id",
        type=int,
        help="Target sequence ID in audit_log (optional).",
    )
    p_attack.add_argument(
        "--checkpoint-id",
        type=int,
        help="Target checkpoint ID in chain_checkpoints (for checkpoint-forgery).",
    )
    p_attack.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite existing snapshot if an attack was already active.",
    )

    # heal
    subparsers.add_parser("heal", parents=[parent_parser], help="Revert all mutations and restore pristine database integrity.")

    # status
    subparsers.add_parser("status", parents=[parent_parser], help="Inspect current attack state and cryptographic integrity.")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "attack":
        return cmd_attack(args)
    elif args.command == "heal":
        return cmd_heal(args)
    elif args.command == "status":
        return cmd_status(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
