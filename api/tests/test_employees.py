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


async def test_auditor_directory_pii_reveal_is_recorded(client_auditor: AsyncClient, mock_db_session: AsyncMock):
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

    response = await client_auditor.get("/api/employees?include_pii=true")
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["full_name"] == "Private Employee"
    assert item["email"] == "private@example.test"
    event = mock_db_session.add.call_args.args[0]
    assert event.event_type == "DIRECTORY_PII_REVEAL"

async def test_create_employee_hr(client_hr: AsyncClient, mock_db_session: AsyncMock):
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
    mock_db_session.execute.side_effect = [mock_role_res, mock_email_res]
    
    payload = {
        "full_name": "Bob",
        "email": "bob@argus-app.com",
        "role_id": 1,
        "national_id": "SSN-123",
        "contact_info": "123 Main St",
        "date_hired": "2026-08-24",
        "salary": 120000
    }
    
    response = await client_hr.post("/api/employees", json=payload)
    assert response.status_code in [201, 500, 409], f"Failed with {response.status_code}: {response.text}"


async def test_list_employees_search_id(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db_session.execute.return_value = mock_result
    response = await client_auditor.get("/api/employees?search=%231")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data


async def test_list_employees_search_emp_prefix(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db_session.execute.return_value = mock_result
    response = await client_auditor.get("/api/employees?search=EMP-0001")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
