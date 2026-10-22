from unittest.mock import AsyncMock, MagicMock

import pytest

from api.models.auth_identity import AuthIdentity
from api.models.user import User
from api.services import identity_user


def _identity(name=""):
    return {
        "provider": "clerk",
        "sub": "clerk:user_test",
        "email": "Person@Example.com",
        "email_verified": True,
        "name": name,
    }


def _result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


@pytest.mark.asyncio
async def test_existing_placeholder_name_is_repaired_on_next_request(monkeypatch):
    user = User(user_id=42, clerk_user_id="clerk:user_test", email="person@example.com",
                full_name="Unknown", role="hr_admin", account_role="hr_admin", is_active=True)
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.execute.side_effect = [
        _result(AuthIdentity(provider="clerk", subject="clerk:user_test", user_id=42)),
        _result(user),
    ]
    monkeypatch.setattr(identity_user, "get_session_factory", lambda _role: lambda: session)

    resolved = await identity_user.resolve_clerk_user(_identity())

    assert resolved.full_name == "person@example.com"
    assert resolved.account_role == "hr_admin"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_real_name_is_not_replaced_by_email(monkeypatch):
    user = User(user_id=42, clerk_user_id="clerk:user_test", email="person@example.com",
                full_name="Existing Name", role="hr_admin", account_role="hr_admin", is_active=True)
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.execute.side_effect = [
        _result(AuthIdentity(provider="clerk", subject="clerk:user_test", user_id=42)),
        _result(user),
    ]
    monkeypatch.setattr(identity_user, "get_session_factory", lambda _role: lambda: session)

    resolved = await identity_user.resolve_clerk_user(_identity("New Name"))

    assert resolved.full_name == "Existing Name"
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_new_account_without_clerk_name_uses_verified_email(monkeypatch):
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.add = MagicMock()
    session.execute.side_effect = [_result(None), _result(None)]
    monkeypatch.setattr(identity_user, "get_session_factory", lambda _role: lambda: session)

    user = await identity_user.resolve_clerk_user(_identity())

    assert user.full_name == "person@example.com"
    assert user.account_role is None
    session.commit.assert_awaited_once()
