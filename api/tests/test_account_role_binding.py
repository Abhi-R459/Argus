from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from api.dependencies import get_current_user
from api.main import app
from api.middleware.clerk_auth import verify_clerk_token
from api.models.user import User
from api.services import identity_user


@pytest.mark.asyncio
async def test_request_header_cannot_change_bound_role(monkeypatch):
    user = User(user_id=7, clerk_user_id="clerk:test", email="test@example.com",
                full_name="Test", role="hr_admin", account_role="hr_admin", is_active=True)
    monkeypatch.setattr("api.dependencies.resolve_clerk_user", AsyncMock(return_value=user))
    budget = AsyncMock()
    monkeypatch.setattr("api.dependencies.consume_request_budget", budget)
    resolved = await get_current_user({"sub": "clerk:test"})
    assert resolved.role == "hr_admin"
    budget.assert_awaited_once_with(user)


@pytest.mark.asyncio
async def test_auditor_header_cannot_unlock_auditor_endpoint(monkeypatch):
    user = User(user_id=7, clerk_user_id="clerk:test", email="test@example.com",
                full_name="Test", role="hr_admin", account_role="hr_admin", is_active=True)
    monkeypatch.setattr("api.dependencies.resolve_clerk_user", AsyncMock(return_value=user))
    monkeypatch.setattr("api.dependencies.consume_request_budget", AsyncMock())
    app.dependency_overrides[verify_clerk_token] = lambda: {"sub": "clerk:test"}
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/analytics/diagnostics/concurrency-benchmark",
                headers={"X-Argus-Role": "compliance_auditor"}, json={"workers": 2},
            )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_unbound_account_cannot_access_role_routed_api(monkeypatch):
    user = User(user_id=7, clerk_user_id="clerk:test", email="test@example.com",
                full_name="Test", role="compliance_auditor", account_role=None, is_active=True)
    monkeypatch.setattr("api.dependencies.resolve_clerk_user", AsyncMock(return_value=user))
    with pytest.raises(HTTPException) as error:
        await get_current_user({"sub": "clerk:test"})
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_role_choice_is_atomic_and_cannot_be_repeated(monkeypatch):
    user = User(user_id=7, clerk_user_id="clerk:test", email="test@example.com",
                full_name="Test", role="compliance_auditor", account_role=None, is_active=True)
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.execute.return_value = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = 7
    monkeypatch.setattr(identity_user, "get_session_factory", lambda _role: lambda: session)
    bound = await identity_user.bind_account_role(user, "hr_admin")
    assert bound.account_role == bound.role == "hr_admin"
    session.commit.assert_awaited_once()

    session.execute.return_value.scalar_one_or_none.return_value = None
    with pytest.raises(HTTPException) as error:
        await identity_user.bind_account_role(user, "compliance_auditor")
    assert error.value.status_code == 409
    assert bound.account_role == "hr_admin"
