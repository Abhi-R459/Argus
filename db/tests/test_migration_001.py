"""Unit tests for Alembic Migration 001: Core Entity Tables."""

import importlib
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine

mig = importlib.import_module("db.alembic.versions.001_core_entity_tables")


@pytest.fixture
def memory_engine():
    """Create in-memory SQLite engine for testing Alembic migration schema structure."""
    engine = create_engine("sqlite:///:memory:")
    return engine


def test_migration_001_upgrade_and_downgrade(memory_engine: Engine):
    """Test that upgrade creates all 5 core tables and downgrade removes them clean."""
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with memory_engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)

        # Inject op into migration module
        mig.op = op

        # Run upgrade
        mig.upgrade()
        conn.commit()

        # Inspect created tables
        inspector = inspect(conn)
        tables = inspector.get_table_names()
        expected_tables = {"departments", "roles", "users", "employees", "salary_history"}
        assert expected_tables.issubset(set(tables)), f"Missing tables: {expected_tables - set(tables)}"

        # Verify departments columns
        dept_cols = {c["name"] for c in inspector.get_columns("departments")}
        assert dept_cols == {"department_id", "name"}

        # Verify roles columns
        role_cols = {c["name"] for c in inspector.get_columns("roles")}
        assert role_cols == {"role_id", "title", "department_id", "salary_band_min", "salary_band_max"}

        # Verify users columns
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        assert user_cols == {"user_id", "clerk_user_id", "full_name", "email", "role", "is_active", "created_at"}

        # Verify employees columns
        emp_cols = {c["name"] for c in inspector.get_columns("employees")}
        assert emp_cols == {"employee_id", "full_name", "email", "role_id", "national_id_encrypted", "contact_info_encrypted", "date_hired", "is_active", "created_at"}

        # Verify salary_history columns
        sal_cols = {c["name"] for c in inspector.get_columns("salary_history")}
        assert sal_cols == {"salary_history_id", "employee_id", "amount", "effective_date", "created_at"}

        # Run downgrade
        mig.downgrade()
        conn.commit()

        # Verify tables dropped
        inspector_after = inspect(conn)
        remaining_tables = inspector_after.get_table_names()
        for t in expected_tables:
            assert t not in remaining_tables, f"Table {t} was not dropped by downgrade()"
