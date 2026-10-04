"""Checkpoint persistence module for Argus tamper-evident audit trail verification engine.

Provides functions to store, retrieve, and compute signed checkpoints in the
chain_checkpoints table.
"""

from __future__ import annotations

import datetime
import hashlib
import logging
from typing import Any

import psycopg2
import psycopg2.extras

logger = logging.getLogger("argus.checkpoint_store")

DEFAULT_MAX_ENTRIES: int = 25
DEFAULT_MAX_SECONDS: float = 60.0
MAX_UNDETECTABLE_TAMPERING_WINDOW_SECONDS: float = 60.0


def store_checkpoint(
    conn: Any,
    sequence_id: int,
    checkpoint_hash: str,
    signature: bytes,
    key_id: str | None = None,
    merkle_root: str | None = None,
    merkle_leaf_count: int | None = None,
) -> bool:
    """Stores a signed checkpoint in the chain_checkpoints table.

    Uses ON CONFLICT (sequence_id) DO NOTHING to ensure idempotency. Commits the
    transaction after inserting.

    Args:
        conn: A psycopg2 database connection object.
        sequence_id: The audit log sequence ID at which the checkpoint is created.
        checkpoint_hash: SHA-256 hash representing the state of the audit chain.
        signature: Cryptographic signature bytes for the checkpoint hash.
        key_id: Optional key identifier string for key rotation tracking (e.g. 'local:ed25519:v1').
        merkle_root: Optional hex-encoded RFC 6962 SHA-256 Merkle root hash.
        merkle_leaf_count: Optional count of audit rows in this checkpoint's Merkle tree.

    Returns:
        bool: True if a new checkpoint row was inserted, False if a row for the
            sequence_id already existed.

    Raises:
        psycopg2.Error: If a database error occurs.
    """
    if merkle_root is not None:
        query = (
            "INSERT INTO chain_checkpoints (sequence_id, checkpoint_hash, signature, key_id, merkle_root, merkle_leaf_count) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (sequence_id) DO NOTHING"
        )
        params: tuple = (sequence_id, checkpoint_hash, signature, key_id, merkle_root, merkle_leaf_count)
    elif key_id is not None:
        query = (
            "INSERT INTO chain_checkpoints (sequence_id, checkpoint_hash, signature, key_id) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (sequence_id) DO NOTHING"
        )
        params = (sequence_id, checkpoint_hash, signature, key_id)
    else:
        query = (
            "INSERT INTO chain_checkpoints (sequence_id, checkpoint_hash, signature) "
            "VALUES (%s, %s, %s) "
            "ON CONFLICT (sequence_id) DO NOTHING"
        )
        params = (sequence_id, checkpoint_hash, signature)
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            inserted = cur.rowcount > 0
        conn.commit()
        return inserted
    except Exception:
        conn.rollback()
        # Fallback if merkle columns do not exist in test schema
        if merkle_root is not None:
            try:
                with conn.cursor() as cur:
                    if key_id is not None:
                        cur.execute(
                            "INSERT INTO chain_checkpoints (sequence_id, checkpoint_hash, signature, key_id) "
                            "VALUES (%s, %s, %s, %s) ON CONFLICT (sequence_id) DO NOTHING",
                            (sequence_id, checkpoint_hash, signature, key_id),
                        )
                    else:
                        cur.execute(
                            "INSERT INTO chain_checkpoints (sequence_id, checkpoint_hash, signature) "
                            "VALUES (%s, %s, %s) ON CONFLICT (sequence_id) DO NOTHING",
                            (sequence_id, checkpoint_hash, signature),
                        )
                    inserted = cur.rowcount > 0
                conn.commit()
                return inserted
            except Exception:
                conn.rollback()
        raise


