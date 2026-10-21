"""Shared, boundary-locked signed checkpoint creation."""

from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.cli.checkpoint_store import compute_checkpoint_hash
from db.cli.keygen import load_private_key
from db.cli.merkle_tree import ArgusMerkleTree
from db.cli.signer import LocalFileSigner

from ..config import get_settings
from ..models.security_audit_event import SecurityAuditEvent

CHECKPOINT_LOCK_KEY = 514729380123
MAX_CHECKPOINT_EVENTS = 10000
CHECKPOINT_KEY_ID = "local:ed25519:v1"


def load_checkpoint_signer() -> LocalFileSigner:
    """Load the configured signing key, failing closed when unavailable."""
    key_path = Path(get_settings().SIGNING_PRIVATE_KEY_PATH)
    if not key_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Checkpoint signing is unavailable: the configured signing key is missing.",
        )
    try:
        return LocalFileSigner(
            private_key=load_private_key(str(key_path)),
            key_id=CHECKPOINT_KEY_ID,
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Checkpoint signing is unavailable: the configured signing key could not be loaded.",
        ) from exc


async def create_signed_checkpoint(
    session: AsyncSession,
    *,
    actor_user_id: int,
    actor_email: str,
    client_ip: str,
    max_events: int = MAX_CHECKPOINT_EVENTS,
    require_full_interval: bool = False,
    starting_after_sequence: int | None = None,
    replace_checkpoint_id: int | None = None,
    signer_loader=load_checkpoint_signer,
    event_type: str = "CHECKPOINT_CREATED",
) -> dict[str, Any] | None:
    """Seal the next bounded audit interval; return None when it is empty."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": CHECKPOINT_LOCK_KEY},
    )
    await session.execute(text("SELECT argus_private.lock_checkpoint_boundary()"))

    latest_result = await session.execute(
        text("SELECT sequence_id FROM chain_checkpoints ORDER BY sequence_id DESC LIMIT 1")
    )
    latest = latest_result.first()
    last_sequence = (
        int(starting_after_sequence)
        if starting_after_sequence is not None
        else (int(latest[0]) if latest else 0)
    )
    entries_result = await session.execute(
        text(
            "SELECT sequence_id, actor_user_id, employee_id, action, table_name, row_id, "
            "old_value, new_value, severity, entry_hash, previous_hash, created_at "
            "FROM audit_log WHERE sequence_id > :last_sequence "
            "ORDER BY sequence_id ASC LIMIT :max_events"
        ),
        {"last_sequence": last_sequence, "max_events": max_events},
    )
    entries = [dict(row) for row in entries_result.mappings().all()]
    if not entries or (require_full_interval and len(entries) < max_events):
        return None

    signer = signer_loader()
    checkpoint_hash = compute_checkpoint_hash([entry["entry_hash"] for entry in entries])
    merkle_tree = ArgusMerkleTree.build(entries)
    signature = signer.sign(f"{checkpoint_hash}:{merkle_tree.root}".encode("utf-8"))
    end_sequence = int(entries[-1]["sequence_id"])
    checkpoint_values = {
        "sequence_id": end_sequence,
        "checkpoint_hash": checkpoint_hash,
        "signature": signature,
        "key_id": signer.key_id,
        "merkle_root": merkle_tree.root,
        "leaf_count": merkle_tree.leaf_count,
    }
    if replace_checkpoint_id is None:
        stored_result = await session.execute(
            text(
                "INSERT INTO chain_checkpoints "
                "(sequence_id, checkpoint_hash, signature, key_id, merkle_root, merkle_leaf_count) "
                "VALUES (:sequence_id, :checkpoint_hash, :signature, :key_id, :merkle_root, :leaf_count) "
                "RETURNING checkpoint_id, created_at"
            ),
            checkpoint_values,
        )
    else:
        checkpoint_values["checkpoint_id"] = replace_checkpoint_id
        stored_result = await session.execute(
            text(
                "UPDATE chain_checkpoints SET sequence_id = :sequence_id, "
                "checkpoint_hash = :checkpoint_hash, signature = :signature, key_id = :key_id, "
                "merkle_root = :merkle_root, merkle_leaf_count = :leaf_count "
                "WHERE checkpoint_id = :checkpoint_id RETURNING checkpoint_id, created_at"
            ),
            checkpoint_values,
        )
    stored = stored_result.first()
    if stored is None:
        return None

    session.add(SecurityAuditEvent(
        event_type=event_type,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        sequence_id=end_sequence,
        matches_found=len(entries),
        client_ip=client_ip,
    ))
    return {
        "checkpoint_id": int(stored[0]),
        "sequence_id": end_sequence,
        "checkpoint_hash": checkpoint_hash,
        "merkle_root": merkle_tree.root,
        "merkle_leaf_count": merkle_tree.leaf_count,
        "entries_sealed": len(entries),
        "signature_status": "signed",
        "key_id": signer.key_id,
        "created_at": stored[1],
        "external_anchor_created": False,
    }
