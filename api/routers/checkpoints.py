"""Authorized on-demand checkpoint creation for HR administrators."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_current_user, get_db_session, require_role
from ..models.user import User
from ..services.checkpoints import create_signed_checkpoint, load_checkpoint_signer

router = APIRouter(prefix="/checkpoints", tags=["Checkpoints"])
_HR_ADMIN_ONLY = [Depends(require_role(["hr_admin"]))]


_load_signer = load_checkpoint_signer


class CheckpointScheduleUpdate(BaseModel):
    enabled: bool
    interval_events: int = Field(ge=1, le=10000)


@router.post("/create", dependencies=_HR_ADMIN_ONLY)
async def create_checkpoint_now(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, scope="function"),
) -> dict[str, Any]:
    """Seal all events since the prior checkpoint and record the requesting HR admin."""
    try:
        result = await create_signed_checkpoint(
            session,
            actor_user_id=current_user.user_id,
            actor_email=current_user.email,
            client_ip=request.client.host if request.client else "unknown",
            signer_loader=_load_signer,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A checkpoint was created concurrently for the current audit-chain boundary. Refresh and retry if new events remain.",
        ) from exc
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="There are no new audit events to checkpoint.",
        )
    return result


@router.get("/schedule", dependencies=_HR_ADMIN_ONLY)
async def get_checkpoint_schedule(
    session: AsyncSession = Depends(get_db_session, scope="function"),
) -> dict[str, Any]:
    result = await session.execute(text(
        "SELECT enabled, interval_events, updated_at "
        "FROM checkpoint_schedule_settings WHERE id = 1"
    ))
    row = result.first()
    if row is None:
        raise HTTPException(status_code=503, detail="Checkpoint schedule settings are unavailable.")
    return {"enabled": bool(row[0]), "interval_events": int(row[1]), "updated_at": row[2]}


@router.put("/schedule", dependencies=_HR_ADMIN_ONLY)
async def update_checkpoint_schedule(
    payload: CheckpointScheduleUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, scope="function"),
) -> dict[str, Any]:
    result = await session.execute(text(
        "UPDATE checkpoint_schedule_settings "
        "SET enabled = :enabled, interval_events = :interval_events, "
        "updated_by = :updated_by, updated_at = now() WHERE id = 1 "
        "RETURNING enabled, interval_events, updated_at"
    ), {
        "enabled": payload.enabled,
        "interval_events": payload.interval_events,
        "updated_by": current_user.user_id,
    })
    row = result.first()
    if row is None:
        raise HTTPException(status_code=503, detail="Checkpoint schedule settings are unavailable.")
    from ..models.security_audit_event import SecurityAuditEvent
    session.add(SecurityAuditEvent(
        event_type=(
            "CHECKPOINT_SCHEDULE_ENABLED" if payload.enabled
            else "CHECKPOINT_SCHEDULE_DISABLED"
        ),
        actor_user_id=current_user.user_id,
        actor_email=current_user.email,
        matches_found=payload.interval_events,
        client_ip=request.client.host if request.client else "unknown",
    ))
    return {"enabled": bool(row[0]), "interval_events": int(row[1]), "updated_at": row[2]}
