import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock

pytestmark = pytest.mark.asyncio

async def test_list_employees_hr(client_hr: AsyncClient, mock_db_session: AsyncMock):
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db_session.execute.return_value = mock_result
    
    response = await client_hr.get("/api/employees")
    assert response.status_code == 200

async def test_list_employees_auditor(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db_session.execute.return_value = mock_result
    response = await client_auditor.get("/api/employees")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


async def test_auditor_directory_redacts_pii_by_default(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    from datetime import date
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    row = SimpleNamespace(
        employee_id=31,
        full_name="Private Employee",
        email="private@example.test",
        role_title="Engineer",
        department_name="Engineering",
        salary=125000,
        date_hired=date(2024, 1, 1),
        is_active=True,
    )
    result = MagicMock(); result.all.return_value = [row]
    mock_db_session.scalar.return_value = 1
    mock_db_session.execute.return_value = result

    response = await client_auditor.get("/api/employees")
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["full_name"] == "Employee #31"
    assert item["email"] == "Restricted"
    assert item["salary"] is None
    assert item["pii_redacted"] is True


async def test_auditor_directory_pii_reveal_uses_privileged_pool_and_is_recorded(
    client_auditor: AsyncClient, mock_db_session: AsyncMock
):
    from datetime import date
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    row = SimpleNamespace(
        employee_id=31,
        full_name="Private Employee",
        email="private@example.test",
        role_title="Engineer",
        department_name="Engineering",
        salary=125000,
        date_hired=date(2024, 1, 1),
        is_active=True,
    )
    result = MagicMock(); result.all.return_value = [row]
    privileged_session = AsyncMock()
    privileged_session.__aenter__.return_value = privileged_session
    privileged_session.__aexit__.return_value = None
    privileged_session.scalar.return_value = 1
    privileged_session.execute.return_value = result
    factory = MagicMock(return_value=privileged_session)
    get_factory = MagicMock(return_value=factory)

    with patch("api.routers.employees.get_session_factory", get_factory):
        response = await client_auditor.get("/api/employees?include_pii=true")
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["full_name"] == "Private Employee"
    assert item["email"] == "private@example.test"
    get_factory.assert_called_once_with("hr_admin")
    factory.assert_called_once_with()
    privileged_session.execute.assert_awaited()
    event = mock_db_session.add.call_args.args[0]
    assert event.event_type == "DIRECTORY_PII_REVEAL"


async def test_auditor_directory_view_is_pii_shielded_by_migration():
    from pathlib import Path

    migration = Path(__file__).parents[2] / "db" / "alembic" / "versions" / "017_auditor_directory_pii_isolation.py"
    sql = migration.read_text(encoding="utf-8").lower()
    assert "revoke select on public.v_employee_directory from compliance_auditor" in sql
    assert "grant select on public.v_compliance_employee_directory to compliance_auditor" in sql
    view_ddl = sql.split("create view public.v_compliance_employee_directory", 1)[1].split(";", 1)[0]
    assert "e.full_name" not in view_ddl
    assert "e.email" not in view_ddl
    assert "employee #" in view_ddl

async def test_create_employee_hr(client_hr: AsyncClient, mock_db_session: AsyncMock):
    import base64
    from types import SimpleNamespace
    from unittest.mock import patch

    # Setup mock
    mock_employee = AsyncMock()
    mock_employee.employee_id = 2
    mock_employee.full_name = "Bob"
    mock_employee.email = "bob@argus.test"
    mock_employee.role_id = 1
    mock_employee.date_hired = "2026-08-24"
    mock_employee.is_active = True
    
    # We mock the database role and email queries
    from unittest.mock import MagicMock
    mock_role_res = MagicMock()
    mock_role_res.scalar_one_or_none.return_value = MagicMock()
    mock_email_res = MagicMock()
    mock_email_res.scalar_one_or_none.return_value = None
    # The employee path also sets the transaction-local blind-index context
    # consumed by the audit trigger.
    mock_db_session.execute.side_effect = [mock_role_res, mock_email_res, MagicMock()]
    
    payload = {
        "full_name": "Bob",
        "email": "bob@argus-app.com",
        "role_id": 1,
        "national_id": "SSN-123",
        "contact_info": "123 Main St",
        "date_hired": "2026-08-24",
        "salary": 120000
    }
    
    key = base64.urlsafe_b64encode(b"0123456789abcdef0123456789abcdef").decode("ascii")
    with patch("api.routers.employees.get_settings", return_value=SimpleNamespace(
        PII_ENCRYPTION_KEY=key,
        AUDIT_SALT="test-salt-is-at-least-thirty-two-bytes",
        BLIND_INDEX_ITERATIONS=1000,
        BLIND_INDEX_MODE="pbkdf2",
    )):
        response = await client_hr.post("/api/employees", json=payload)

    assert response.status_code == 201, response.text
    assert mock_db_session.add.call_count == 2


async def test_create_employee_encrypts_sensitive_fields(client_hr: AsyncClient, mock_db_session: AsyncMock):
    import base64
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    from db.crypto.pii import decrypt_pii, is_encrypted_pii

    key = base64.urlsafe_b64encode(b"0123456789abcdef0123456789abcdef").decode("ascii")
    role_result = MagicMock(); role_result.scalar_one_or_none.return_value = MagicMock()
    email_result = MagicMock(); email_result.scalar_one_or_none.return_value = None
    mock_db_session.execute.side_effect = [role_result, email_result, MagicMock()]
    payload = {
        "full_name": "Private Person", "email": "pii@argus-app.com", "role_id": 1,
        "national_id": "NID-TEST-123", "contact_info": "Private address",
        "date_hired": "2026-08-24", "salary": 120000,
    }

    with patch("api.routers.employees.get_settings", return_value=SimpleNamespace(
        PII_ENCRYPTION_KEY=key, AUDIT_SALT="test-salt-is-at-least-thirty-two-bytes", BLIND_INDEX_ITERATIONS=1000,
        BLIND_INDEX_MODE="pbkdf2",
    )):
        response = await client_hr.post("/api/employees", json=payload)

    assert response.status_code == 201, response.text
    employee = mock_db_session.add.call_args_list[0].args[0]
    assert is_encrypted_pii(employee.national_id_encrypted)
    assert is_encrypted_pii(employee.contact_info_encrypted)
    assert payload["national_id"].encode() not in employee.national_id_encrypted
    assert payload["contact_info"].encode() not in employee.contact_info_encrypted
    assert decrypt_pii(employee.national_id_encrypted, "national_id", key) == payload["national_id"]
    assert decrypt_pii(employee.contact_info_encrypted, "contact_info", key) == payload["contact_info"]


async def test_create_employee_fails_closed_without_valid_pii_key(client_hr: AsyncClient, mock_db_session: AsyncMock):
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    role_result = MagicMock(); role_result.scalar_one_or_none.return_value = MagicMock()
    email_result = MagicMock(); email_result.scalar_one_or_none.return_value = None
    mock_db_session.execute.side_effect = [role_result, email_result]
    payload = {
        "full_name": "Private Person", "email": "pii@argus-app.com", "role_id": 1,
        "national_id": "NID-TEST-123", "contact_info": "Private address",
        "date_hired": "2026-08-24", "salary": 120000,
    }

    with patch("api.routers.employees.get_settings", return_value=SimpleNamespace(
        PII_ENCRYPTION_KEY="invalid-key", AUDIT_SALT="test-salt-is-at-least-thirty-two-bytes", BLIND_INDEX_ITERATIONS=1000,
        BLIND_INDEX_MODE="pbkdf2",
    )):
        response = await client_hr.post("/api/employees", json=payload)

    assert response.status_code == 503
    mock_db_session.add.assert_not_called()


async def test_create_employee_fails_closed_without_unique_audit_salt(client_hr: AsyncClient, mock_db_session: AsyncMock):
    import base64
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    key = base64.urlsafe_b64encode(b"0123456789abcdef0123456789abcdef").decode("ascii")
    role_result = MagicMock(); role_result.scalar_one_or_none.return_value = MagicMock()
    email_result = MagicMock(); email_result.scalar_one_or_none.return_value = None
    mock_db_session.execute.side_effect = [role_result, email_result]
    payload = {
        "full_name": "Private Person", "email": "pii@argus-app.com", "role_id": 1,
        "national_id": "NID-TEST-123", "contact_info": "Private address",
        "date_hired": "2026-08-24", "salary": 120000,
    }

    with patch("api.routers.employees.get_settings", return_value=SimpleNamespace(
        PII_ENCRYPTION_KEY=key, AUDIT_SALT="short", BLIND_INDEX_ITERATIONS=1000,
        BLIND_INDEX_MODE="pbkdf2",
    )):
        response = await client_hr.post("/api/employees", json=payload)

    assert response.status_code == 503
    mock_db_session.add.assert_not_called()


async def test_update_employee_encrypts_contact_info(client_hr: AsyncClient, mock_db_session: AsyncMock):
    import base64
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    from db.crypto.pii import decrypt_pii, encrypt_pii, is_encrypted_pii

    key = base64.urlsafe_b64encode(b"0123456789abcdef0123456789abcdef").decode("ascii")
    employee = SimpleNamespace(
        employee_id=7, full_name="Private Person", email="pii@argus-app.com", role_id=1,
        is_active=True, national_id_encrypted=encrypt_pii("NID-TEST-123", "national_id", key),
        contact_info_encrypted=encrypt_pii("Old address", "contact_info", key),
    )
    employee_result = MagicMock(); employee_result.scalar_one_or_none.return_value = employee
    mock_db_session.execute.side_effect = [employee_result, MagicMock()]

    with patch("api.routers.employees.get_settings", return_value=SimpleNamespace(
        PII_ENCRYPTION_KEY=key, AUDIT_SALT="test-salt-is-at-least-thirty-two-bytes", BLIND_INDEX_ITERATIONS=1000,
        BLIND_INDEX_MODE="pbkdf2",
    )):
        response = await client_hr.patch("/api/employees/7", json={"contact_info": "New private address"})

    assert response.status_code == 200, response.text
    assert is_encrypted_pii(employee.contact_info_encrypted)
    assert decrypt_pii(employee.contact_info_encrypted, "contact_info", key) == "New private address"


async def test_list_employees_search_id(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    from unittest.mock import MagicMock, patch
    mock_result = MagicMock()
    mock_result.all.return_value = []
    privileged_session = AsyncMock()
    privileged_session.__aenter__.return_value = privileged_session
    privileged_session.__aexit__.return_value = None
    privileged_session.scalar.return_value = 0
    privileged_session.execute.return_value = mock_result
    get_factory = MagicMock(return_value=MagicMock(return_value=privileged_session))
    with patch("api.routers.employees.get_session_factory", get_factory):
        response = await client_auditor.get("/api/employees?search=%231")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data


async def test_list_employees_search_emp_prefix(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    from unittest.mock import MagicMock, patch
    mock_result = MagicMock()
    mock_result.all.return_value = []
    privileged_session = AsyncMock()
    privileged_session.__aenter__.return_value = privileged_session
    privileged_session.__aexit__.return_value = None
    privileged_session.scalar.return_value = 0
    privileged_session.execute.return_value = mock_result
    get_factory = MagicMock(return_value=MagicMock(return_value=privileged_session))
    with patch("api.routers.employees.get_session_factory", get_factory):
        response = await client_auditor.get("/api/employees?search=EMP-0001")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
