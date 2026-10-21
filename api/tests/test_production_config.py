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
    (tmp_path / 'public_key.pem').write_bytes(key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    values = {
        "_env_file": None,
        "APP_ENV": "production",
        "DATABASE_URL_HR_ADMIN": "postgresql+asyncpg://hr_admin:secret@db.example:5432/app?ssl=require",
        "DATABASE_URL_COMPLIANCE_AUDITOR": "postgresql+asyncpg://compliance_auditor:secret@db.example:5432/app?ssl=require",
        "SUPABASE_URL": "https://abcdefghijklmnopqrst.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_inert_test_key",
        "HR_ADMIN_EMAILS": "hr@example.com",
        "COMPLIANCE_AUDITOR_EMAILS": "audit@example.com",
        "PII_ENCRYPTION_KEY": base64.urlsafe_b64encode(b"p" * 32).decode().rstrip("="),
        "AUDIT_SALT": "s" * 32,
        "AUDIT_CONTEXT_SECRET": "a1" * 32,
        "CORS_ORIGINS": "https://argus.example.com",
        "SIGNING_PRIVATE_KEY_PATH": str(signing_key),
        "CHECKPOINT_PUBLIC_KEYS_DIR": str(tmp_path),
    }
    values.update(overrides)
    return Settings(**values)


def test_production_settings_accept_complete_secure_configuration(tmp_path):
    settings = _production_settings(tmp_path)
    assert settings.APP_ENV == "production"
    assert settings.SUPABASE_URL == "https://abcdefghijklmnopqrst.supabase.co"


def test_production_monitor_accepts_https_alert_receiver(tmp_path):
    settings = _production_settings(
        tmp_path,
        INTEGRITY_MONITOR_ENABLED=True,
        INTEGRITY_MONITOR_INTERVAL_SECONDS=300,
        SECURITY_ALERT_WEBHOOK_URL="https://alerts.example.com/argus",
    )

    assert settings.INTEGRITY_MONITOR_ENABLED is True
    assert settings.INTEGRITY_MONITOR_INTERVAL_SECONDS == 300


def test_alert_receiver_rejects_plain_http(tmp_path):
    with pytest.raises(ValueError, match="must be an HTTPS URL"):
        _production_settings(
            tmp_path,
            SECURITY_ALERT_WEBHOOK_URL="http://alerts.example.com/argus",
        )


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"SUPABASE_URL": ""}, "missing: SUPABASE_URL"),
        ({"CORS_ORIGINS": "http://argus.example.com"}, "HTTPS origins"),
        (
            {"DATABASE_URL_HR_ADMIN": "postgresql+asyncpg://hr_admin:secret@db/app"},
            "TLS required",
        ),
        ({"ALLOW_DEMO_ROLE_SWITCH": True}, "disabled in production"),
        ({"ALLOW_CONCURRENCY_DIAGNOSTICS": True}, "disabled in production"),
        ({"SUPABASE_URL": "https://untrusted.example.com"}, "Supabase project URL"),
        ({"SUPABASE_PUBLISHABLE_KEY": "sb_secret_private"}, "public publishable key"),
        ({"CORS_ORIGINS": "https://app.example.com?unsafe=1"}, "HTTPS origins"),
        ({"DATABASE_URL_HR_ADMIN": "postgresql+asyncpg://postgres:secret@db.example:5432/app?ssl=require"}, "dedicated hr_admin"),
        ({"HR_ADMIN_EMAILS": "audit@example.com"}, "must not overlap"),
    ],
)
def test_production_settings_fail_closed(tmp_path, override, message):
    with pytest.raises(ValueError, match=message):
        _production_settings(tmp_path, **override)


def test_production_configuration_errors_do_not_print_secrets(tmp_path):
    with pytest.raises(ValueError) as error:
        _production_settings(tmp_path, SUPABASE_URL='')
    message = str(error.value)
    assert 'secret@db.example' not in message
    assert 'a1' * 32 not in message
    assert 'BEGIN PUBLIC KEY' not in message
