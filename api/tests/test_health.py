import pytest
from contextlib import asynccontextmanager
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from api.main import app
from api.routers import health

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readiness_checks_both_database_roles(monkeypatch):
    session = AsyncMock()

    @asynccontextmanager
    async def session_context():
        yield session

    requested_roles = []

    def get_factory(role):
        requested_roles.append(role)
        return MagicMock(return_value=session_context())

    monkeypatch.setattr(health, "get_session_factory", get_factory)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert requested_roles == ["hr_admin", "compliance_auditor"]
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_readiness_returns_503_when_database_role_fails(monkeypatch):
    session = AsyncMock()
    session.execute.side_effect = RuntimeError("database unavailable")

    @asynccontextmanager
    async def session_context():
        yield session

    monkeypatch.setattr(health, "get_session_factory", lambda role: MagicMock(return_value=session_context()))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Required database connection is unavailable."}
