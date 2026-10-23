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
from ..models.department import Department
from ..models.hr_undo_action import HrUndoAction
from ..models.role import Role
from ..models.user import User
from ..services.hr_undo import decrypt_snapshot, employee_snapshot, snapshot_hash
from db.crypto.pii import decrypt_pii
from .employees import _set_employee_pii_audit_context

router = APIRouter(prefix="/hr-undo", tags=["HR Undo"], dependencies=[Depends(require_role(["hr_admin"]))])


@router.get("")
async def list_undo_actions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, scope="function"),
):
    result = await session.execute(
        select(HrUndoAction)
        .where(HrUndoAction.actor_user_id == current_user.user_id)
        .order_by(HrUndoAction.action_id.desc())
        .limit(50)
    )
    return [{
        "action_id": item.action_id,
        "employee_id": item.employee_id,
        "action_type": item.action_type,
        "created_at": item.created_at,
        "undone_at": item.undone_at,
    } for item in result.scalars().all()]


@router.get("/{action_id}/preview")
async def preview_hr_undo_action(
    action_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, scope="function"),
):
    """Show the exact employee fields a receipt would restore, without changing data."""
    action = (await session.execute(
        select(HrUndoAction).where(
            HrUndoAction.action_id == action_id,
            HrUndoAction.actor_user_id == current_user.user_id,
        )
    )).scalar_one_or_none()
    if action is None:
        raise HTTPException(404, "Undo action was not found.")
    employee = (await session.execute(
        select(Employee).where(Employee.employee_id == action.employee_id)
    )).scalar_one_or_none()
    if employee is None:
        raise HTTPException(409, "The employee record is no longer available.")

    current = employee_snapshot(employee)
    try:
        if action.action_type == "employee_created":
            restored = {**current, "is_active": False}
        elif action.action_type in {"profile_updated", "employee_deactivated"} and action.before_ciphertext:
            restored = decrypt_snapshot(bytes(action.before_ciphertext))
        else:
            raise ValueError("Unsupported undo receipt")
        # Validate the receipt before showing any proposed values to an HR user.
        for field in ("full_name", "email", "role_id", "is_active", "contact_info_encrypted"):
            if field not in restored:
                raise ValueError("Incomplete undo receipt")
        contact_current = decrypt_pii(
            bytes(employee.contact_info_encrypted), "contact_info", get_settings().PII_ENCRYPTION_KEY
        )
        contact_restored = decrypt_pii(
            base64.b64decode(restored["contact_info_encrypted"], validate=True),
            "contact_info", get_settings().PII_ENCRYPTION_KEY,
        )
    except (ValueError, KeyError, TypeError):
        raise HTTPException(503, "This change cannot be reviewed safely.") from None

    role_names = {}
    if current["role_id"] != restored["role_id"]:
        roles = await session.execute(
            select(Role.role_id, Role.title, Department.name)
            .join(Department, Role.department_id == Department.department_id)
            .where(Role.role_id.in_([current["role_id"], restored["role_id"]]))
        )
        role_names = {row.role_id: f"{row.title} · {row.name}" for row in roles.all()}

    changes = []
    for field, label in (
        ("full_name", "Name"),
        ("email", "Email"),
        ("role_id", "Job role and department"),
        ("is_active", "Status"),
    ):
        if current[field] == restored[field]:
            continue
        if field == "role_id":
            present = role_names.get(current[field], f"Role #{current[field]}")
            previous = role_names.get(restored[field], f"Role #{restored[field]}")
        elif field == "is_active":
            present = "Active" if current[field] else "Deactivated"
            previous = "Active" if restored[field] else "Deactivated"
        else:
            present, previous = current[field], restored[field]
        changes.append({"field": field, "label": label, "current": present, "restored": previous})
    if contact_current != contact_restored:
        changes.append({
            "field": "contact_info", "label": "Contact information",
            "current": contact_current, "restored": contact_restored,
        })

    blocked_reason = None
    if action.undone_at is not None:
        blocked_reason = "This change has already been undone."
    elif snapshot_hash(current) != action.after_hash:
        blocked_reason = "The employee has changed since this action. Review the current record first."
    return {
        "action_id": action.action_id,
        "employee_id": employee.employee_id,
        "employee_name": employee.full_name,
        "action_type": action.action_type,
        "created_at": action.created_at,
        "changes": changes,
        "can_undo": blocked_reason is None,
        "blocked_reason": blocked_reason,
    }


@router.post("/{action_id}/undo")
async def undo_hr_action(
    action_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, scope="function"),
):
    action = (await session.execute(
        select(HrUndoAction).where(
            HrUndoAction.action_id == action_id,
            HrUndoAction.actor_user_id == current_user.user_id,
        ).with_for_update()
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
