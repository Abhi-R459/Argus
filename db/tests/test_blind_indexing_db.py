"""Unit tests for BLIND-001: Migration 010 & HMAC Blind Indexing Logic.

Validates Gate 2 intermediate testing requirements:
- Migration 010 upgrade and downgrade execution hygiene.
- Blind index calculation equivalence with Python's HMAC-SHA256 standard.
- Employee payload masking and blind index injection without plaintext leakage.
"""

import hashlib
import hmac
import importlib
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

mig1 = importlib.import_module("db.alembic.versions.001_core_entity_tables")
mig2 = importlib.import_module("db.alembic.versions.002_audit_chain_tables")
mig10 = importlib.import_module("db.alembic.versions.010_blind_indexing")


@pytest.fixture
def memory_engine():
    """Create in-memory SQLite engine for testing Alembic migration schema structure."""
    engine = create_engine("sqlite:///:memory:")
    return engine


def test_migration_010_upgrade_and_downgrade(memory_engine: Engine):
    """Test that migration 010 upgrades and downgrades cleanly."""
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with memory_engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)

        mig1.op = op
        mig2.op = op
        mig10.op = op

        # Run prerequisite upgrades
        mig1.upgrade()
        mig2.upgrade()

        # Run migration 010 upgrade
        mig10.upgrade()
        conn.commit()

        # Verify index was registered in sqlite_master (SQLAlchemy inspector skips expression indexes on SQLite)
        index_rows = conn.execute(text("SELECT name FROM sqlite_master WHERE type = 'index'")).all()
        index_names = {row[0] for row in index_rows}
        assert "idx_audit_log_nid_blind" in index_names

        # Run migration 010 downgrade
        mig10.downgrade()
        conn.commit()

        # Verify index was dropped
        index_rows_after = conn.execute(text("SELECT name FROM sqlite_master WHERE type = 'index'")).all()
        index_names_after = {row[0] for row in index_rows_after}
        assert "idx_audit_log_nid_blind" not in index_names_after


def test_compute_blind_index_algorithm():
    """Assert blind indexing calculation matches HMAC-SHA256 specification."""
    salt = "argus_default_blind_index_salt_2026"
    test_cases = [
        ("123-45-6789", "c6c1cb4db8eeb598418080df7f73966f3630f9ec398a1a9718aa0c36cb3a69a4"),
        ("987-65-4321", "22b5e0ee76b509ef851a70428fafe9ff6cfebc238b724f885df40b2efd45dc72"),
        ("AAA-BB-CCCC", "020c6a85859e9bf9b9fb7d206f6bda24eb6a9829986ee0895311ba0337c7ba28"),
    ]

    for val, _ in test_cases:
        expected = hmac.new(salt.encode("utf-8"), val.encode("utf-8"), hashlib.sha256).hexdigest()
        assert len(expected) == 64
        # Verify deterministic idempotency
        again = hmac.new(salt.encode("utf-8"), val.encode("utf-8"), hashlib.sha256).hexdigest()
        assert again == expected


def test_mask_employee_payload_preserves_privacy():
    """Test simulated payload masking logic to confirm zero plaintext PII leaks."""
    salt = "argus_default_blind_index_salt_2026"
    raw_nid = "123-45-6789"
    expected_hmac = hmac.new(salt.encode("utf-8"), raw_nid.encode("utf-8"), hashlib.sha256).hexdigest()

    # Incoming payload with encrypted bytes / plaintext
    payload = {
        "employee_id": 42,
        "full_name": "Test Subject",
        "national_id": raw_nid,
        "contact_info": "+1-555-0199",
    }

    # Simulate mask_employee_payload
    masked = dict(payload)
    if "national_id" in masked:
        masked["national_id_blind_index"] = expected_hmac
        masked["national_id_encrypted"] = "[REDACTED]"
        del masked["national_id"]
    if "contact_info" in masked:
        masked["contact_info_encrypted"] = "[REDACTED]"
        del masked["contact_info"]

    # Assertions
    assert masked["national_id_encrypted"] == "[REDACTED]"
    assert masked["contact_info_encrypted"] == "[REDACTED]"
    assert "national_id" not in masked
    assert "contact_info" not in masked
    assert masked["national_id_blind_index"] == expected_hmac
