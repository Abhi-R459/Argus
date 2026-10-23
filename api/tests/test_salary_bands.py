from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.routers.employees import _validate_salary_band
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.parametrize("amount", [Decimal("300000"), Decimal("1800000")])
def test_salary_band_includes_both_endpoints(amount):
    role = SimpleNamespace(salary_band_min=Decimal("300000"), salary_band_max=Decimal("1800000"))

    _validate_salary_band(amount, role)


@pytest.mark.parametrize("amount", [Decimal("299999.99"), Decimal("1800000.01"), Decimal("2500000")])
def test_salary_band_rejects_amounts_outside_role_band(amount):
    role = SimpleNamespace(salary_band_min=Decimal("300000"), salary_band_max=Decimal("1800000"))

    with pytest.raises(HTTPException) as error:
        _validate_salary_band(amount, role)

    assert error.value.status_code == 422
    assert "annual band" in error.value.detail
    assert "300000" in error.value.detail
    assert "1800000" in error.value.detail


def test_salary_band_migration_guards_all_database_write_paths():
    migration = Path(__file__).parents[2] / "db" / "alembic" / "versions" / "038_enforce_role_salary_bands.py"
    source = migration.read_text(encoding="utf-8")

    assert "BEFORE INSERT OR UPDATE OF employee_id, amount, effective_date ON public.salary_history" in source
    assert "BEFORE UPDATE OF role_id ON public.employees" in source
    assert "BEFORE UPDATE OF salary_band_min, salary_band_max ON public.roles" in source
    assert "USING ERRCODE = '23514', CONSTRAINT = 'salary_within_role_band'" in source
    assert "FOR SHARE" in source


def test_deactivation_migration_preserves_events_and_collapses_duplicate_flags():
    migration = Path(__file__).parents[2] / "db" / "alembic" / "versions" / "039_group_deactivation_burst_flags.py"
    source = migration.read_text(encoding="utf-8")

    assert "superseded_by_flag_id" in source
    assert "UPDATE public.suspicious_activity_flags AS duplicate" in source
    assert "CREATE TEMP TABLE argus_deactivation_flag_groups" in source
    assert "SELECT representatives.sequence_id, 'mass_employee_deactivations'" in source
    assert "DELETE FROM public.suspicious_activity_flags" not in source


@pytest.mark.asyncio
async def test_employee_creation_rejects_salary_above_band(client_hr, mock_db_session):
    role = SimpleNamespace(salary_band_min=Decimal("300000"), salary_band_max=Decimal("1800000"))
    result = MagicMock()
    result.scalar_one_or_none.return_value = role
    mock_db_session.execute.return_value = result

    response = await client_hr.post("/api/employees", json={
        "full_name": "Test Analyst", "email": "analyst@example.com", "role_id": 9,
        "national_id": "TEST-ID", "contact_info": "Test address",
        "date_hired": "2026-10-23", "salary": 2500000,
    })

    assert response.status_code == 422
    assert "annual band" in response.json()["detail"]
    mock_db_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_salary_addition_rejects_salary_above_band(client_hr, mock_db_session):
    employee_result = MagicMock()
    employee_result.scalar_one_or_none.return_value = SimpleNamespace(
        employee_id=7, is_active=True, role_id=9,
    )
    role_result = MagicMock()
    role_result.scalar_one_or_none.return_value = SimpleNamespace(
        salary_band_min=Decimal("300000"), salary_band_max=Decimal("1800000"),
    )
    mock_db_session.execute.side_effect = [employee_result, role_result]

    response = await client_hr.post(
        "/api/employees/7/salary",
        json={"amount": 2500000, "effective_date": "2026-10-23"},
    )

    assert response.status_code == 422
    assert "annual band" in response.json()["detail"]
    mock_db_session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_role_change_rejects_existing_salary_above_target_band(client_hr, mock_db_session):
    employee = SimpleNamespace(
        employee_id=7, full_name="Test Analyst", email="analyst@example.test", role_id=3,
        is_active=True, national_id_encrypted=b"encrypted-id", contact_info_encrypted=b"encrypted-contact",
    )
    employee_result = MagicMock()
    employee_result.scalar_one_or_none.return_value = employee
    role_result = MagicMock()
    role_result.scalar_one_or_none.return_value = SimpleNamespace(
        salary_band_min=Decimal("300000"), salary_band_max=Decimal("1800000"),
    )
    salary_result = MagicMock()
    salary_result.scalar_one_or_none.return_value = Decimal("2500000")
    mock_db_session.execute.side_effect = [employee_result, role_result, salary_result]

    with patch("api.routers.employees.get_settings", return_value=SimpleNamespace(
        PII_ENCRYPTION_KEY="test-key", AUDIT_SALT="unused",
    )), patch("api.routers.employees.decrypt_pii", return_value="TEST-ID"), \
         patch("api.routers.employees._set_employee_pii_audit_context", new_callable=AsyncMock):
        response = await client_hr.patch("/api/employees/7", json={"role_id": 9})

    assert response.status_code == 422
    assert employee.role_id == 3
    mock_db_session.flush.assert_not_awaited()
