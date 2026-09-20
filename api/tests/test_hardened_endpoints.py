import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock
from api.config import get_settings
from api.models.user import User

pytestmark = pytest.mark.asyncio

async def test_verify_chain_fails_closed(client_auditor: AsyncClient):
    """Assert POST /api/verify fails closed (status='error') when verifier/connection fails."""
    with patch("db.cli.hash_verifier.verify_chain", side_effect=ConnectionError("Database unreachable")):
        response = await client_auditor.post("/api/verify")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert data["anchor_match"] is False
        assert "failure" in data["details"].lower() or "unreachable" in data["details"].lower()

async def test_role_switch_gated_by_setting(client_hr: AsyncClient):
    """Assert POST /api/auth/role is 403 Forbidden when ALLOW_DEMO_ROLE_SWITCH is False."""
    settings = get_settings()
    original_flag = settings.ALLOW_DEMO_ROLE_SWITCH
    try:
        settings.ALLOW_DEMO_ROLE_SWITCH = False
        response = await client_hr.post("/api/auth/role?new_role=compliance_auditor")
        assert response.status_code == 403
        assert "disabled in production" in response.json()["detail"].lower()
    finally:
        settings.ALLOW_DEMO_ROLE_SWITCH = original_flag

async def test_concurrency_benchmark_diagnostic_path(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    """Assert /api/analytics/diagnostics/concurrency-benchmark is accessible to auditors."""
    m_tail = MagicMock(); m_tail.scalar.return_value = 10
    m_row = MagicMock(); m_row.first.return_value = (10, "dummy_hash")
    mock_db_session.execute.side_effect = [m_tail, m_row, m_row]

    response = await client_auditor.post(
        "/api/analytics/diagnostics/concurrency-benchmark",
        json={"workers": 2},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["workers"] == 2
    assert payload["success_count"] == 2
    assert len(payload["logs"]) == 2

async def test_concurrency_benchmark_hr_forbidden(client_hr: AsyncClient):
    """Assert /api/analytics/diagnostics/concurrency-benchmark is 403 for HR role."""
    response = await client_hr.post(
        "/api/analytics/diagnostics/concurrency-benchmark",
        json={"workers": 2},
    )
    assert response.status_code == 403

async def test_get_my_profile_hr(client_hr: AsyncClient, mock_hr_user: User):
    """Assert GET /api/auth/me returns the authenticated user profile."""
    with patch("api.routers.auth.get_session_factory") as mock_factory:
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_hr_user
        mock_session.execute.return_value = mock_result
        mock_factory.return_value = MagicMock(return_value=mock_session)

        response = await client_hr.get("/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["clerk_user_id"] == mock_hr_user.clerk_user_id
        assert data["role"] == "hr_admin"
