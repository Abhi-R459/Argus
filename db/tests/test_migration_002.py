"""Unit tests for Alembic Migration 002: Audit & Chain Tables."""

import importlib
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine

mig1 = importlib.import_module("db.alembic.versions.001_core_entity_tables")
mig2 = importlib.import_module("db.alembic.versions.002_audit_chain_tables")


@pytest.fixture
def memory_engine():
    """Create in-memory SQLite engine for testing Alembic migration schema structure."""
    engine = create_engine("sqlite:///:memory:")
    return engine


def test_migration_002_upgrade_and_downgrade(memory_engine: Engine):
    """Test that migration 002 creates all 5 audit and chain tables and downgrade removes them."""
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with memory_engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)

        mig1.op = op
        mig2.op = op

        # Run upgrade 001 and 002
        mig1.upgrade()
        mig2.upgrade()
        conn.commit()

        # Inspect created tables
        inspector = inspect(conn)
        tables = inspector.get_table_names()
        expected_tables = {"audit_log", "suspicious_activity_flags", "chain_state", "chain_checkpoints", "backups"}
        assert expected_tables.issubset(set(tables)), f"Missing tables: {expected_tables - set(tables)}"

        # Check indices on audit_log
        indexes = {idx["name"] for idx in inspector.get_indexes("audit_log")}
        assert "idx_audit_log_seq_time" in indexes
        assert "idx_audit_log_employee_time" in indexes

        # Run downgrade 002
        mig2.downgrade()
        conn.commit()

        # Verify 002 tables dropped
        inspector_after = inspect(conn)
        remaining_tables = inspector_after.get_table_names()
        for t in expected_tables:
            assert t not in remaining_tables, f"Table {t} was not dropped by downgrade()"
