"""Authenticated encryption for employee PII stored in BYTEA columns."""

from __future__ import annotations

import base64
import binascii
import os
from typing import Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from db.crypto.blind_index import DEFAULT_ITERATIONS, DEFAULT_MODE, compute_blind_index


_MAGIC = b"ARGUS-PII\x01"
_NONCE_SIZE = 12
_TAG_SIZE = 16
_AAD_BY_FIELD = {
    "national_id": b"argus:employees:national_id:v1",
    "contact_info": b"argus:employees:contact_info:v1",
}


class InvalidPiiEnvelope(ValueError):
    """Ciphertext is malformed, has been altered, or cannot be decrypted."""


class LegacyPlaintextPiiError(InvalidPiiEnvelope):
    """A database value is not in the versioned encrypted envelope format."""


def _load_key(key_b64: Optional[str]) -> bytes:
    """Decode the required environment-configured URL-safe Base64 AES-256 key."""
    encoded = key_b64 if key_b64 is not None else os.environ.get("PII_ENCRYPTION_KEY")
    if not encoded:
        raise ValueError("PII_ENCRYPTION_KEY must be configured as URL-safe Base64 for a 32-byte key.")

    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        key = base64.b64decode(padded, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("PII_ENCRYPTION_KEY must be URL-safe Base64 for a 32-byte key.") from exc
    if len(key) != 32:
        raise ValueError("PII_ENCRYPTION_KEY must decode to exactly 32 bytes (AES-256).")
    return key


def _aad(field: str) -> bytes:
    try:
        return _AAD_BY_FIELD[field]
    except KeyError as exc:
        raise ValueError("Unsupported employee PII field.") from exc


def is_encrypted_pii(value: bytes) -> bool:
    """Return whether bytes carry this module's recognized version marker."""
    return isinstance(value, bytes) and value.startswith(_MAGIC)


def require_pii_encryption_key(key_b64: Optional[str] = None) -> None:
    """Fail before database work if the configured AES-256 key is unavailable or invalid."""
    _load_key(key_b64)


def validate_employee_pii_config(key_b64: Optional[str] = None) -> None:
    """Validate encryption and audit-index settings before a writer mutates data."""
    require_pii_encryption_key(key_b64)
    pii_audit_context("preflight")


def validate_audit_salt(salt_value: Optional[str] = None) -> str:
    """Require a deployment-specific salt before creating or searching PII indexes."""
    salt = salt_value if salt_value is not None else os.environ.get("AUDIT_SALT")
    if not salt or len(salt.encode("utf-8")) < 32:
        raise ValueError("AUDIT_SALT must be configured with at least 32 bytes of unique random data.")
    return salt


def pii_audit_context(national_id: str) -> dict[str, str]:
    """Build the same blind-index settings used by the API and SQL audit trigger."""
    salt = validate_audit_salt()
    mode = os.environ.get("BLIND_INDEX_MODE", DEFAULT_MODE).lower()
    try:
        iterations = int(os.environ.get("BLIND_INDEX_ITERATIONS", str(DEFAULT_ITERATIONS)))
    except ValueError as exc:
        raise ValueError("BLIND_INDEX_ITERATIONS must be a positive integer.") from exc
    if iterations < 1:
        raise ValueError("BLIND_INDEX_ITERATIONS must be a positive integer.")
    if mode not in {"pbkdf2", "hmac"}:
        raise ValueError("BLIND_INDEX_MODE must be 'pbkdf2' or 'hmac'.")

    index = compute_blind_index(
        national_id,
        salt=salt,
        iterations=iterations,
        mode=mode,
    )
    trigger_iterations = 1 if mode == "hmac" else iterations
    return {
        "salt": salt,
        "iterations": str(trigger_iterations),
        "blind_index": index,
    }


def prepare_employee_pii(
    cursor,
    national_id: str,
    contact_info: str,
    key_b64: Optional[str] = None,
) -> tuple[bytes, bytes]:
    """Encrypt both employee PII fields and set the row's matching audit context.

    This is for synchronous PostgreSQL writers such as seed and benchmark tools.
    The context must be set immediately before that employee's INSERT because a
    transaction-local single index cannot represent a bulk insert of multiple IDs.
    """
    encrypted_national_id = encrypt_pii(national_id, "national_id", key_b64)
    encrypted_contact_info = encrypt_pii(contact_info, "contact_info", key_b64)
    set_employee_audit_context(cursor, national_id)
    return encrypted_national_id, encrypted_contact_info


def set_employee_audit_context(cursor, national_id: str) -> None:
    """Set the transaction-local blind-index context before any employee DML."""
    context = pii_audit_context(national_id)
    cursor.execute(
        "SELECT set_config('argus.audit_salt', %s, true), "
        "set_config('argus.blind_index_iterations', %s, true), "
        "set_config('argus.employee_national_id_blind_index', %s, true)",
        (context["salt"], context["iterations"], context["blind_index"]),
    )


def encrypt_pii(value: str, field: str, key_b64: Optional[str] = None) -> bytes:
    """Encrypt one string with AES-256-GCM and field-specific associated data.

    The envelope is ``MAGIC || nonce || ciphertext || tag``. A fresh 96-bit
    nonce is generated for every encryption. The external key is never stored
    beside the ciphertext.
    """
    key = _load_key(key_b64)
    aad = _aad(field)
    if not isinstance(value, str):
        raise TypeError("Employee PII values must be strings.")
    nonce = os.urandom(_NONCE_SIZE)
    encrypted = AESGCM(key).encrypt(nonce, value.encode("utf-8"), aad)
    return _MAGIC + nonce + encrypted


def decrypt_pii(value: bytes, field: str, key_b64: Optional[str] = None) -> str:
    """Decrypt an envelope; reject legacy plaintext instead of guessing format."""
    key = _load_key(key_b64)
    aad = _aad(field)
    if not isinstance(value, bytes) or not value.startswith(_MAGIC):
        raise LegacyPlaintextPiiError("Employee PII is not in the supported encrypted envelope format.")
    if len(value) < len(_MAGIC) + _NONCE_SIZE + _TAG_SIZE:
        raise InvalidPiiEnvelope("Employee PII encrypted envelope is malformed.")

    nonce_start = len(_MAGIC)
    nonce = value[nonce_start:nonce_start + _NONCE_SIZE]
    ciphertext = value[nonce_start + _NONCE_SIZE:]
    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, aad)
        return plaintext.decode("utf-8")
    except (InvalidTag, UnicodeDecodeError) as exc:
        raise InvalidPiiEnvelope("Employee PII could not be authenticated or decoded.") from exc