def get_checkpoint(
    conn: Any,
    checkpoint_id: int,
    include_key_id: bool = False,
    include_merkle: bool = False,
) -> dict | None:
    """Retrieves a checkpoint by its primary key (checkpoint_id).

    Args:
        conn: A psycopg2 database connection object.
        checkpoint_id: The unique ID of the checkpoint to retrieve.
        include_key_id: If True, includes the key_id column in the returned dict.
        include_merkle: If True, includes merkle_root and merkle_leaf_count in the returned dict.

    Returns:
        dict | None: Dictionary with keys 'checkpoint_id', 'sequence_id',
            'checkpoint_hash', 'signature', and 'created_at' if found, or
            None if no matching record exists.

    Raises:
        psycopg2.Error: If a database error occurs.
    """
    cols = "checkpoint_id, sequence_id, checkpoint_hash, signature, created_at"
    if include_key_id:
        cols += ", key_id"
    if include_merkle:
        cols += ", merkle_root, merkle_leaf_count"
    query = (
        f"SELECT {cols} "
        "FROM chain_checkpoints "
        "WHERE checkpoint_id = %s"
    )
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, (checkpoint_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return dict(row)


def get_checkpoints_in_range(
    conn: Any,
    start_seq: int,
    end_seq: int,
    include_key_id: bool = False,
    include_merkle: bool = False,
) -> list[dict]:
    """Retrieves all checkpoints with sequence_id in the specified range.

    Args:
        conn: A psycopg2 database connection object.
        start_seq: The lower bound sequence ID (inclusive).
        end_seq: The upper bound sequence ID (inclusive).
        include_key_id: If True, includes key_id column in returned dicts.
        include_merkle: If True, includes merkle_root and merkle_leaf_count in returned dicts.

    Returns:
        list[dict]: A list of checkpoint dictionary objects ordered by sequence_id.

    Raises:
        psycopg2.Error: If a database error occurs.
    """
    cols = "checkpoint_id, sequence_id, checkpoint_hash, signature, created_at"
    if include_key_id:
        cols += ", key_id"
    if include_merkle:
        cols += ", merkle_root, merkle_leaf_count"
    query = (
        f"SELECT {cols} "
        "FROM chain_checkpoints "
        "WHERE sequence_id BETWEEN %s AND %s "
        "ORDER BY sequence_id"
    )
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, (start_seq, end_seq))
        rows = cur.fetchall()
        return [dict(row) for row in rows]


def compute_checkpoint_hash(entry_hashes: list[str]) -> str:
    """Computes a SHA-256 digest from a list of entry hashes.

    Concatenates all entry hash strings in the order provided and computes
    their SHA-256 hex digest.

    Args:
        entry_hashes: List of entry hash hex strings to concatenate.

    Returns:
        str: SHA-256 hex digest string.
    """
    concatenated = "".join(entry_hashes)
    return hashlib.sha256(concatenated.encode("utf-8")).hexdigest()


def get_all_checkpoints(
    conn: Any,
    include_key_id: bool = False,
    include_merkle: bool = False,
) -> list[dict]:
    """Retrieves all checkpoint rows ordered by sequence_id.

    Used by the parallel verification engine to derive segment boundaries.
    Each checkpoint's ``sequence_id`` marks the end (inclusive) of a segment.

    Args:
        conn: A psycopg2 database connection object.
        include_key_id: If True, includes the key_id column in returned dicts.
        include_merkle: If True, includes merkle_root and merkle_leaf_count in returned dicts.

    Returns:
        list[dict]: All checkpoint rows as dicts, ordered by sequence_id
            ascending.  Empty list if no checkpoints exist.

    Raises:
        psycopg2.Error: If a database error occurs.
    """
    cols = "checkpoint_id, sequence_id, checkpoint_hash, signature, created_at"
    if include_key_id:
        cols += ", key_id"
    if include_merkle:
        cols += ", merkle_root, merkle_leaf_count"
    query = (
        f"SELECT {cols} "
        "FROM chain_checkpoints "
        "ORDER BY sequence_id"
    )
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query)
        rows = cur.fetchall()
        return [dict(row) for row in rows]


def get_latest_checkpoint(
    conn: Any,
    include_key_id: bool = False,
    include_merkle: bool = False,
) -> dict | None:
    """Retrieves the latest checkpoint from chain_checkpoints ordered by sequence_id.

    Args:
        conn: A psycopg2 database connection object.
        include_key_id: If True, includes the key_id column in returned dict.
        include_merkle: If True, includes merkle_root and merkle_leaf_count in returned dict.

    Returns:
        dict | None: The most recent checkpoint row as a dict, or None if empty.

    Raises:
        psycopg2.Error: If a database error occurs.
    """
    cols = "checkpoint_id, sequence_id, checkpoint_hash, signature, created_at"
    if include_key_id:
        cols += ", key_id"
    if include_merkle:
        cols += ", merkle_root, merkle_leaf_count"
    query = (
        f"SELECT {cols} "
        "FROM chain_checkpoints "
        "ORDER BY sequence_id DESC "
        "LIMIT 1"
    )
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query)
        row = cur.fetchone()
        if row is None:
            return None
        return dict(row)


