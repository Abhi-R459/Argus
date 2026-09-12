import pytest
from httpx import AsyncClient, ASGITransport
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

from api.main import app
from api.dependencies import get_db_session, get_current_user
from api.middleware.clerk import verify_clerk_token
from api.models.user import User

@pytest.fixture
def mock_hr_user() -> User:
    user = User(
        user_id=1,
        clerk_user_id="user_hr_123",
        email="hr@argus.test",
        full_name="HR Admin",
        role="hr_admin",
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
    return session

@pytest.fixture
async def client_hr(mock_hr_user, mock_db_session) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_current_user] = lambda: mock_hr_user
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    app.dependency_overrides[verify_clerk_token] = lambda: {"sub": "user_hr_123", "email": "hr@argus.test", "name": "HR Admin"}
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
        
    app.dependency_overrides.clear()

@pytest.fixture
async def client_auditor(mock_auditor_user, mock_db_session) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_current_user] = lambda: mock_auditor_user
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    app.dependency_overrides[verify_clerk_token] = lambda: {"sub": "user_auditor_123", "email": "auditor@argus.test", "name": "Compliance Auditor"}
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
        
    app.dependency_overrides.clear()


@pytest.fixture
async def client_unauth() -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
