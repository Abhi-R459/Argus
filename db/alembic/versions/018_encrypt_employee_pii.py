"""Encrypt legacy employee PII byte columns and version the audit blind index.

Revision ID: 018_encrypt_employee_pii
Revises: 017_auditor_dir_pii_isolation
"""

from __future__ import annotations

import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from db.crypto.blind_index import compute_blind_index
from db.crypto.pii import (
    InvalidPiiEnvelope,
    decrypt_pii,
    encrypt_pii,
    is_encrypted_pii,
)


revision: str = "018_encrypt_employee_pii"
down_revision: Union[str, None] = "017_auditor_dir_pii_isolation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_MASK_EMPLOYEE_PAYLOAD = r"""
CREATE OR REPLACE FUNCTION public.mask_employee_payload(p_payload JSONB)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
AS $func$
DECLARE
    v_salt TEXT;
    v_raw_nid TEXT;
    v_blind_index TEXT := NULL;
    v_supplied_blind_index TEXT;
    v_iters_str TEXT;
    v_iters INT := 1000;
BEGIN
    v_salt := current_setting('argus.audit_salt', true);
    IF v_salt IS NULL OR v_salt = '' THEN
        RAISE EXCEPTION 'AUDIT_SALT must be configured for employee audit writes';
    END IF;

    v_iters_str := current_setting('argus.blind_index_iterations', true);
    IF v_iters_str IS NOT NULL AND v_iters_str <> '' THEN
        BEGIN
            v_iters := v_iters_str::INT;
        EXCEPTION WHEN OTHERS THEN
            v_iters := 1000;
        END;
    END IF;
    IF v_iters IS NULL OR v_iters < 1 THEN
        v_iters := 1000;
    END IF;

    v_supplied_blind_index := current_setting('argus.employee_national_id_blind_index', true);
    IF v_supplied_blind_index ~ '^[0-9a-f]{64}$' THEN
        v_blind_index := v_supplied_blind_index;
    END IF;

    IF p_payload ? 'national_id' AND p_payload->>'national_id' IS NOT NULL AND p_payload->>'national_id' <> '[REDACTED]' THEN
        v_raw_nid := p_payload->>'national_id';
    ELSIF p_payload ? 'national_id_encrypted' AND p_payload->>'national_id_encrypted' LIKE '\x%' THEN
        BEGIN
            v_raw_nid := convert_from(decode(substring(p_payload->>'national_id_encrypted' from 3), 'hex'), 'UTF8');
        EXCEPTION WHEN OTHERS THEN
            v_raw_nid := NULL;
        END;
    END IF;

    IF v_blind_index IS NULL AND v_raw_nid IS NOT NULL AND v_raw_nid <> '' THEN
        v_blind_index := compute_blind_index(v_raw_nid, v_salt, v_iters);
    END IF;

    p_payload := p_payload - 'national_id_encrypted' - 'contact_info_encrypted' - 'national_id' - 'contact_info';
    p_payload := p_payload
        || jsonb_build_object('national_id_encrypted', '[REDACTED]')
        || jsonb_build_object('contact_info_encrypted', '[REDACTED]');
    IF v_blind_index IS NOT NULL THEN
        p_payload := p_payload || jsonb_build_object('national_id_blind_index', v_blind_index);
    END IF;
    RETURN p_payload;