def get_uncheckpointed_entries(conn: Any, last_checkpoint_seq: int = 0) -> list[dict]:
    """Retrieves all audit_log entries with sequence_id strictly greater than last_checkpoint_seq.

    Args:
        conn: A psycopg2 database connection object.
        last_checkpoint_seq: Sequence ID of the last recorded checkpoint (default: 0).

    Returns:
        list[dict]: Uncheckpointed audit log entries ordered by sequence_id ascending.

    Raises:
        psycopg2.Error: If a database error occurs.
    """
    query = (
        "SELECT sequence_id, entry_hash, created_at "
        "FROM audit_log "
        "WHERE sequence_id > %s "
        "ORDER BY sequence_id ASC"
    )
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, (last_checkpoint_seq,))
        rows = cur.fetchall()
        return [dict(r) for r in rows]


def get_uncheckpointed_rows(conn: Any, last_checkpoint_seq: int = 0) -> list[dict]:
    """Retrieves full audit_log entries strictly greater than last_checkpoint_seq for Merkle tree generation."""
    query = (
        "SELECT sequence_id, actor_user_id, employee_id, action, table_name, row_id, "
        "old_value, new_value, severity, entry_hash, previous_hash, created_at "
        "FROM audit_log "
        "WHERE sequence_id > %s "
        "ORDER BY sequence_id ASC"
    )
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, (last_checkpoint_seq,))
        rows = cur.fetchall()
        return [dict(r) for r in rows]


