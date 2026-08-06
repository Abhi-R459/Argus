"""Checkpoint persistence module for Argus tamper-evident audit trail verification engine.

Provides functions to store, retrieve, and compute signed checkpoints in the
chain_checkpoints table.
"""

from __future__ import annotations

import hashlib
from typing import Any

import psycopg2
import psycopg2.extras


def store_checkpoint(
    conn: Any,
    sequence_id: int,
    checkpoint_hash: str,
    signature: bytes,
) -> bool:
    """Stores a signed checkpoint in the chain_checkpoints table.

    Uses ON CONFLICT (sequence_id) DO NOTHING to ensure idempotency. Commits the
    transaction after inserting.

    Args:
        conn: A psycopg2 database connection object.
        sequence_id: The audit log sequence ID at which the checkpoint is created.
        checkpoint_hash: SHA-256 hash representing the state of the audit chain.
        signature: Cryptographic signature bytes for the checkpoint hash.

    Returns:
        bool: True if a new checkpoint row was inserted, False if a row for the
            sequence_id already existed.

    Raises:
        psycopg2.Error: If a database error occurs.
    """
    query = (
        "INSERT INTO chain_checkpoints (sequence_id, checkpoint_hash, signature) "
        "VALUES (%s, %s, %s) "
        "ON CONFLICT (sequence_id) DO NOTHING"
    )
    try:
        with conn.cursor() as cur:
            cur.execute(query, (sequence_id, checkpoint_hash, signature))
            inserted = cur.rowcount > 0
        conn.commit()
        return inserted
    except Exception:
        conn.rollback()
        raise


def get_checkpoint(conn: Any, checkpoint_id: int) -> dict | None:
    """Retrieves a checkpoint by its primary key (checkpoint_id).

    Args:
        conn: A psycopg2 database connection object.
        checkpoint_id: The unique ID of the checkpoint to retrieve.

    Returns:
        dict | None: Dictionary with keys 'checkpoint_id', 'sequence_id',
            'checkpoint_hash', 'signature', and 'created_at' if found, or
            None if no matching record exists.

    Raises:
        psycopg2.Error: If a database error occurs.
    """
    query = (
        "SELECT checkpoint_id, sequence_id, checkpoint_hash, signature, created_at "
        "FROM chain_checkpoints "
        "WHERE checkpoint_id = %s"
    )
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, (checkpoint_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return dict(row)


def get_checkpoints_in_range(conn: Any, start_seq: int, end_seq: int) -> list[dict]:
    """Retrieves all checkpoints with sequence_id in the specified range.

    Args:
        conn: A psycopg2 database connection object.
        start_seq: The lower bound sequence ID (inclusive).
        end_seq: The upper bound sequence ID (inclusive).

    Returns:
        list[dict]: A list of checkpoint dictionary objects ordered by sequence_id.

    Raises:
        psycopg2.Error: If a database error occurs.
    """
    query = (
        "SELECT checkpoint_id, sequence_id, checkpoint_hash, signature, created_at "
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
