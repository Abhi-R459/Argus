from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.security import HTTPAuthorizationCredentials

from api.middleware import clerk


@pytest.fixture
def signing_keys():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


def _token(private_key, *, issuer="https://clerk.example.com", azp="https://argus.example.com"):
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": "user_test_123",
            "iss": issuer,
            "azp": azp,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        },
        private_key,
        algorithm="RS256",
    )


@pytest.mark.asyncio
async def test_clerk_token_requires_expected_issuer_and_authorized_party(monkeypatch, signing_keys):
    private_key, public_key = signing_keys
    monkeypatch.setattr(clerk, "_fetch_clerk_jwks", lambda: _public_key(public_key))
    monkeypatch.setattr(
        clerk,
        "get_settings",
        lambda: SimpleNamespace(
            APP_ENV="production",
            CLERK_ISSUER="https://clerk.example.com",
            CLERK_AUTHORIZED_PARTIES="https://argus.example.com",
            authorized_parties={"https://argus.example.com"},
        ),
    )

    payload = await clerk.verify_clerk_token(
        HTTPAuthorizationCredentials(scheme="Bearer", credentials=_token(private_key))
    )
    assert payload["sub"] == "user_test_123"

    for token in (
        _token(private_key, issuer="https://other-clerk.example.com"),
        _token(private_key, azp="https://untrusted.example.com"),
    ):
        with pytest.raises(HTTPException) as error:
            await clerk.verify_clerk_token(
                HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            )
        assert error.value.status_code == 401


async def _public_key(key):
    return {"pem_key": key}
