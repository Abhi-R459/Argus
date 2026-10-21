import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from api.middleware import clerk_auth


pytestmark = pytest.mark.asyncio
PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC_PEM = PRIVATE_KEY.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
).decode()


def token(**changes):
    now = int(time.time())
    claims = {
        "sub": "user_test123", "sid": "sess_test123",
        "iss": "https://clerk.arguss.in", "azp": "https://arguss.in",
        "iat": now, "nbf": now, "exp": now + 60,
    }
    claims.update(changes)
    return HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=jwt.encode(claims, PRIVATE_KEY, algorithm="RS256")
    )


def settings():
    return SimpleNamespace(
        CLERK_JWT_KEY=PUBLIC_PEM, CLERK_SECRET_KEY="sk_test_inert",
        CLERK_ISSUER="https://clerk.arguss.in",
        CLERK_AUTHORIZED_PARTIES="https://arguss.in",
    )


@pytest.mark.parametrize("claims", [
    {"iss": "https://attacker.example"},
    {"azp": "https://attacker.example"},
    {"exp": 1},
    {"sid": "bad/path"},
])
async def test_bad_clerk_claims_rejected(claims):
    with patch.object(clerk_auth, "get_settings", return_value=settings()):
        with pytest.raises(HTTPException) as exc:
            await clerk_auth.verify_clerk_token(token(**claims))
    assert exc.value.status_code == 401


async def test_revoked_session_rejected():
    with patch.object(clerk_auth, "get_settings", return_value=settings()), \
         patch.object(clerk_auth, "_clerk_object", new_callable=AsyncMock) as fetch:
        fetch.return_value = {"status": "revoked", "user_id": "user_test123"}
        with pytest.raises(HTTPException) as exc:
            await clerk_auth.verify_clerk_token(token())
    assert exc.value.status_code == 401


async def test_verified_clerk_session_accepted():
    user = {
        "id": "user_test123", "primary_email_address_id": "id_1",
        "email_addresses": [{"id": "id_1", "email_address": "Verified@Example.com",
                             "verification": {"status": "verified"}}],
        "first_name": "Test", "last_name": "User",
    }
    with patch.object(clerk_auth, "get_settings", return_value=settings()), \
         patch.object(clerk_auth, "_clerk_object", new_callable=AsyncMock) as fetch:
        fetch.side_effect = [{"status": "active", "user_id": "user_test123"}, user]
        identity = await clerk_auth.verify_clerk_token(token())
    assert identity["sub"] == "clerk:user_test123"
    assert identity["email"] == "verified@example.com"
