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
2. recompute-and-hide   — Replaces a business value, then recalculates all forward SHA-256 chain hashes
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
from decimal import Decimal
import hashlib
import json
import os
import secrets
from pathlib import Path
import sys
from typing import Any, Optional
from urllib.parse import quote

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
    """Resolve a configured database URL without falling back to credentials."""
    try:
        from db.cli.db_url import resolve_db_url as resolve
    except ImportError:
        from db_url import resolve_db_url as resolve  # type: ignore[no-redef]
    return resolve(db_url)

def get_admin_connection(db_url: str | None = None) -> psycopg2.extensions.connection | None:
    """Establish direct administrative connection to PostgreSQL."""
    try:
        url = resolve_db_url(db_url)
        conn = psycopg2.connect(url)
        return conn
    except ValueError as exc:
        print(f"{Colors.RED}[!] Database configuration required: {exc}{Colors.RESET}")
        return None
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


def plan_business_value_replacement(cur: Any, audit_row: dict) -> tuple[dict, dict, dict]:
    """Prepare a real source-row mutation and matching audit payload change.

    Only the demo's supported business tables/columns are mutable. The caller
    snapshots the returned source value before applying the SQL update.
    """
    table_name = audit_row["table_name"]
    row_id = int(audit_row["row_id"])
    payload_text = audit_row.get("new_value_text") or "{}"
    try:
        payload = json.loads(payload_text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Sequence {audit_row['sequence_id']} has an unreadable audit payload.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Sequence {audit_row['sequence_id']} does not contain a record payload.")

    if table_name == "salary_history" and audit_row["action"] != "DELETE":
        cur.execute(
            "SELECT amount AS amount FROM salary_history WHERE salary_history_id = %s FOR UPDATE",
            (row_id,),
        )
        source = cur.fetchone()
        if not source:
            raise RuntimeError(f"Salary record {row_id} no longer exists in salary_history.")
        original = Decimal(str(source["amount"]))
        replacement = (original * Decimal("1.50")).quantize(Decimal("0.01"))
        if replacement == original:
            replacement += Decimal("1.00")
        payload["amount"] = float(replacement)
        change = {
            "table_name": "salary_history",
            "row_id": row_id,
            "column": "amount",
            "before_value": str(original),
            "after_value": str(replacement),
        }
    elif table_name == "employees" and audit_row["action"] != "DELETE":
        cur.execute(
            "SELECT is_active AS is_active FROM employees WHERE employee_id = %s FOR UPDATE",
            (row_id,),
        )
        source = cur.fetchone()
        if not source:
            raise RuntimeError(f"Employee {row_id} no longer exists in employees.")
        cur.execute(
            "SELECT MAX(sequence_id) FROM audit_log WHERE table_name = 'employees' AND row_id = %s",
            (row_id,),
        )
        latest_sequence = cur.fetchone()["max"]
        if latest_sequence != audit_row["sequence_id"]:
            raise RuntimeError(
                f"Employee event #{audit_row['sequence_id']} is historical; choose the latest employee event "
                "or a salary_history event so the live row and event describe the same value."
            )
        original = bool(source["is_active"])
        replacement = not original
        payload["is_active"] = replacement
        change = {
            "table_name": "employees",
            "row_id": row_id,
            "column": "is_active",
            "before_value": original,
            "after_value": replacement,
        }
    else:
        raise RuntimeError(
            f"Sequence {audit_row['sequence_id']} is not a supported live salary or employee event. "
            "Choose a salary_history record or the latest employees event."
        )

    return payload, change, {"table_name": table_name, "row_id": row_id, "column": change["column"], "value": change["before_value"]}


def apply_business_value_replacement(cur: Any, change: dict, value: Any) -> None:
    """Apply an allow-listed source-row change while suppressing audit triggers."""
    # This is the adversary's privileged, out-of-band path: session_replication_role
    # suppresses user triggers so the attack does not generate a clean new audit row.
    cur.execute("SET LOCAL session_replication_role = replica")
    if change["table_name"] == "salary_history" and change["column"] == "amount":
        cur.execute(
            "UPDATE salary_history SET amount = %s WHERE salary_history_id = %s",
            (value, change["row_id"]),
        )
    elif change["table_name"] == "employees" and change["column"] == "is_active":
        cur.execute(
            "UPDATE employees SET is_active = %s WHERE employee_id = %s",
            (value, change["row_id"]),
        )
    else:
        raise RuntimeError("Refusing an unsupported business-row mutation.")


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
    if existing_snap:
        raise RuntimeError(
            f"An attack snapshot already exists ({existing_snap.get('scenario')}). "
            "Run 'heal' first; an active recovery baseline cannot be overwritten."
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
            # Prefer a live salary record so the default attack changes real data.
            cur.execute(
                "SELECT sequence_id, actor_user_id, employee_id, action, table_name, "
                "row_id, old_value::TEXT AS old_value_text, new_value::TEXT AS new_value_text, "
                "severity, entry_hash, previous_hash, created_at::TEXT AS created_at_text "
                "FROM audit_log WHERE table_name = 'salary_history' AND new_value ? 'amount' "
                "AND action <> 'DELETE' ORDER BY sequence_id DESC LIMIT 1"
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
        tampered_val, business_change, business_snapshot = plan_business_value_replacement(cur, target_row)

        # Record snapshot
        snapshot = {
            "scenario": "dba-row-tamper",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target_sequence_id": target_seq,
            "audit_rows": [dict(target_row)],
            "business_rows": [business_snapshot],
            "notes": "Out-of-band business-row and matching audit-payload mutation without hash update.",
        }
        save_snapshot(snapshot, snapshot_path)

        # A privileged DBA changes the business table and falsifies its ledger
        # event while leaving the stored chain hashes untouched.
        apply_business_value_replacement(cur, business_change, business_change["after_value"])
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
            "business_change": business_change,
            "sql_executed": "Updated the live business row and matching audit payload with triggers suppressed; left hashes unchanged.",
            "message": f"Successfully injected SQL row tamper at sequence_id {target_seq}. Hash chain is now invalid.",
        }


def attack_recompute_and_hide(
    conn: psycopg2.extensions.connection,
    sequence_id: int | None = None,
    snapshot_path: str = DEFAULT_SNAPSHOT_PATH,
    force: bool = False,
) -> dict:
    """Scenario 2: Replace a business value and recalculate all forward hashes.
    
    A sophisticated rogue DBA replaces a historical salary amount (or employee
    status/role for an explicitly selected employee event) and rewrites the
    SHA-256 hash chain from that point forward to the chain tail.
    
    Result:
    The internal chain passes a naive verification walk (`verify_chain` returns True),
    BUT fails external anchor verification because the historical Ed25519 checkpoint
    anchor was already committed to an immutable store before the attack occurred.
    """
    existing_snap = load_snapshot(snapshot_path)
    if existing_snap:
        raise RuntimeError(
            f"An attack snapshot already exists ({existing_snap.get('scenario')}). "
            "Run 'heal' first; an active recovery baseline cannot be overwritten."
        )

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Determine target sequence
        if sequence_id is not None:
            target_seq = sequence_id
        else:
            # Prefer a real salary event before the first checkpoint so the demo
            # shows an actual business-value replacement in the forensic diff.
            cur.execute("SELECT MIN(sequence_id) FROM chain_checkpoints")
            min_cp = cur.fetchone()["min"]
            if min_cp and min_cp > 5:
                target_boundary = min_cp - 5
            else:
                cur.execute("SELECT COUNT(*) FROM audit_log")
                cnt = cur.fetchone()["count"]
                target_boundary = max(1, cnt // 2)
            cur.execute(
                "SELECT MAX(sequence_id) FROM audit_log "
                "WHERE table_name = 'salary_history' AND sequence_id <= %s "
                "AND new_value ? 'amount'",
                (target_boundary,),
            )
            salary_target = cur.fetchone()["max"]
            if salary_target is not None:
                target_seq = salary_target
            else:
                target_seq = target_boundary

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
        tampered_val, business_change, business_snapshot = plan_business_value_replacement(cur, affected_rows[0])

        # Fetch chain_state
        cur.execute("SELECT id, tail_hash, tail_sequence_id, last_checkpoint_sequence_id FROM chain_state WHERE id = 1")
        chain_state_row = cur.fetchone()

        # Fetch checkpoints at or after target_seq
        cur.execute(
            "SELECT checkpoint_id, sequence_id, checkpoint_hash, merkle_root, signature, created_at "
            "FROM chain_checkpoints WHERE sequence_id >= %s ORDER BY sequence_id ASC",
            (target_seq,),
        )
        affected_cps = cur.fetchall()
        if not affected_cps:
            raise RuntimeError(
                f"Sequence {target_seq} is beyond the latest signed checkpoint. "
                "Choose an event covered by an existing checkpoint so the external anchor can detect the rewrite."
            )

        # Save snapshot
        snapshot = {
            "scenario": "recompute-and-hide",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target_sequence_id": target_seq,
            "audit_rows": [dict(r) for r in affected_rows],
            "business_rows": [business_snapshot],
            "chain_state": dict(chain_state_row) if chain_state_row else None,
            "checkpoints": [
                {
                    "checkpoint_id": cp["checkpoint_id"],
                    "sequence_id": cp["sequence_id"],
                    "checkpoint_hash": cp["checkpoint_hash"],
                    "merkle_root": cp["merkle_root"],
                    "signature_hex": bytes(cp["signature"]).hex(),
                    "created_at": cp["created_at"].isoformat() if hasattr(cp["created_at"], "isoformat") else str(cp["created_at"]),
                }
                for cp in affected_cps
            ],
            "notes": "Recalculated forward hash chain to test external anchor mismatch.",
        }
        # Get predecessor hash for target row
        if target_seq > 1:
            cur.execute("SELECT entry_hash FROM audit_log WHERE sequence_id = %s", (target_seq - 1,))
            pred = cur.fetchone()
            current_prev_hash = pred["entry_hash"] if pred else ("0" * 64)
        else:
            current_prev_hash = "0" * 64

        # Save the recovery snapshot only after confirming this target supports
        # a meaningful replacement, so a rejected target cannot leave a stale
        # snapshot that blocks the next attack.
        save_snapshot(snapshot, snapshot_path)

        # A compromised database administrator changes the live source row,
        # falsifies the corresponding ledger event, and recomputes the chain.
        apply_business_value_replacement(cur, business_change, business_change["after_value"])
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
            "business_change": business_change,
            "message": (
                f"Replaced {business_change['table_name']}.{business_change['column']} "
                f"from {business_change['before_value']} to {business_change['after_value']}, "
                f"then recalculated {recalculated_count} forward hashes. "
                "The internal chain is consistent; the signed checkpoint and external anchor detect the rewrite."
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
    if existing_snap:
        raise RuntimeError(
            f"An attack snapshot already exists ({existing_snap.get('scenario')}). "
            "Run 'heal' first; an active recovery baseline cannot be overwritten."
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

        # Simulate opaque signature corruption without a recognizable marker.
        # A random 64-byte value has the same shape as an Ed25519 signature but
        # cannot authenticate the checkpoint under the trusted public key.
        forged_sig = secrets.token_bytes(64)
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
    if existing_snap:
        raise RuntimeError(
            f"An attack snapshot already exists ({existing_snap.get('scenario')}). "
            "Run 'heal' first; an active recovery baseline cannot be overwritten."
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
    scenario = snapshot.get("scenario", "unknown") if snapshot else None

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
            business_rows = snapshot.get("business_rows", [])
            if business_rows:
                # Recovery updates source tables without generating fresh audit
                # events; their original audit rows and hashes are restored below.
                cur.execute("SET LOCAL session_replication_role = replica")
            for business_row in business_rows:
                if business_row["table_name"] == "salary_history" and business_row["column"] == "amount":
                    cur.execute(
                        "UPDATE salary_history SET amount = %s WHERE salary_history_id = %s",
                        (business_row["value"], business_row["row_id"]),
                    )
                elif business_row["table_name"] == "employees" and business_row["column"] == "is_active":
                    cur.execute(
                        "UPDATE employees SET is_active = %s WHERE employee_id = %s",
                        (business_row["value"], business_row["row_id"]),
                    )
                else:
                    raise RuntimeError("Snapshot contains an unsupported business-row restoration.")

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

        # Repair signatures only with the configured local signer, and only when
        # its public key is the trusted key for that checkpoint's key_id. The old
        # hard-coded keys/public_key.pem + signing_key.pem pair could silently
        # replace valid demo signatures with signatures the API did not trust.
        healed_checkpoints = []
        signature_failures = []
        try:
            from api.config import get_settings
            from db.cli.keygen import load_public_key, load_private_key
            from db.cli.signer import verify_signature, sign_checkpoint
            from cryptography.hazmat.primitives import serialization

            settings = get_settings()
            key_dir = Path(settings.CHECKPOINT_PUBLIC_KEYS_DIR)
            private_path = Path(settings.SIGNING_PRIVATE_KEY_PATH)
            private_key = load_private_key(str(private_path)) if private_path.is_file() else None
            private_public = (
                private_key.public_key().public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                )
                if private_key
                else None
            )

            cur.execute(
                "SELECT checkpoint_id, checkpoint_hash, signature, merkle_root, key_id "
                "FROM chain_checkpoints ORDER BY checkpoint_id ASC"
            )
            for chk_id, chk_hash, chk_sig, merkle_root, key_id in cur.fetchall():
                public_filename = (
                    "public_key.pem"
                    if not key_id or key_id == "local:ed25519:v1"
                    else f"{quote(str(key_id), safe='')}.pem"
                )
                public_path = key_dir / public_filename
                if not public_path.is_file():
                    signature_failures.append(chk_id)
                    continue
                public_key = load_public_key(str(public_path))
                sig_bytes = bytes(chk_sig) if chk_sig else None
                if sig_bytes and verify_signature(
                    public_key, chk_hash, sig_bytes, key_id=key_id, merkle_root=merkle_root
                ):
                    continue

                trusted_public = public_key.public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                )
                if private_key is None or private_public != trusted_public:
                    signature_failures.append(chk_id)
                    continue

                signed_payload = f"{chk_hash}:{merkle_root}" if merkle_root else chk_hash
                repaired_signature = sign_checkpoint(private_key, signed_payload)
                cur.execute(
                    "UPDATE chain_checkpoints SET signature = %s WHERE checkpoint_id = %s",
                    (psycopg2.Binary(repaired_signature), chk_id),
                )
                healed_checkpoints.append(chk_id)
            conn.commit()

            # Re-check every signature after any repairs.
            signature_failures = []
            cur.execute(
                "SELECT checkpoint_id, checkpoint_hash, signature, merkle_root, key_id "
                "FROM chain_checkpoints ORDER BY checkpoint_id ASC"
            )
            for chk_id, chk_hash, chk_sig, merkle_root, key_id in cur.fetchall():
                public_filename = (
                    "public_key.pem"
                    if not key_id or key_id == "local:ed25519:v1"
                    else f"{quote(str(key_id), safe='')}.pem"
                )
                public_path = key_dir / public_filename
                if not public_path.is_file() or not chk_sig:
                    signature_failures.append(chk_id)
                    continue
                public_key = load_public_key(str(public_path))
                if not verify_signature(
                    public_key,
                    chk_hash,
                    bytes(chk_sig),
                    key_id=key_id,
                    merkle_root=merkle_root,
                ):
                    signature_failures.append(chk_id)
        except Exception:
            # A hash walk alone does not prove checkpoint signatures. Fail closed.
            signature_failures = [-1]

    # Validate post-healing integrity
    verify_res = verify_chain(conn)

    signatures_valid = not signature_failures
    restored_cleanly = verify_res.is_valid and signatures_valid
    # Keep the recovery material whenever validation fails so the operator can
    # investigate or retry instead of losing the only known-good baseline.
    if snapshot and restored_cleanly:
        clear_snapshot(snapshot_path)

    return {
        "status": "healed" if restored_cleanly and (snapshot or healed_checkpoints) else "failed" if not restored_cleanly else "clean",
        "scenario": scenario or ("checkpoint-signature-repair" if healed_checkpoints else None),
        "is_valid": verify_res.is_valid and signatures_valid,
        "signatures_valid": signatures_valid,
        "invalid_checkpoints": signature_failures,
        "entries_scanned": verify_res.total_entries,
        "mismatches": len(verify_res.mismatches),
        "gaps": len(verify_res.gaps),
        "orphans": len(verify_res.orphans),
        "healed_checkpoints": healed_checkpoints,
        "message": (
            "Database and cryptographic integrity successfully restored and re-verified."
            if restored_cleanly and (snapshot or healed_checkpoints)
            else "Restoration could not be fully verified. The recovery snapshot was retained."
            if not restored_cleanly
            else "No active attack snapshot found. Database is in pristine condition."
        ),
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

    # Use the same configured anchor and trusted-key paths as the API verifier.
    checkpoint_status = "unknown"
    checkpoints_valid = False
    invalid_checkpoints = []
    anchor_status = "unknown"
    anchor_intact = False
    anchor_details = "No checkpoints are available for anchor comparison."
    try:
        from api.config import get_settings
        from db.cli.keygen import load_public_key
        from db.cli.signer import verify_signature
        settings = get_settings()
        key_dir = Path(settings.CHECKPOINT_PUBLIC_KEYS_DIR)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT checkpoint_id, sequence_id, checkpoint_hash, signature, merkle_root, key_id "
                "FROM chain_checkpoints ORDER BY checkpoint_id ASC"
            )
            checkpoint_rows = cur.fetchall()
            checkpoint_status = "pass" if checkpoint_rows else "unknown"
            for cp in checkpoint_rows:
                key_name = (
                    "public_key.pem"
                    if not cp["key_id"] or cp["key_id"] == "local:ed25519:v1"
                    else f"{quote(str(cp['key_id']), safe='')}.pem"
                )
                pub_path = key_dir / key_name
                sig_bytes = bytes(cp["signature"]) if cp["signature"] else None
                if not pub_path.is_file():
                    if checkpoint_status != "fail":
                        checkpoint_status = "unknown"
                    continue
                if not sig_bytes:
                    checkpoint_status = "fail"
                    checkpoints_valid = False
                    invalid_checkpoints.append({
                        "checkpoint_id": cp["checkpoint_id"],
                        "sequence_id": cp["sequence_id"],
                        "checkpoint_hash": cp["checkpoint_hash"],
                    })
                    continue
                if not verify_signature(
                    load_public_key(str(pub_path)),
                    cp["checkpoint_hash"],
                    sig_bytes,
                    key_id=cp["key_id"],
                    merkle_root=cp["merkle_root"],
                ):
                    checkpoint_status = "fail"
                    invalid_checkpoints.append({
                        "checkpoint_id": cp["checkpoint_id"],
                        "sequence_id": cp["sequence_id"],
                        "checkpoint_hash": cp["checkpoint_hash"],
                    })
        checkpoints_valid = checkpoint_status == "pass"

        configured_anchor = Path(settings.ANCHOR_FILE_PATH)
        anchor_dir = configured_anchor.parent if configured_anchor.suffix else configured_anchor
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT checkpoint_id, sequence_id, checkpoint_hash "
                "FROM chain_checkpoints ORDER BY sequence_id DESC LIMIT 1"
            )
            latest = cur.fetchone()
        if latest:
            anchor_path = anchor_dir / f"{latest['checkpoint_id']}.json"
            try:
                anchor_data = json.loads(anchor_path.read_text(encoding="utf-8"))
                anchor_intact = (
                    anchor_data.get("checkpoint_id") == latest["checkpoint_id"]
                    and anchor_data.get("sequence_id") == latest["sequence_id"]
                    and anchor_data.get("checkpoint_hash") == latest["checkpoint_hash"]
                )
                anchor_status = "pass" if anchor_intact else "fail"
                anchor_details = (
                    f"Anchor {latest['checkpoint_id']} matches configured store."
                    if anchor_intact
                    else f"Anchor mismatch for checkpoint {latest['checkpoint_id']}."
                )
            except FileNotFoundError:
                anchor_details = f"No external anchor record exists for checkpoint {latest['checkpoint_id']}."
            except (OSError, json.JSONDecodeError, TypeError):
                anchor_details = f"External anchor record for checkpoint {latest['checkpoint_id']} could not be read."
    except Exception as e:
        checkpoint_status = "unknown"
        checkpoints_valid = False
        anchor_status = "unknown"
        anchor_intact = False
        anchor_details = f"Configured verification evidence could not be read: {e}"

    # A recovery snapshot is not evidence of compromise. Only failed integrity
    # checks are allowed to mark the database as attacked.
    anomaly_detected = (
        not chain_res.is_valid
        or checkpoint_status == "fail"
        or anchor_status == "fail"
    )

    inferred_scenario = None
    if not chain_res.is_valid:
        inferred_scenario = "delete-audit-row" if chain_res.gaps else "dba-row-tamper"
    elif anchor_status == "fail":
        inferred_scenario = "recompute-and-hide"
    elif checkpoint_status == "fail":
        inferred_scenario = "checkpoint-forgery"

    inferred_target_seq = None
    if chain_res.mismatches:
        inferred_target_seq = chain_res.mismatches[0].get("sequence_id")
    elif chain_res.gaps:
        inferred_target_seq = chain_res.gaps[0].get("expected_seq")
    elif chain_res.orphans:
        inferred_target_seq = chain_res.orphans[0].get("sequence_id")
    elif invalid_checkpoints:
        inferred_target_seq = invalid_checkpoints[0]["sequence_id"]
    elif anchor_status == "fail" and snapshot and snapshot.get("target_sequence_id"):
        # The independently verified anchor mismatch proves tampering. The
        # snapshot is used only to focus the forensic view on the edited row.
        inferred_target_seq = snapshot["target_sequence_id"]

    return {
        "attack_active": anomaly_detected,
        "snapshot_exists": snapshot is not None,
        "recovery_available": snapshot is not None,
        "active_scenario": inferred_scenario,
        "attack_timestamp": snapshot.get("timestamp") if snapshot else None,
        "target_sequence_id": inferred_target_seq,
        "chain_valid": chain_res.is_valid,
        "checkpoints_valid": checkpoints_valid,
        "checkpoint_status": checkpoint_status,
        "invalid_checkpoints": invalid_checkpoints,
        "total_audit_rows": total_rows,
        "total_checkpoints": total_checkpoints,
        "mismatches": chain_res.mismatches,
        "gaps": chain_res.gaps,
        "orphans": chain_res.orphans,
        "anchor_intact": anchor_intact,
        "anchor_status": anchor_status,
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
    if conn is None:
        return 2
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
            change = res["business_change"]
            print(
                f"    Live DB Change     : {Colors.YELLOW}{change['table_name']}.{change['column']} "
                f"{change['before_value']} -> {change['after_value']}{Colors.RESET}"
            )
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
            change = res["business_change"]
            print(
                f"    Live DB Change     : {Colors.YELLOW}{change['table_name']}.{change['column']} "
                f"{change['before_value']} -> {change['after_value']}{Colors.RESET}"
            )
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
    if conn is None:
        return 2
    try:
        print_banner()
        print(f"{Colors.CYAN}[*] Restoring database integrity from snapshot...{Colors.RESET}")
        res = heal_database(conn, snapshot_path=args.snapshot_path)
        
        if res["status"] == "clean" and res["is_valid"]:
            print(f"{Colors.GREEN}[OK] {res['message']}{Colors.RESET}")
        elif res["is_valid"]:
            print(f"{Colors.GREEN}{Colors.BOLD}[OK] HEAL SUCCESSFUL!{Colors.RESET}")
            print(f"    Reverted Scenario  : {Colors.BOLD}{res['scenario']}{Colors.RESET}")
            if res.get("healed_checkpoints"):
                print(f"    Healed Signatures  : {Colors.BOLD}Checkpoints {res['healed_checkpoints']}{Colors.RESET}")
            print(f"    Entries Verified   : {Colors.BOLD}{res['entries_scanned']}{Colors.RESET}")
            print(f"    Chain & Signatures : {Colors.GREEN}{Colors.BOLD}VALID (Zero Tampering){Colors.RESET}")
            print()
            print(f"Verify in Web Dashboard at {Colors.CYAN}http://localhost:5173/auditor/overview{Colors.RESET} (Status: VALID).")
        else:
            print(f"{Colors.RED}{Colors.BOLD}[!] HEAL INCOMPLETE: cryptographic verification still fails.{Colors.RESET}")
            print(f"    Hash Chain         : {'VALID' if res['mismatches'] == 0 and res['gaps'] == 0 and res['orphans'] == 0 else 'INVALID'}")
            print(f"    Invalid Checkpoints: {res.get('invalid_checkpoints', [])}")

        return 0 if res["is_valid"] else 1

    except Exception as exc:
        print(f"{Colors.RED}[!] Heal failed:{Colors.RESET} {exc}")
        return 1
    finally:
        conn.close()


def cmd_status(args: argparse.Namespace) -> int:
    conn = get_admin_connection(args.db_url)
    if conn is None:
        return 2
    try:
        print_banner()
        print(f"{Colors.CYAN}[*] Diagnosing Database and Verifier Integrity...{Colors.RESET}\n")
        status = get_adversary_status(conn, snapshot_path=args.snapshot_path)

        if status["attack_active"]:
            print(f"{Colors.RED}{Colors.BOLD}+---------------------------------------------------------------+{Colors.RESET}")
            print(f"{Colors.RED}{Colors.BOLD}| [!] CRYPTOGRAPHIC INTEGRITY BREACH DETECTED                    |{Colors.RESET}")
            print(f"{Colors.RED}{Colors.BOLD}+---------------------------------------------------------------+{Colors.RESET}")
            print(f"  Evidence   : {Colors.YELLOW}{status['active_scenario'] or 'Direct DB Tampering'}{Colors.RESET}")
            if status.get("target_sequence_id"):
                print(f"  Evidence Seq: {Colors.YELLOW}{status['target_sequence_id']}{Colors.RESET}")
            if status.get("recovery_available"):
                print(f"  Recovery   : {Colors.GREEN}Pre-attack snapshot available{Colors.RESET}")
            print(f"  Heal with  : {Colors.GREEN}python -m db.cli.adversary heal{Colors.RESET}\n")
        elif status.get("recovery_available"):
            print(f"{Colors.YELLOW}[i] Recovery snapshot available; no cryptographic breach was detected.{Colors.RESET}")
            print(f"    The snapshot is for restore only and is not used as verifier evidence. Heal before another attack.\n")
        elif status.get("checkpoint_status") == "unknown" or status.get("anchor_status") == "unknown":
            print(f"{Colors.YELLOW}[?] No breach was proven, but some cryptographic evidence is unavailable.{Colors.RESET}\n")
        else:
            print(f"{Colors.GREEN}[OK] Cryptographic checks passed; no integrity breach detected.{Colors.RESET}\n")

        valid_str = f"{Colors.GREEN}VALID (INTACT){Colors.RESET}" if status["chain_valid"] else f"{Colors.RED}TAMPERED / INVALID{Colors.RESET}"
        print(f"  Total Audit Log Entries : {status['total_audit_rows']}")
        print(f"  Total Checkpoints       : {status['total_checkpoints']}")
        print(f"  Internal Hash Chain     : {valid_str}")

        cp_valid_str = (
            f"{Colors.GREEN}VALID (All signatures verified){Colors.RESET}"
            if status.get("checkpoint_status") == "pass"
            else f"{Colors.RED}INVALID ({len(status.get('invalid_checkpoints', []))} invalid signature(s)){Colors.RESET}"
            if status.get("checkpoint_status") == "fail"
            else f"{Colors.YELLOW}UNVERIFIED (trusted key/evidence unavailable){Colors.RESET}"
        )
        print(f"  Checkpoint Signatures   : {cp_valid_str}")
        if status.get("checkpoint_status") == "fail":
            for inv_cp in status.get("invalid_checkpoints", []):
                print(f"    - Checkpoint {inv_cp['checkpoint_id']} (Seq {inv_cp['sequence_id']}): {Colors.RED}Invalid Ed25519 signature{Colors.RESET}")

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

        anchor_str = (
            f"{Colors.GREEN}MATCH{Colors.RESET}"
            if status.get("anchor_status") == "pass"
            else f"{Colors.RED}MISMATCH{Colors.RESET}"
            if status.get("anchor_status") == "fail"
            else f"{Colors.YELLOW}UNVERIFIED{Colors.RESET}"
        )
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
    parser.add_argument(
        "--tui",
        action="store_true",
        help="Launch the interactive Terminal User Interface (TUI) for the adversary engine.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Adversary commands")

    # tui
    subparsers.add_parser("tui", parents=[parent_parser], help="Launch the interactive Terminal User Interface (TUI) for the adversary engine.")

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
        help="Deprecated. Active recovery snapshots are never overwritten; heal first.",
    )

    # heal
    subparsers.add_parser("heal", parents=[parent_parser], help="Revert all mutations and restore pristine database integrity.")

    # status
    subparsers.add_parser("status", parents=[parent_parser], help="Inspect current attack state and cryptographic integrity.")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if getattr(args, "tui", False) or args.command == "tui":
        from db.cli.tui_adversary import run_adversary_tui
        try:
            # The normal Argus walkthrough keeps its database override in
            # .env.local. Load it after .env so every TUI action uses the same
            # explicitly resolved database instead of splitting discovery and
            # mutation across different targets.
            from dotenv import load_dotenv

            load_dotenv(".env", override=False)
            if Path(".env.local").is_file():
                load_dotenv(".env.local", override=True)
            tui_db_url = resolve_db_url(args.db_url)
        except (ImportError, ValueError) as exc:
            print(f"{Colors.RED}[!] Cannot resolve TUI database: {exc}{Colors.RESET}")
            return 2
        run_adversary_tui(tui_db_url)
        return 0

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
