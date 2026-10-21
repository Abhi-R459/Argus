from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from api.config import Settings


def _production_settings(tmp_path, **overrides):
    signing_key = tmp_path / "signing_private_key.pem"
    key = Ed25519PrivateKey.generate()
    signing_key.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    (tmp_path / "public_key.pem").write_bytes(key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    values = {
        "_env_file": None,
        "APP_ENV": "production",
        "DATABASE_URL_HR_ADMIN": "postgresql+asyncpg://hr_admin:secret@db.example:5432/app?ssl=require",
        "DATABASE_URL_COMPLIANCE_AUDITOR": "postgresql+asyncpg://compliance_auditor:secret@db.example:5432/app?ssl=require",
        "CLERK_JWT_KEY": "test-public-key",
        "CLERK_SECRET_KEY": "sk_live_inert",
        "CLERK_ISSUER": "https://clerk.arguss.in",
        "CLERK_AUTHORIZED_PARTIES": "https://arguss.in",
        "PII_ENCRYPTION_KEY": base64.urlsafe_b64encode(b"p" * 32).decode().rstrip("="),
        "AUDIT_SALT": "s" * 32,
        "AUDIT_CONTEXT_SECRET": "a1" * 32,
        "CORS_ORIGINS": "https://arguss.in",
        "SIGNING_PRIVATE_KEY_PATH": str(signing_key),
        "CHECKPOINT_PUBLIC_KEYS_DIR": str(tmp_path),
    }
    values.update(overrides)
    return Settings(**values)


def test_production_settings_accept_clerk_configuration(tmp_path):
    assert _production_settings(tmp_path).CLERK_ISSUER == "https://clerk.arguss.in"


@pytest.mark.parametrize(("override", "message"), [
    ({"CLERK_JWT_KEY": ""}, "CLERK_JWT_KEY"),
    ({"CLERK_SECRET_KEY": ""}, "CLERK_SECRET_KEY"),
    ({"CLERK_SECRET_KEY": "pk_live_inert"}, "production secret key"),
    ({"CLERK_ISSUER": "http://clerk.arguss.in"}, "HTTPS"),
    ({"CLERK_AUTHORIZED_PARTIES": "http://arguss.in"}, "HTTPS origins"),
    ({"CORS_ORIGINS": "http://arguss.in"}, "HTTPS origins"),
    ({"DATABASE_URL_HR_ADMIN": "postgresql+asyncpg://postgres:secret@db.example/app?ssl=require"}, "dedicated hr_admin"),
])
def test_production_settings_fail_closed(tmp_path, override, message):
    with pytest.raises(ValueError, match=message):
        _production_settings(tmp_path, **override)
