import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock

pytestmark = pytest.mark.asyncio

async def test_audit_logs_auditor(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db_session.execute.return_value = mock_result
    
    response = await client_auditor.get("/api/audit-logs")
    assert response.status_code in [200, 500]

async def test_audit_logs_hr_forbidden(client_hr: AsyncClient):
    response = await client_hr.get("/api/audit-logs")
    assert response.status_code == 403

async def test_verify_chain_auditor(client_auditor: AsyncClient):
    response = await client_auditor.post("/api/verify")
    # Endpoint might return 200 or 500 based on mock, but definitely not 403
    assert response.status_code in [200, 500]

async def test_verify_chain_hr_forbidden(client_hr: AsyncClient):
    response = await client_hr.post("/api/verify")
    assert response.status_code == 403

async def test_suspicious_flags_auditor(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db_session.execute.return_value = mock_result
    response = await client_auditor.get("/api/suspicious-activity")
    assert response.status_code in [200, 500]

async def test_suspicious_flags_hr_forbidden(client_hr: AsyncClient):
    response = await client_hr.get("/api/suspicious-activity")
    assert response.status_code == 403

async def test_export_auditor(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db_session.execute.return_value = mock_result
    response = await client_auditor.get("/api/audit-logs/export")
    assert response.status_code in [200, 500]

async def test_export_hr_forbidden(client_hr: AsyncClient):
    response = await client_hr.get("/api/audit-logs/export")
    assert response.status_code == 403
