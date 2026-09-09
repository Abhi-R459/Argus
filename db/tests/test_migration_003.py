"""Unit tests for Alembic Migration 003 and chain_lock helper."""

import importlib
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

mig1 = importlib.import_module("db.alembic.versions.001_core_entity_tables")
mig2 = importlib.import_module("db.alembic.versions.002_audit_chain_tables")
mig3 = importlib.import_module("db.alembic.versions.003_chain_state_seed")
from db.cli.chain_lock import chain_lock


@pytest.fixture
def seeded_engine():
    """Create in-memory SQLite engine with migrations 001, 002, 003 applied."""
    engine = create_engine("sqlite:///:memory:")
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)

        mig1.op = op
        mig2.op = op
        mig3.op = op

        mig1.upgrade()
        mig2.upgrade()
        mig3.upgrade()
        conn.commit()

    return engine


def test_chain_state_seed_and_downgrade(seeded_engine: Engine):
    """Verify chain_state contains exactly one seed row and downgrade removes it."""
    with seeded_engine.connect() as conn:
        result = conn.execute(text("SELECT id, tail_hash, tail_sequence_id, last_checkpoint_sequence_id FROM chain_state")).fetchall()
        assert len(result) == 1
        row = result[0]
        assert row.id == 1
        assert row.tail_hash == '0' * 64
        assert row.tail_sequence_id == 0
        assert row.last_checkpoint_sequence_id == 0

        # Test chain_lock context manager execution
        with chain_lock(conn):
            # lock acquired
            pass

    # Test downgrade 003
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with seeded_engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)
        mig3.op = op
        mig3.downgrade()
        conn.commit()

        result_after = conn.execute(text("SELECT COUNT(*) FROM chain_state")).scalar()
        assert result_after == 0
