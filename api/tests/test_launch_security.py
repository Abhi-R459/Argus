from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from api.config import get_settings
from api.database import runtime_engine_options
from api.main import app
from api.models.user import User
from api.routers import auth
from api.services.export import get_or_create_signing_key
from api.services import request_budget


@pytest.mark.asyncio
async def test_inactive_account_cannot_read_profile(client_hr, monkeypatch):
    user = User(user_id=10, clerk_user_id="user_hr_123", email="hr@argus.test",
                full_name="Inactive", role="hr_admin", is_active=False)
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.execute.return_value = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = user
    monkeypatch.setattr(auth, "get_session_factory", lambda role: lambda: session)
    response = await client_hr.get("/api/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_diagnostics_disabled_by_default(client_auditor):
    response = await client_auditor.post("/api/analytics/diagnostics/concurrency-benchmark", json={"workers": 2})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_validation_errors_do_not_echo_sensitive_input(client_hr):
    secret = "PRIVATE-NATIONAL-ID-123"
    response = await client_hr.post("/api/employees", json={"national_id": secret, "email": secret})
    assert response.status_code == 422
    assert secret not in response.text
    assert response.headers["X-Request-ID"]
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.asyncio
async def test_body_limit_applies_to_chunked_requests():
    async def chunks():
        yield b"x" * 600000
        yield b"x" * 600000
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.post("/api/auth/sync", content=chunks())
    assert response.status_code == 413


@pytest.mark.parametrize('mode', ['require', 'verify-ca', 'verify-full'])
def test_database_tls_authenticates_the_server(mode):
    import ssl
    options = runtime_engine_options(f"postgresql+asyncpg://hr_admin@db/app?sslmode={mode}", get_settings())
    context = options["connect_args"]["ssl"]
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname
    assert not options["url"].query
    assert options["connect_args"]["server_settings"]["statement_timeout"] == "30000"


def test_missing_database_ca_fails_closed(tmp_path):
    with pytest.raises(FileNotFoundError):
        runtime_engine_options(f"postgresql+asyncpg://hr_admin@db/app?sslmode=verify-full&sslrootcert={tmp_path / 'missing.crt'}", get_settings())


def test_production_export_never_generates_a_replacement_key(tmp_path, monkeypatch):
    original_files = set(tmp_path.iterdir())
    monkeypatch.setattr("api.services.export.get_settings", lambda: SimpleNamespace(
        APP_ENV="production", SIGNING_PRIVATE_KEY_PATH=str(tmp_path / "missing.pem")))
    with pytest.raises(FileNotFoundError):
        get_or_create_signing_key()
    assert set(tmp_path.iterdir()) == original_files


@pytest.mark.asyncio
async def test_request_budget_denial_is_committed_before_429(monkeypatch):
    from fastapi import HTTPException
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.execute.return_value = MagicMock()
    session.execute.return_value.one.return_value = (False, 20)
    monkeypatch.setattr(request_budget, "get_settings", lambda: SimpleNamespace(APP_ENV="production"))
    monkeypatch.setattr(request_budget, "get_session_factory", lambda role: lambda: session)
    with pytest.raises(HTTPException) as error:
        await request_budget.consume_request_budget(SimpleNamespace(role="hr_admin", user_id=10))
    assert error.value.status_code == 429
    assert error.value.headers == {"Retry-After": "20"}
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_auditor_cannot_create_business_metadata(client_auditor):
    assert (await client_auditor.post("/api/departments", json={"name": "People"})).status_code == 403
    assert (await client_auditor.post("/api/roles", json={"title": "Engineer", "department_id": 1,
        "salary_band_min": 1, "salary_band_max": 2})).status_code == 403


@pytest.mark.asyncio
async def test_transaction_failure_is_reported_before_success_response(client_hr, mock_db_session):
    from api.main import app
    from api.dependencies import get_db_session
    from sqlalchemy.exc import TimeoutError
    async def failing_transaction():
        yield mock_db_session
        raise TimeoutError('Commit failed; private details must not be echoed')
    app.dependency_overrides[get_db_session] = failing_transaction
    response = await client_hr.get('/api/departments')
    assert response.status_code == 503
    assert 'private details' not in response.text


@pytest.mark.asyncio
async def test_blind_index_budget_is_checked_before_reserving_business_connection(client_auditor, monkeypatch):
    from fastapi import HTTPException
    from api.main import app
    from api.dependencies import get_db_session
    from api.routers import audits
    settings = get_settings().model_copy(update={'APP_ENV': 'production'})
    monkeypatch.setattr(audits, 'get_settings', lambda: settings)
    async def denied(*args):
        raise HTTPException(status_code=429, detail='Rate limit exceeded')
    monkeypatch.setattr(audits, 'consume_request_budget', denied)
    business_connection = MagicMock()
    app.dependency_overrides[get_db_session] = business_connection
    response = await client_auditor.post('/api/audit-logs/search', json={'national_id_search': 'budget-check'})
    assert response.status_code == 429
    business_connection.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('lock_acquired', [True, False])
async def test_nonce_cleanup_runs_on_restart_and_backs_off_on_lock_contention(monkeypatch, lock_acquired):
    import asyncio
    from api import main
    session = AsyncMock()
    session.__aenter__.return_value = session
    lock = MagicMock()
    lock.scalar.return_value = lock_acquired
    cleanup = MagicMock()
    cleanup.scalar_one.return_value = 2
    session.execute.side_effect = [lock, cleanup]
    monkeypatch.setattr(main, 'get_session_factory', lambda role: lambda: session)
    wait = AsyncMock(side_effect=asyncio.CancelledError)
    monkeypatch.setattr(main.asyncio, 'sleep', wait)
    with pytest.raises(asyncio.CancelledError):
        await main._prune_actor_context_nonces_periodically()
    assert session.execute.await_count == (2 if lock_acquired else 1)
    wait.assert_awaited_once_with(6 * 60 * 60)
    if lock_acquired:
        session.commit.assert_awaited_once()
    else:
        session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_external_store_never_claims_anchoring(client_auditor, mock_db_session, monkeypatch):
    from datetime import datetime, timezone
    from api.routers import audits
    settings = get_settings().model_copy(update={'ANCHOR_STORE': 'none'})
    monkeypatch.setattr(audits, 'get_settings', lambda: settings)
    checkpoint = MagicMock()
    checkpoint.first.return_value = (1, 5, 'a' * 64, datetime.now(timezone.utc), 'local:ed25519:v1')
    tail = MagicMock()
    tail.first.return_value = (8,)
    mock_db_session.execute.side_effect = [checkpoint, tail]
    response = await client_auditor.get('/api/anchor/status')
    assert response.status_code == 200
    status = response.json()
    assert status['status'] == 'MISSING'
    assert status['last_anchored'] is None
    assert status['entries_since_anchor'] == 8
    assert status['witness_report']['verification_status'] == 'unknown'
    assert status['witness_report']['independent_trust_domains'] is False
