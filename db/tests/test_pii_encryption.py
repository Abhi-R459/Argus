"""Focused tests for employee PII envelope encryption."""

import base64

import pytest

from db.crypto.pii import (
    InvalidPiiEnvelope,
    LegacyPlaintextPiiError,
    decrypt_pii,
    encrypt_pii,
    is_encrypted_pii,
    prepare_employee_pii,
)
from db.crypto.blind_index import compute_blind_index


TEST_KEY = base64.urlsafe_b64encode(b"0123456789abcdef0123456789abcdef").decode("ascii")


def test_encrypts_with_random_nonce_and_decrypts_with_field_binding():
    plaintext = "person@example.test"

    first = encrypt_pii(plaintext, "contact_info", TEST_KEY)
    second = encrypt_pii(plaintext, "contact_info", TEST_KEY)

    assert first != second
    assert plaintext.encode() not in first
    assert decrypt_pii(first, "contact_info", TEST_KEY) == plaintext
    with pytest.raises(InvalidPiiEnvelope):
        decrypt_pii(first, "national_id", TEST_KEY)


def test_rejects_legacy_plaintext_instead_of_returning_it_as_decrypted():
    with pytest.raises(LegacyPlaintextPiiError):
        decrypt_pii(b"legacy plaintext national id", "national_id", TEST_KEY)


@pytest.mark.parametrize("key", ["", "not-base64", base64.urlsafe_b64encode(b"short").decode()])
def test_requires_valid_external_256_bit_key(key):
    with pytest.raises(ValueError, match="PII_ENCRYPTION_KEY"):
        encrypt_pii("sensitive", "national_id", key)


def test_requires_environment_key_when_no_explicit_key_is_passed(monkeypatch):
    monkeypatch.delenv("PII_ENCRYPTION_KEY", raising=False)
    with pytest.raises(ValueError, match="PII_ENCRYPTION_KEY"):
        encrypt_pii("sensitive", "national_id")


class RecordingCursor:
    def __init__(self):
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))


def test_prepare_employee_pii_encrypts_both_values_and_sets_matching_audit_context(monkeypatch):
    monkeypatch.setenv("PII_ENCRYPTION_KEY", TEST_KEY)
    audit_salt = "configured-audit-salt-with-minimum-length"
    monkeypatch.setenv("AUDIT_SALT", audit_salt)
    monkeypatch.setenv("BLIND_INDEX_ITERATIONS", "1200")
    monkeypatch.setenv("BLIND_INDEX_MODE", "pbkdf2")
    cursor = RecordingCursor()

    national_id = "NID-TEST-998"
    contact = "Private contact"
    encrypted_nid, encrypted_contact = prepare_employee_pii(cursor, national_id, contact)

    assert is_encrypted_pii(encrypted_nid)
    assert is_encrypted_pii(encrypted_contact)
    assert national_id.encode() not in encrypted_nid
    assert contact.encode() not in encrypted_contact
    assert decrypt_pii(encrypted_nid, "national_id", TEST_KEY) == national_id
    assert decrypt_pii(encrypted_contact, "contact_info", TEST_KEY) == contact
    assert len(cursor.calls) == 1
    query, params = cursor.calls[0]
    assert "argus.employee_national_id_blind_index" in query
    assert params == (
        audit_salt,
        "1200",
        compute_blind_index(national_id, audit_salt, 1200),
    )


@pytest.mark.parametrize("key", [None, "malformed"])
def test_prepare_employee_pii_fails_before_database_context_when_key_is_missing_or_invalid(monkeypatch, key):
    monkeypatch.delenv("PII_ENCRYPTION_KEY", raising=False)
    cursor = RecordingCursor()

    with pytest.raises(ValueError, match="PII_ENCRYPTION_KEY"):
        prepare_employee_pii(cursor, "NID-TEST-998", "Private contact", key)

    assert cursor.calls == []


def test_prepare_employee_pii_rejects_invalid_blind_index_configuration(monkeypatch):
    monkeypatch.setenv("PII_ENCRYPTION_KEY", TEST_KEY)
    monkeypatch.setenv("AUDIT_SALT", "test-blind-index-salt-is-at-least-32-bytes")
    monkeypatch.setenv("BLIND_INDEX_MODE", "unknown")
    cursor = RecordingCursor()

    with pytest.raises(ValueError, match="BLIND_INDEX_MODE"):
        prepare_employee_pii(cursor, "NID-TEST-998", "Private contact")

    assert cursor.calls == []


def test_prepare_employee_pii_requires_unique_audit_salt_before_database_context(monkeypatch):
    monkeypatch.setenv("PII_ENCRYPTION_KEY", TEST_KEY)
    monkeypatch.setenv("AUDIT_SALT", "short")
    cursor = RecordingCursor()

    with pytest.raises(ValueError, match="AUDIT_SALT"):
        prepare_employee_pii(cursor, "NID-TEST-998", "Private contact")

    assert cursor.calls == []


def test_encryption_migration_suppresses_user_audit_for_storage_only_rewrite():
    from pathlib import Path

    migration = Path(__file__).parents[1] / "alembic" / "versions" / "018_encrypt_employee_pii.py"
    sql = migration.read_text(encoding="utf-8")
    assert 'ALTER TABLE employees DISABLE TRIGGER trg_employees_hash_chain' in sql
    assert 'ALTER TABLE employees ENABLE TRIGGER trg_employees_hash_chain' in sql
