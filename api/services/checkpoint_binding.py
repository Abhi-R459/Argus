"""Verify that signed checkpoint commitments cover the current audit rows."""

from __future__ import annotations

from dataclasses import dataclass

import psycopg2.extras

from db.cli.checkpoint_store import compute_checkpoint_hash
from db.cli.merkle_tree import ArgusMerkleTree


@dataclass(frozen=True)
class BindingResult:
    status: str  # pass | fail | unknown
    detail: str
    sequence_id: int | None = None


def verify_checkpoint_bindings(conn) -> BindingResult:
    """Rebuild each checkpoint's hash and Merkle root from its audit interval.

    The caller must use one repeatable-read snapshot for its chain walk and this
    function. Missing legacy Merkle evidence is unknown, never a false pass.
    """
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT checkpoint_id, sequence_id, checkpoint_hash, merkle_root, "
            "merkle_leaf_count FROM chain_checkpoints ORDER BY sequence_id"
        )
        checkpoints = cursor.fetchall()
    if not checkpoints:
        return BindingResult("unknown", "No checkpoint exists to bind to audit events.")

    previous_sequence = 0
    legacy_evidence = False
    for checkpoint_id, sequence_id, checkpoint_hash, merkle_root, leaf_count in checkpoints:
        sequence_id = int(sequence_id)
        if sequence_id <= previous_sequence:
            return BindingResult("fail", "Checkpoint sequence boundaries are invalid.", sequence_id)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                "SELECT sequence_id, actor_user_id, employee_id, action, table_name, row_id, "
                "old_value, new_value, severity, entry_hash, previous_hash, created_at "
                "FROM audit_log WHERE sequence_id > %s AND sequence_id <= %s "
                "ORDER BY sequence_id",
                (previous_sequence, sequence_id),
            )
            records = [dict(row) for row in cursor.fetchall()]
        if not records or int(records[-1]["sequence_id"]) != sequence_id:
            return BindingResult(
                "fail", f"Audit events sealed by checkpoint {checkpoint_id} are missing.",
                sequence_id,
            )
        actual_hash = compute_checkpoint_hash([record["entry_hash"] for record in records])
        if actual_hash != checkpoint_hash:
            return BindingResult(
                "fail", f"Audit events do not match checkpoint {checkpoint_id}'s signed hash.",
                sequence_id,
            )
        if merkle_root is None or leaf_count is None:
            legacy_evidence = True
        elif len(records) != int(leaf_count) or ArgusMerkleTree.build(records).root != merkle_root:
            return BindingResult(
                "fail", f"Audit events do not match checkpoint {checkpoint_id}'s Merkle root.",
                sequence_id,
            )
        previous_sequence = sequence_id
    if legacy_evidence:
        return BindingResult("unknown", "Some historical checkpoints lack Merkle evidence.")
    return BindingResult("pass", "All signed checkpoint commitments match their audit events.")
