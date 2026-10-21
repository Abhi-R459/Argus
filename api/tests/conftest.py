import base64
import os

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# API tests use mocked sessions. Never import the app with deployment secrets.
os.environ.setdefault("DATABASE_URL_HR_ADMIN", "postgresql+asyncpg://hr_admin@localhost/argus_test")
os.environ.setdefault("DATABASE_URL_COMPLIANCE_AUDITOR", "postgresql+asyncpg://compliance_auditor@localhost/argus_test")
os.environ["APP_ENV"] = "development"
# HR rollback receipts encrypt employee snapshots even in mocked route tests.
# Use deterministic, test-only values rather than inheriting deployment secrets.
os.environ["PII_ENCRYPTION_KEY"] = base64.urlsafe_b64encode(b"x" * 32).decode().rstrip("=")
os.environ["AUDIT_SALT"] = "test-only-audit-salt-" + ("x" * 32)
from httpx import AsyncClient, ASGITransport
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

from api.main import app
from api.dependencies import get_db_session, get_current_user
from api.middleware.clerk_auth import verify_clerk_token
from api.models.user import User
from api.config import get_settings


@pytest.fixture(autouse=True)
def isolated_signing_key(tmp_path):
    settings = get_settings()
    previous = settings.SIGNING_PRIVATE_KEY_PATH
    key = Ed25519PrivateKey.generate()
    key_path = tmp_path / "signing_private_key.pem"
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    settings.SIGNING_PRIVATE_KEY_PATH = str(key_path)
    try:
        yield
    finally:
        settings.SIGNING_PRIVATE_KEY_PATH = previous

@pytest.fixture
def mock_hr_user() -> User:
    user = User(
        user_id=1,
        clerk_user_id="user_hr_123",
        email="hr@argus.test",
        full_name="HR Admin",
        role="hr_admin",
        account_role="hr_admin",
        is_active=True,
    )
    return user

@pytest.fixture
def mock_auditor_user() -> User:
    user = User(
        user_id=2,
        clerk_user_id="user_auditor_123",
        email="auditor@argus.test",
        full_name="Compliance Auditor",
        role="compliance_auditor",
        account_role="compliance_auditor",
        is_active=True,
    )
    return user

@pytest.fixture
def mock_db_session():
    # Return an AsyncMock that acts like an AsyncSession
    session = AsyncMock()
    # Mock context manager behavior if needed
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None
    session.scalar.return_value = 0

    # Synchronous session methods in SQLAlchemy AsyncSession
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.delete = MagicMock()

    # Configure session.execute to return a synchronous Result mock
    mock_result = MagicMock()
    mock_result.scalar.return_value = 1
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalars.return_value.first.return_value = None
    mock_result.all.return_value = []
    mock_result.first.return_value = None
    session.execute.return_value = mock_result

    # Mock refresh to assign default integer IDs when refreshed
    async def _mock_refresh(instance):
        if hasattr(instance, "employee_id") and getattr(instance, "employee_id", None) is None:
            instance.employee_id = 2

    session.refresh = AsyncMock(side_effect=_mock_refresh)
    return session

@pytest.fixture
async def client_hr(mock_hr_user, mock_db_session) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_current_user] = lambda: mock_hr_user
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    app.dependency_overrides[verify_clerk_token] = lambda: {"sub": "clerk:user_hr_123", "email": "hr@argus.test", "name": "HR Admin", "email_verified": True, "provider": "clerk"}
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
        
    app.dependency_overrides.clear()

@pytest.fixture
async def client_auditor(mock_auditor_user, mock_db_session) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_current_user] = lambda: mock_auditor_user
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    app.dependency_overrides[verify_clerk_token] = lambda: {"sub": "clerk:user_auditor_123", "email": "auditor@argus.test", "name": "Compliance Auditor", "email_verified": True, "provider": "clerk"}
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
        
    app.dependency_overrides.clear()


@pytest.fixture
async def client_unauth() -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
