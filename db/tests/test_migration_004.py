"""Unit tests for Alembic Migration 004: Views."""

import importlib
import pytest
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine

mig1 = importlib.import_module("db.alembic.versions.001_core_entity_tables")
mig2 = importlib.import_module("db.alembic.versions.002_audit_chain_tables")
mig3 = importlib.import_module("db.alembic.versions.003_chain_state_seed")
mig4 = importlib.import_module("db.alembic.versions.004_views")


@pytest.fixture
def memory_engine():
    """Create in-memory SQLite engine for testing Alembic migration 004 views."""
    engine = create_engine("sqlite:///:memory:")
    return engine


def test_views_creation_and_downgrade(memory_engine: Engine):
    """Verify v_employee_directory and v_compliance_overview exist and drop clean."""
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with memory_engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)

        mig1.op = op
        mig2.op = op
        mig3.op = op
        mig4.op = op

        mig1.upgrade()
        mig2.upgrade()
        mig3.upgrade()
        mig4.upgrade()
        conn.commit()

        # Query views
        res_emp = conn.execute(text("SELECT * FROM v_employee_directory LIMIT 1")).fetchall()
        assert len(res_emp) == 0

        res_comp = conn.execute(text("SELECT * FROM v_compliance_overview LIMIT 1")).fetchall()
        assert len(res_comp) == 0

        # Downgrade 004
        mig4.downgrade()
        conn.commit()

        inspector = inspect(conn)
        view_names = inspector.get_view_names()
        assert "v_employee_directory" not in view_names
        assert "v_compliance_overview" not in view_names
