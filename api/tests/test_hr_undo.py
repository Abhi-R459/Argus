import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.hr_undo import employee_snapshot, encrypt_snapshot, decrypt_snapshot, snapshot_hash
from db.crypto.pii import encrypt_pii


KEY = base64.urlsafe_b64encode(b"0123456789abcdef0123456789abcdef").decode("ascii")


def _employee():
    return SimpleNamespace(
        employee_id=7, full_name="Current Name", email="current@example.test",
        role_id=2, is_active=False,
        national_id_encrypted=encrypt_pii("TEST-ID-7", "national_id", KEY),
        contact_info_encrypted=encrypt_pii("Current contact", "contact_info", KEY),
    )


def test_undo_snapshot_is_encrypted_and_authenticated():
    before = employee_snapshot(_employee())
    with patch("api.services.hr_undo.get_settings", return_value=SimpleNamespace(PII_ENCRYPTION_KEY=KEY)):
        encrypted = encrypt_snapshot(before)
        assert b"current@example.test" not in encrypted
        assert decrypt_snapshot(encrypted) == before
        altered = bytearray(encrypted)
        altered[-1] ^= 1
        with pytest.raises(ValueError):
            decrypt_snapshot(bytes(altered))


@pytest.mark.asyncio
async def test_undo_rejects_later_employee_change(client_hr, mock_db_session):
    employee = _employee()
    action = SimpleNamespace(
        action_id=3, employee_id=7, action_type="employee_deactivated",
        before_ciphertext=b"opaque", after_hash="0" * 64, undone_at=None,
    )
    action_result = MagicMock(); action_result.scalar_one_or_none.return_value = action
    employee_result = MagicMock(); employee_result.scalar_one_or_none.return_value = employee
    mock_db_session.execute.side_effect = [action_result, employee_result]

    response = await client_hr.post("/api/hr-undo/3/undo")
    assert response.status_code == 409
    assert employee.is_active is False
    mock_db_session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_undo_preview_shows_values_without_writing(client_hr, mock_db_session):
    employee = _employee()
    before = {**employee_snapshot(employee), "full_name": "Prior Name", "is_active": True}
    with patch("api.services.hr_undo.get_settings", return_value=SimpleNamespace(PII_ENCRYPTION_KEY=KEY)):
        ciphertext = encrypt_snapshot(before)
    action = SimpleNamespace(
        action_id=3, employee_id=7, action_type="employee_deactivated",
        before_ciphertext=ciphertext, after_hash=snapshot_hash(employee_snapshot(employee)),
        undone_at=None, created_at="2026-10-22T08:18:07Z",
    )
    action_result = MagicMock(); action_result.scalar_one_or_none.return_value = action
    employee_result = MagicMock(); employee_result.scalar_one_or_none.return_value = employee
    mock_db_session.execute.side_effect = [action_result, employee_result]

    with patch("api.routers.hr_undo.get_settings", return_value=SimpleNamespace(PII_ENCRYPTION_KEY=KEY)), \
         patch("api.services.hr_undo.get_settings", return_value=SimpleNamespace(PII_ENCRYPTION_KEY=KEY)):
        response = await client_hr.get("/api/hr-undo/3/preview")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["can_undo"] is True
    assert body["changes"] == [
        {"field": "full_name", "label": "Name", "current": "Current Name", "restored": "Prior Name"},
        {"field": "is_active", "label": "Status", "current": "Deactivated", "restored": "Active"},
    ]
    assert employee.full_name == "Current Name"
    assert employee.is_active is False
    mock_db_session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_undo_preview_blocks_stale_change(client_hr, mock_db_session):
    employee = _employee()
    before = {**employee_snapshot(employee), "full_name": "Prior Name"}
    with patch("api.services.hr_undo.get_settings", return_value=SimpleNamespace(PII_ENCRYPTION_KEY=KEY)):
        ciphertext = encrypt_snapshot(before)
    action = SimpleNamespace(
        action_id=3, employee_id=7, action_type="profile_updated",
        before_ciphertext=ciphertext, after_hash="0" * 64,
        undone_at=None, created_at="2026-10-22T08:18:07Z",
    )
    action_result = MagicMock(); action_result.scalar_one_or_none.return_value = action
    employee_result = MagicMock(); employee_result.scalar_one_or_none.return_value = employee
    mock_db_session.execute.side_effect = [action_result, employee_result]

    with patch("api.routers.hr_undo.get_settings", return_value=SimpleNamespace(PII_ENCRYPTION_KEY=KEY)), \
         patch("api.services.hr_undo.get_settings", return_value=SimpleNamespace(PII_ENCRYPTION_KEY=KEY)):
        response = await client_hr.get("/api/hr-undo/3/preview")

    assert response.status_code == 200, response.text
    assert response.json()["can_undo"] is False
    assert "changed since" in response.json()["blocked_reason"]
    mock_db_session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_undo_preview_resolves_job_role_and_contact_changes(client_hr, mock_db_session):
    employee = _employee()
    before = {
        **employee_snapshot(employee),
        "role_id": 1,
        "contact_info_encrypted": base64.b64encode(
            encrypt_pii("Previous contact", "contact_info", KEY)
        ).decode("ascii"),
    }
    with patch("api.services.hr_undo.get_settings", return_value=SimpleNamespace(PII_ENCRYPTION_KEY=KEY)):
        ciphertext = encrypt_snapshot(before)
    action = SimpleNamespace(
        action_id=3, employee_id=7, action_type="profile_updated",
        before_ciphertext=ciphertext, after_hash=snapshot_hash(employee_snapshot(employee)),
        undone_at=None, created_at="2026-10-22T08:18:07Z",
    )
    action_result = MagicMock(); action_result.scalar_one_or_none.return_value = action
    employee_result = MagicMock(); employee_result.scalar_one_or_none.return_value = employee
    roles_result = MagicMock()
    roles_result.all.return_value = [
        SimpleNamespace(role_id=2, title="Analyst", name="Engineering"),
        SimpleNamespace(role_id=1, title="Coordinator", name="People"),
    ]
    mock_db_session.execute.side_effect = [action_result, employee_result, roles_result]

    with patch("api.routers.hr_undo.get_settings", return_value=SimpleNamespace(PII_ENCRYPTION_KEY=KEY)), \
         patch("api.services.hr_undo.get_settings", return_value=SimpleNamespace(PII_ENCRYPTION_KEY=KEY)):
        response = await client_hr.get("/api/hr-undo/3/preview")

    assert response.status_code == 200, response.text
    assert response.json()["changes"] == [
        {
            "field": "role_id", "label": "Job role and department",
            "current": "Analyst · Engineering", "restored": "Coordinator · People",
        },
        {
            "field": "contact_info", "label": "Contact information",
            "current": "Current contact", "restored": "Previous contact",
        },
    ]
    mock_db_session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_undo_restores_employee_and_keeps_receipt(client_hr, mock_db_session):
    employee = _employee()
    before = {**employee_snapshot(employee), "full_name": "Prior Name", "is_active": True}
    with patch("api.services.hr_undo.get_settings", return_value=SimpleNamespace(PII_ENCRYPTION_KEY=KEY)):
        ciphertext = encrypt_snapshot(before)
    action = SimpleNamespace(
        action_id=3, employee_id=7, action_type="employee_deactivated",
        before_ciphertext=ciphertext, after_hash=snapshot_hash(employee_snapshot(employee)),
        undone_at=None, undone_by_user_id=None,
    )
    action_result = MagicMock(); action_result.scalar_one_or_none.return_value = action
    employee_result = MagicMock(); employee_result.scalar_one_or_none.return_value = employee
    mock_db_session.execute.side_effect = [action_result, employee_result]

    with patch("api.routers.hr_undo.get_settings", return_value=SimpleNamespace(PII_ENCRYPTION_KEY=KEY)), \
         patch("api.services.hr_undo.get_settings", return_value=SimpleNamespace(PII_ENCRYPTION_KEY=KEY)), \
         patch("api.routers.hr_undo._set_employee_pii_audit_context", new_callable=AsyncMock):
        response = await client_hr.post("/api/hr-undo/3/undo")

    assert response.status_code == 200, response.text
    assert employee.full_name == "Prior Name"
    assert employee.is_active is True
    assert action.undone_by_user_id == 1
    assert action.undone_at is not None
    mock_db_session.flush.assert_awaited_once()