def _normalize_datetime(dt: datetime.datetime | None) -> datetime.datetime:
    """Normalizes a datetime object to UTC timezone-aware."""
    if dt is None:
        return datetime.datetime.now(datetime.timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def should_create_checkpoint(
    conn: Any,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    max_seconds: float = DEFAULT_MAX_SECONDS,
    current_time: datetime.datetime | None = None,
) -> tuple[bool, str, dict]:
    """Determines whether a dual-trigger checkpoint condition is satisfied.

    Evaluates both:
    1. Count condition: Uncheckpointed entries >= max_entries (N=25 by default)
    2. Time condition: Elapsed time since last checkpoint (or first uncheckpointed entry)
       >= max_seconds (T=60s by default)

    This hybrid cadence ensures that high-throughput bursts checkpoint at regular
    transaction intervals while quiet workloads are bounded by a maximum 60-second
    tampering exposure window against an administrative adversary (A_DBA).

    Args:
        conn: A psycopg2 database connection object.
        max_entries: Entry count threshold (default: 25).
        max_seconds: Maximum elapsed seconds before forcing a checkpoint (default: 60.0).
        current_time: Optional datetime reference for evaluation/testing.

    Returns:
        tuple[bool, str, dict]: (should_fire, reason, details_dict)
            reason is one of:
            - "entry_count_threshold": triggered by row count >= max_entries
            - "time_elapsed_threshold": triggered by time >= max_seconds
            - "no_entries": no uncheckpointed entries exist
            - "threshold_not_reached": neither condition is met
    """
    latest = get_latest_checkpoint(conn)
    last_seq = latest["sequence_id"] if latest else 0

    uncheckpointed = get_uncheckpointed_entries(conn, last_checkpoint_seq=last_seq)
    entry_count = len(uncheckpointed)

    now_utc = _normalize_datetime(current_time)

    if entry_count == 0:
        return False, "no_entries", {
            "entries_since": 0,
            "seconds_since": 0.0,
            "max_entries": max_entries,
            "max_seconds": max_seconds,
            "last_checkpoint_seq": last_seq,
        }

    # Reference timestamp for elapsed time calculation
    if latest is not None and latest.get("created_at") is not None:
        ref_time = _normalize_datetime(latest["created_at"])
    else:
        ref_time = _normalize_datetime(uncheckpointed[0]["created_at"])

    seconds_since = max(0.0, (now_utc - ref_time).total_seconds())

    details = {
        "entries_since": entry_count,
        "seconds_since": round(seconds_since, 3),
        "max_entries": max_entries,
        "max_seconds": max_seconds,
        "last_checkpoint_seq": last_seq,
        "start_seq": uncheckpointed[0]["sequence_id"],
        "end_seq": uncheckpointed[-1]["sequence_id"],
    }

    if entry_count >= max_entries:
        logger.info(
            "Dual-trigger checkpoint condition met: %d entries >= threshold %d",
            entry_count,
            max_entries,
        )
        return True, "entry_count_threshold", details

    if seconds_since >= max_seconds:
        logger.info(
            "Dual-trigger checkpoint condition met: %.1fs elapsed >= threshold %.1fs (entries: %d)",
            seconds_since,
            max_seconds,
            entry_count,
        )
        return True, "time_elapsed_threshold", details

    return False, "threshold_not_reached", details


def create_dual_trigger_checkpoint(
    conn: Any,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    max_seconds: float = DEFAULT_MAX_SECONDS,
    current_time: datetime.datetime | None = None,
    signature: bytes | None = None,
    signer: Any | None = None,
    key_id: str | None = None,
) -> dict | None:
    """Creates and stores a signed checkpoint if either dual-trigger condition is satisfied.

    Args:
        conn: A psycopg2 database connection object.
        max_entries: Entry count threshold (default: 25).
        max_seconds: Maximum elapsed seconds before forcing a checkpoint (default: 60.0).
        current_time: Optional datetime reference for testing.
        signature: Explicit cryptographic signature bytes. If None and signer is provided,
            signer will be invoked; otherwise defaults to placeholder zero bytes.
        signer: Optional Signer instance or callable accepting bytes and returning bytes.
        key_id: Optional key identifier (e.g. 'local:ed25519:v1'). If None and signer has
            key_id attribute, signer.key_id will be used automatically.

    Returns:
        dict | None: Metadata dictionary of the created checkpoint, or None if skipped.
    """
    should_fire, reason, details = should_create_checkpoint(
        conn,
        max_entries=max_entries,
        max_seconds=max_seconds,
        current_time=current_time,
    )

    if not should_fire:
        return None

    last_seq = details["last_checkpoint_seq"]
    uncheckpointed = get_uncheckpointed_entries(conn, last_checkpoint_seq=last_seq)
    if not uncheckpointed:
        return None

    entry_hashes = [r["entry_hash"] for r in uncheckpointed]
    target_seq = uncheckpointed[-1]["sequence_id"]
    cp_hash = compute_checkpoint_hash(entry_hashes)

    # Compute RFC 6962 Merkle Tree over full audit rows in interval
    merkle_root = None
    merkle_leaf_count = None
    try:
        from db.cli.merkle_tree import ArgusMerkleTree
        full_rows = get_uncheckpointed_rows(conn, last_checkpoint_seq=last_seq)
        if full_rows:
            merkle_tree = ArgusMerkleTree.build(full_rows)
            merkle_root = merkle_tree.root
            merkle_leaf_count = merkle_tree.leaf_count
    except Exception as m_err:
        logger.debug("Could not compute Merkle tree: %s", m_err)

    resolved_key_id = key_id
    if signer is not None:
        sign_payload = (
            f"{cp_hash}:{merkle_root}".encode("utf-8")
            if merkle_root
            else cp_hash.encode("utf-8")
        )
        if hasattr(signer, "sign"):
            sig_bytes = signer.sign(sign_payload)
        elif callable(signer):
            sig_bytes = signer(sign_payload)
        else:
            raise TypeError("signer must have a .sign() method or be callable")
        if resolved_key_id is None and hasattr(signer, "key_id"):
            resolved_key_id = signer.key_id
    elif signature is not None:
        sig_bytes = signature
    else:
        sig_bytes = b"\x00" * 64

    stored = store_checkpoint(
        conn,
        target_seq,
        cp_hash,
        sig_bytes,
        key_id=resolved_key_id,
        merkle_root=merkle_root,
        merkle_leaf_count=merkle_leaf_count,
    )

    query = (
        "SELECT checkpoint_id, sequence_id, checkpoint_hash, signature, created_at "
        "FROM chain_checkpoints "
        "WHERE sequence_id = %s"
    )
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, (target_seq,))
        cp_row = cur.fetchone()

    return {
        "event": "checkpoint_created",
        "checkpoint_id": cp_row["checkpoint_id"] if cp_row else None,
        "checkpoint_sequence_id": target_seq,
        "checkpoint_hash": cp_hash,
        "merkle_root": merkle_root,
        "merkle_leaf_count": merkle_leaf_count,
        "entries_in_range": len(entry_hashes),
        "trigger_reason": reason,
        "newly_stored": stored,
        "key_id": resolved_key_id,
        "metadata": details,
    }


