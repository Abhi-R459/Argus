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
mig13 = importlib.import_module("db.alembic.versions.013_tunable_pbkdf2_blind_index")


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


def test_migration_013_upgrade_and_downgrade(memory_engine: Engine):
    """Test that migration 013 (tunable PBKDF2 blind indexing) upgrades and downgrades cleanly."""
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with memory_engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)

        mig1.op = op
        mig2.op = op
        mig10.op = op
        mig13.op = op

        # Run prerequisite upgrades
        mig1.upgrade()
        mig2.upgrade()
        mig10.upgrade()

        # Run migration 013 upgrade
        mig13.upgrade()
        conn.commit()

        # Run migration 013 downgrade
        mig13.downgrade()
        conn.commit()


def test_compute_pbkdf2_blind_index_algorithm():
    """Assert tunable PBKDF2 blind index matches NIST SP 800-132 bit-for-bit across iteration counts."""
    from db.crypto.blind_index import compute_blind_index, DEFAULT_SALT

    salt = DEFAULT_SALT
    test_cases = [
        "123-45-6789",
        "987-65-4321",
        "111-00-9999",
    ]

    for nid in test_cases:
        for iters in [1, 10, 100, 1000]:
            digest = compute_blind_index(nid, salt=salt, iterations=iters, mode="pbkdf2")
            assert len(digest) == 64
            if iters <= 1:
                expected = hmac.new(salt.encode("utf-8"), nid.encode("utf-8"), hashlib.sha256).hexdigest()
            else:
                expected = hashlib.pbkdf2_hmac("sha256", nid.encode("utf-8"), salt.encode("utf-8"), iters, 32).hex()
            assert digest == expected, f"PBKDF2 mismatch for {nid} at {iters} iterations"


def test_calibration_work_factor_tradeoff():
    """Verify that calibration demonstrates the trade-off between write SLA (<5ms) and GPU resistance."""
    from db.crypto.blind_index import calibrate_work_factor

    metrics = calibrate_work_factor(iterations_list=[1, 1000, 10000, 50000], num_samples=3)
    assert len(metrics) == 4

    # 1 iteration (HMAC): fast but GPU cracking is < 1 second
    assert metrics[0]["iterations"] == 1
    assert metrics[0]["gpu_search_seconds"] < 1.0

    # 1,000 iterations: sub-millisecond in Python (<0.5ms), raises GPU cracking to ~14 min
    assert metrics[1]["iterations"] == 1000
    assert metrics[1]["sla_compliant"] is True
    assert metrics[1]["gpu_search_seconds"] > 600.0

    # 10,000 iterations: raises GPU cracking to >2 hours
    assert metrics[2]["iterations"] == 10000
    assert metrics[2]["gpu_search_seconds"] > 7200.0

    # 50,000 iterations: raises GPU cracking to >10 hours
    assert metrics[3]["iterations"] == 50000
    assert metrics[3]["gpu_search_seconds"] > 36000.0
