"""Create short-lived, signed actor assertions for database audit triggers."""

from __future__ import annotations

import hashlib
import hmac
import re
import time
from uuid import uuid4


_HEX_KEY = re.compile(r"^(?:[0-9a-fA-F]{2}){32,}$")
_KEY_ID = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_SUPPORTED_DB_ROLES = {"hr_admin", "compliance_auditor"}
_MAX_TTL_SECONDS = 60


def parse_context_secret(secret_hex: str) -> bytes:
    """Validate a hex-encoded secret containing at least 32 random bytes."""
    if not isinstance(secret_hex, str) or not _HEX_KEY.fullmatch(secret_hex):
        raise ValueError("AUDIT_CONTEXT_SECRET must be at least 64 hexadecimal characters.")
    return bytes.fromhex(secret_hex)


def canonical_actor_payload(
    *,
    key_id: str,
    actor_user_id: int,
    actor_employee_id: int,
    db_role: str,
    nonce: str,
    issued_at: int,
    expires_at: int,
) -> bytes:
    """Serialize fields in one stable format shared with the PostgreSQL verifier."""
    if not _KEY_ID.fullmatch(key_id):
        raise ValueError("AUDIT_CONTEXT_KEY_ID contains unsupported characters.")
    if db_role not in _SUPPORTED_DB_ROLES:
        raise ValueError("Unsupported audit-context database role.")
    if actor_user_id <= 0 or actor_user_id > 2_147_483_647 or actor_employee_id < 0 or actor_employee_id > 2_147_483_647:
        raise ValueError("Audit-context actor identifiers are invalid.")
    if issued_at <= 0 or expires_at <= issued_at or expires_at - issued_at > _MAX_TTL_SECONDS:
        raise ValueError("Audit-context expiry must be within 60 seconds of issue time.")
    return (
        f"argus-actor-context-v1|{key_id}|{actor_user_id}|{actor_employee_id}|"
        f"{db_role}|{nonce}|{issued_at}|{expires_at}"
    ).encode("ascii")


def create_actor_context(
    *,
    actor_user_id: int,
    actor_employee_id: int | None,
    db_role: str,
    secret_hex: str,
    key_id: str = "v1",
    now: int | None = None,
) -> dict[str, str]:
    """Create an assertion suitable for transaction-local PostgreSQL settings."""
    key = parse_context_secret(secret_hex)
    issued_at = int(time.time()) if now is None else int(now)
    expires_at = issued_at + 30
    nonce = str(uuid4())
    employee_id = int(actor_employee_id or 0)
    payload = canonical_actor_payload(
        key_id=key_id,
        actor_user_id=int(actor_user_id),
        actor_employee_id=employee_id,
        db_role=db_role,
        nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    signature = hmac.new(key, payload, hashlib.sha256).hexdigest()
    return {
        "version": "1",
        "key_id": key_id,
        "actor_user_id": str(int(actor_user_id)),
        "actor_employee_id": str(employee_id),
        "db_role": db_role,
        "nonce": nonce,
        "issued_at": str(issued_at),
        "expires_at": str(expires_at),
        "signature": signature,
    }
