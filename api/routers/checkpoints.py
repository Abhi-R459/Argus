"""Authorized on-demand checkpoint creation for HR administrators."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.cli.checkpoint_store import compute_checkpoint_hash
from db.cli.merkle_tree import ArgusMerkleTree
from db.cli.signer import LocalFileSigner
from db.cli.keygen import load_private_key

from ..config import get_settings
from ..dependencies import get_current_user, get_db_session, require_role
from ..models.security_audit_event import SecurityAuditEvent
from ..models.user import User

router = APIRouter(prefix="/checkpoints", tags=["Checkpoints"])
_HR_ADMIN_ONLY = [Depends(require_role(["hr_admin"]))]
_CHECKPOINT_KEY_ID = "local:ed25519:v1"
_CHECKPOINT_LOCK_KEY = 514729380123


def _load_signer() -> LocalFileSigner:
    """Load the configured signing key, failing closed when it is unavailable."""
    settings = get_settings()
    if settings.APP_ENV == "production":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="On-demand signing is unavailable in production until a managed signer is configured.",
        )
    key_path = Path(settings.SIGNING_PRIVATE_KEY_PATH)
    if not key_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Checkpoint signing is unavailable: the configured signing key is missing.",
        )
    try:
        return LocalFileSigner(
            private_key=load_private_key(str(key_path)),
            key_id=_CHECKPOINT_KEY_ID,
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Checkpoint signing is unavailable: the configured signing key could not be loaded.",
        ) from exc


@router.post("/create", dependencies=_HR_ADMIN_ONLY)
async def create_checkpoint_now(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Seal all events since the prior checkpoint and record the requesting HR admin."""
    # Audit triggers take the chain_state row lock before appending events. Taking
    # the same lock freezes the chain boundary until the checkpoint transaction
    # commits and also serializes competing manual checkpoint requests.
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": _CHECKPOINT_LOCK_KEY},
    )
    await session.execute(
        text("SELECT id FROM chain_state WHERE id = 1 FOR UPDATE")
    )
    latest_result = await session.execute(
        text("SELECT sequence_id FROM chain_checkpoints ORDER BY sequence_id DESC LIMIT 1")
    )
    latest = latest_result.first()
    last_checkpoint_sequence = int(latest[0]) if latest else 0

    entries_result = await session.execute(
        text(
            "SELECT sequence_id, actor_user_id, employee_id, action, table_name, row_id, "
            "old_value, new_value, severity, entry_hash, previous_hash, created_at "
            "FROM audit_log WHERE sequence_id > :last_sequence ORDER BY sequence_id ASC"
        ),
        {"last_sequence": last_checkpoint_sequence},
    )
    entries = [dict(row) for row in entries_result.mappings().all()]
    if not entries:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="There are no new audit events to checkpoint.",
        )

    signer = _load_signer()
    checkpoint_hash = compute_checkpoint_hash([entry["entry_hash"] for entry in entries])
    merkle_tree = ArgusMerkleTree.build(entries)
    signature = signer.sign(f"{checkpoint_hash}:{merkle_tree.root}".encode("utf-8"))
    end_sequence = int(entries[-1]["sequence_id"])

    try:
        inserted = await session.execute(
            text(
                "INSERT INTO chain_checkpoints "
                "(sequence_id, checkpoint_hash, signature, key_id, merkle_root, merkle_leaf_count) "
                "VALUES (:sequence_id, :checkpoint_hash, :signature, :key_id, :merkle_root, :leaf_count) "
                "RETURNING checkpoint_id, created_at"
            ),
            {
                "sequence_id": end_sequence,
                "checkpoint_hash": checkpoint_hash,
                "signature": signature,
                "key_id": signer.key_id,
                "merkle_root": merkle_tree.root,
                "leaf_count": merkle_tree.leaf_count,
            },
        )
    except IntegrityError as exc:
        # The uniqueness constraint also protects against a checkpoint daemon
        # that does not participate in this API's advisory-lock protocol.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A checkpoint was created concurrently for the current audit-chain boundary. Refresh and retry if new events remain.",
        ) from exc
    stored = inserted.first()
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A checkpoint already exists at the current audit-chain boundary.",
        )

    session.add(
        SecurityAuditEvent(
            event_type="CHECKPOINT_CREATED",
            actor_user_id=current_user.user_id,
            actor_email=current_user.email,
            sequence_id=end_sequence,
            matches_found=len(entries),
            client_ip=request.client.host if request.client else "unknown",
        )
    )

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
