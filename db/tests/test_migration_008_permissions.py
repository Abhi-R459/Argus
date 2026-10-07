from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import MagicMock, patch


MIGRATION_PATH = Path(__file__).parents[1] / "alembic" / "versions" / "008_finalize_permissions.py"
SPEC = spec_from_file_location("migration_008_permissions", MIGRATION_PATH)
MIGRATION = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MIGRATION)


def test_permission_migration_skips_grants_when_application_roles_are_absent():
    bind = MagicMock()
    bind.execute.return_value.scalar_one.return_value = 0

    with patch.object(MIGRATION.op, "get_bind", return_value=bind), patch.object(MIGRATION.op, "execute") as execute:
        MIGRATION.upgrade()

    bind.execute.assert_called_once()
    execute.assert_not_called()


def test_permission_migration_applies_grants_when_both_roles_exist():
    bind = MagicMock()
    bind.execute.return_value.scalar_one.return_value = 2

    with patch.object(MIGRATION.op, "get_bind", return_value=bind), patch.object(MIGRATION.op, "execute") as execute:
        MIGRATION.upgrade()

    assert execute.call_count == 12


def test_hardening_migration_does_not_swallow_missing_role_errors():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "011_audit_log_hardening.py"
    spec = spec_from_file_location("migration_011_hardening", path)
    migration = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)

    bind = MagicMock()
    bind.dialect.name = "postgresql"
    bind.execute.return_value.scalars.return_value.all.return_value = []
    with patch.object(migration.op, "get_bind", return_value=bind), patch.object(migration.op, "execute") as execute:
        migration.upgrade()

    assert execute.call_count == 2
