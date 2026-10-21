"""Compensating HR actions. Audit history is never removed."""

import base64
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..dependencies import get_current_user, get_db_session, require_role
from ..models.employee import Employee
from ..models.hr_undo_action import HrUndoAction
from ..models.user import User
from ..services.hr_undo import decrypt_snapshot, employee_snapshot, snapshot_hash
from db.crypto.pii import decrypt_pii
from .employees import _set_employee_pii_audit_context

router = APIRouter(prefix="/hr-undo", tags=["HR Undo"], dependencies=[Depends(require_role(["hr_admin"]))])


@router.get("")
async def list_undo_actions(
    session: AsyncSession = Depends(get_db_session, scope="function"),
):
    result = await session.execute(
        select(HrUndoAction).order_by(HrUndoAction.action_id.desc()).limit(50)
    )
    return [{
        "action_id": item.action_id,
        "employee_id": item.employee_id,
        "action_type": item.action_type,
        "created_at": item.created_at,
        "undone_at": item.undone_at,
    } for item in result.scalars().all()]


@router.post("/{action_id}/undo")
async def undo_hr_action(
    action_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, scope="function"),
):
    action = (await session.execute(
        select(HrUndoAction).where(HrUndoAction.action_id == action_id).with_for_update()
    )).scalar_one_or_none()
    if action is None:
        raise HTTPException(404, "Undo action was not found.")
    if action.undone_at is not None:
        raise HTTPException(409, "This change has already been undone.")
    employee = (await session.execute(
        select(Employee).where(Employee.employee_id == action.employee_id).with_for_update()
    )).scalar_one_or_none()
    if employee is None:
        raise HTTPException(409, "The employee record is no longer available.")
    if snapshot_hash(employee_snapshot(employee)) != action.after_hash:
        raise HTTPException(409, "The employee has changed since this action. Review the current record first.")

    settings = get_settings()
    try:
        national_id = decrypt_pii(
            bytes(employee.national_id_encrypted), "national_id", settings.PII_ENCRYPTION_KEY
        )
        await _set_employee_pii_audit_context(session, national_id, settings)
        if action.action_type == "employee_created":
            employee.is_active = False
        elif action.action_type in {"profile_updated", "employee_deactivated"} and action.before_ciphertext:
            before = decrypt_snapshot(bytes(action.before_ciphertext))
            employee.full_name = before["full_name"]
            employee.email = before["email"]
            employee.role_id = before["role_id"]
            employee.is_active = before["is_active"]
            employee.contact_info_encrypted = base64.b64decode(
                before["contact_info_encrypted"], validate=True
            )
        else:
            raise ValueError("Unsupported undo receipt")
    except (ValueError, KeyError, TypeError):
        raise HTTPException(503, "This change cannot be restored safely.") from None

    action.undone_at = datetime.now(timezone.utc)
    action.undone_by_user_id = current_user.user_id
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(409, "The previous value now conflicts with another record.") from None
    return {"action_id": action.action_id, "employee_id": employee.employee_id, "status": "undone"}