def verify_checkpoint_signatures(
    conn: Any,
    key_registry: Any | None = None,
    default_public_key: Any | None = None,
) -> tuple[bool, list[dict]]:
    """Verifies cryptographic signatures of all checkpoints in the database.

    Supports on-chain key rotation by resolving key_id for each checkpoint via
    KeyRegistry. If key_registry is provided, each checkpoint looks up its
    recorded key_id to verify its Ed25519 signature. If key_registry is None,
    falls back to default_public_key.

    Args:
        conn: A psycopg2 database connection object.
        key_registry: Optional KeyRegistry instance mapping key_id -> public key.
        default_public_key: Optional fallback Ed25519 public key.

    Returns:
        tuple[bool, list[dict]]: (all_valid, checkpoint_verification_records)
    """
    from db.cli.signer import verify_signature

    query = (
        "SELECT checkpoint_id, sequence_id, checkpoint_hash, signature, "
        "COALESCE(key_id, 'local:ed25519:v1') as key_id, merkle_root, merkle_leaf_count, created_at "
        "FROM chain_checkpoints "
        "ORDER BY sequence_id ASC"
    )
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        try:
            cur.execute(query)
            rows = cur.fetchall()
        except Exception:
            # Fallback if merkle columns or key_id have not been migrated yet in test db
            conn.rollback()
            try:
                cur.execute(
                    "SELECT checkpoint_id, sequence_id, checkpoint_hash, signature, "
                    "COALESCE(key_id, 'local:ed25519:v1') as key_id, created_at "
                    "FROM chain_checkpoints ORDER BY sequence_id ASC"
                )
                rows = [dict(r) for r in cur.fetchall()]
            except Exception:
                conn.rollback()
                cur.execute(
                    "SELECT checkpoint_id, sequence_id, checkpoint_hash, signature, created_at "
                    "FROM chain_checkpoints ORDER BY sequence_id ASC"
                )
                rows = [
                    {**dict(r), "key_id": "local:ed25519:v1"} for r in cur.fetchall()
                ]

    all_valid = True
    results = []

    for row in rows:
        chk_id = row["checkpoint_id"]
        chk_hash = row["checkpoint_hash"]
        chk_sig = bytes(row["signature"]) if row.get("signature") else b""
        chk_key_id = row.get("key_id", "local:ed25519:v1")
        chk_merkle_root = row.get("merkle_root")

        if not chk_sig or chk_sig == b"\x00" * 64:
            results.append({
                "checkpoint_id": chk_id,
                "sequence_id": row["sequence_id"],
                "status": "unsigned",
                "key_id": chk_key_id,
                "merkle_root": chk_merkle_root,
                "valid": False,
            })
            all_valid = False
            continue

        resolved_key = None
        if key_registry is not None:
            try:
                resolved_key = key_registry.get_public_key(chk_key_id)
            except KeyError:
                if default_public_key is not None:
                    resolved_key = default_public_key
                else:
                    results.append({
                        "checkpoint_id": chk_id,
                        "sequence_id": row["sequence_id"],
                        "status": "key_not_found",
                        "key_id": chk_key_id,
                        "merkle_root": chk_merkle_root,
                        "valid": False,
                    })
                    all_valid = False
                    continue
        else:
            resolved_key = default_public_key

        if resolved_key is None:
            results.append({
                "checkpoint_id": chk_id,
                "sequence_id": row["sequence_id"],
                "status": "no_key_provided",
                "key_id": chk_key_id,
                "merkle_root": chk_merkle_root,
                "valid": False,
            })
            all_valid = False
            continue

        valid = verify_signature(
            resolved_key,
            chk_hash,
            chk_sig,
            key_id=chk_key_id,
            merkle_root=chk_merkle_root,
        )
        results.append({
            "checkpoint_id": chk_id,
            "sequence_id": row["sequence_id"],
            "status": "verified" if valid else "invalid_signature",
            "key_id": chk_key_id,
            "merkle_root": chk_merkle_root,
            "valid": valid,
        })
        if not valid:
            all_valid = False

    return all_valid, results

