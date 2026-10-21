"""Encrypted HR undo receipts and optimistic conflict checks."""

import base64
import hashlib
import json

from ..config import get_settings
from ..models.employee import Employee
from ..models.hr_undo_action import HrUndoAction
from db.crypto.pii import encrypt_pii, decrypt_pii


def employee_snapshot(employee: Employee) -> dict:
    return {
        "full_name": employee.full_name,
        "email": employee.email,
        "role_id": employee.role_id,
        "is_active": employee.is_active,
        "contact_info_encrypted": base64.b64encode(bytes(employee.contact_info_encrypted)).decode("ascii"),
    }


def snapshot_hash(snapshot: dict) -> str:
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def encrypt_snapshot(snapshot: dict) -> bytes:
    return encrypt_pii(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")),
        "hr_undo_snapshot",
        get_settings().PII_ENCRYPTION_KEY,
    )


def decrypt_snapshot(ciphertext: bytes) -> dict:
    value = decrypt_pii(ciphertext, "hr_undo_snapshot", get_settings().PII_ENCRYPTION_KEY)
    result = json.loads(value)
    if not isinstance(result, dict):
        raise ValueError("Invalid undo receipt")
    return result


def record_employee_change(session, employee: Employee, before: dict | None, action_type: str, actor_user_id: int) -> None:
    session.add(HrUndoAction(
        employee_id=employee.employee_id,
        action_type=action_type,
        actor_user_id=actor_user_id,
        before_ciphertext=encrypt_snapshot(before) if before else None,
        after_hash=snapshot_hash(employee_snapshot(employee)),
    ))