END;
$func$;
"""


def _encoded_pii(value: bytes, field: str, key: str, employee_id: int) -> tuple[bytes, str]:
    if is_encrypted_pii(value):
        try:
            plaintext = decrypt_pii(value, field, key)
        except (InvalidPiiEnvelope, ValueError) as exc:
            raise RuntimeError(
                f"Cannot validate existing encrypted {field} for employee {employee_id}; migration stopped."
            ) from exc
        return value, plaintext

    try:
        plaintext = value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError(
            f"Legacy {field} for employee {employee_id} is not UTF-8; migration stopped without changing it."
        ) from exc
    return encrypt_pii(plaintext, field, key), plaintext


def upgrade() -> None:
    """Encrypt existing plaintext rows transactionally, preserving blind indexes."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    key = os.environ.get("PII_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("Set PII_ENCRYPTION_KEY before running this migration.")
    # Validate key format before taking locks or reading employee data.
    encrypt_pii("migration-key-check", "contact_info", key)

    salt = os.environ.get("AUDIT_SALT")
    if not salt or len(salt.encode("utf-8")) < 32:
        raise RuntimeError("Set AUDIT_SALT to at least 32 bytes of unique random data before this migration.")
    mode = os.environ.get("BLIND_INDEX_MODE", "pbkdf2")
    try:
        iterations = int(os.environ.get("BLIND_INDEX_ITERATIONS", "1000"))
    except ValueError as exc:
        raise RuntimeError("BLIND_INDEX_ITERATIONS must be an integer.") from exc
    trigger_iterations = 1 if mode == "hmac" else iterations

    bind = op.get_bind()
    bind.execute(sa.text(_MASK_EMPLOYEE_PAYLOAD))
    # The national-ID immutability rule is temporarily removed within this
    # migration transaction so legacy values can be re-enveloped atomically.
    bind.execute(sa.text("DROP TRIGGER IF EXISTS trg_employees_national_id_immutable ON employees"))
    # Re-encrypting storage is a maintenance transformation, not a user edit.
    # The audit trigger would attribute it to actor 0 and can violate the actor
    # foreign key in a clean database. The transactional migration itself is
    # the record of this operation; restore the trigger before commit.
    bind.execute(sa.text("ALTER TABLE employees DISABLE TRIGGER trg_employees_hash_chain"))

    last_id = 0
    while True:
        rows = bind.execute(
            sa.text(
                "SELECT employee_id, national_id_encrypted, contact_info_encrypted "
                "FROM employees WHERE employee_id > :last_id ORDER BY employee_id LIMIT 500"
            ),
            {"last_id": last_id},
        ).mappings().all()
        if not rows:
            break

        for row in rows:
            employee_id = int(row["employee_id"])
            national_id_envelope, national_id = _encoded_pii(
                bytes(row["national_id_encrypted"]), "national_id", key, employee_id
            )
            contact_info_envelope, _ = _encoded_pii(
                bytes(row["contact_info_encrypted"]), "contact_info", key, employee_id
            )
            blind_index = compute_blind_index(
                national_id,
                salt=salt,
                iterations=iterations,
                mode=mode,
            )
            bind.execute(
                sa.text(
                    "SELECT set_config('argus.audit_salt', :salt, true), "
                    "set_config('argus.blind_index_iterations', :iterations, true), "
                    "set_config('argus.employee_national_id_blind_index', :blind_index, true)"
                ),
                {
                    "salt": salt,
                    "iterations": str(trigger_iterations),
                    "blind_index": blind_index,
                },
            )
            bind.execute(
                sa.text(
                    "UPDATE employees SET national_id_encrypted = :national_id, "
                    "contact_info_encrypted = :contact_info WHERE employee_id = :employee_id"
                ),
                {
                    "national_id": national_id_envelope,
                    "contact_info": contact_info_envelope,
                    "employee_id": employee_id,
                },
            )
            last_id = employee_id

    bind.execute(sa.text("ALTER TABLE employees ENABLE TRIGGER trg_employees_hash_chain"))
    bind.execute(sa.text("""
        CREATE TRIGGER trg_employees_national_id_immutable
            BEFORE UPDATE ON employees
            FOR EACH ROW
            EXECUTE FUNCTION trg_employees_national_id_immutable_fn()
    """))


def downgrade() -> None:
    """Keep the encrypted data format; reverting to plaintext is unsafe."""
    raise RuntimeError(
        "PII envelope migration is intentionally irreversible. Restore the prior application only after a planned re-encryption procedure."
    )
