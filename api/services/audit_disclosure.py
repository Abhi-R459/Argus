"""Mask employee data in ordinary auditor ledger views.

The persisted audit row and its hash are never changed. Full payloads are
available only through an explicit, recorded reveal or evidence export.
"""

from typing import Any


_SENSITIVE_FIELDS = frozenset({
    "full_name", "email", "national_id", "national_id_blind_index",
    "national_id_encrypted", "contact_info_encrypted", "contact_info",
    "phone", "phone_number", "contact_number", "address", "amount", "salary",
})
REDACTED = "[REDACTED]"


def redact_audit_payload(table_name: str, payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    def mask(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: REDACTED if key.lower() in _SENSITIVE_FIELDS else mask(item) for key, item in value.items()}
        if isinstance(value, list):
            return [mask(item) for item in value]
        return value

    return mask(payload)
