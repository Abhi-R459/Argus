"""Create isolated local-demo secrets from configured Clerk Development settings.

This script never copies database URLs or cryptographic secrets from the main
.env file. It creates a separate .env.demo and Ed25519 key for local demo use.
"""

from __future__ import annotations

import base64
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ENV = ROOT / ".env"
DEMO_ENV = ROOT / ".env.demo"
KEY_DIR = ROOT / "keys"
PRIVATE_KEY = KEY_DIR / "local_demo_signing_private_key.pem"


def main() -> int:
    if not SOURCE_ENV.is_file():
        print("Create and configure the repository .env first.", file=sys.stderr)
        return 2
    if DEMO_ENV.exists():
        print(".env.demo already exists; refusing to overwrite local demo secrets.", file=sys.stderr)
        return 2

    source = dotenv_values(SOURCE_ENV)
    publishable_key = source.get("VITE_CLERK_PUBLISHABLE_KEY") or ""
    issuer = (source.get("CLERK_ISSUER") or "").strip().rstrip("/")
    issuer_host = urlsplit(issuer).hostname or ""
    if not publishable_key.startswith("pk_test_") or not issuer_host.endswith(".clerk.accounts.dev"):
        print("The source .env must contain Clerk Development publishable key and issuer values.", file=sys.stderr)
        return 2
    for name in ("CLERK_JWT_KEY", "HR_ADMIN_EMAILS", "COMPLIANCE_AUDITOR_EMAILS"):
        if not (source.get(name) or "").strip():
            print(f"The source .env is missing {name}.", file=sys.stderr)
            return 2

    if PRIVATE_KEY.exists():
        print(f"Refusing to overwrite existing local demo key: {PRIVATE_KEY}", file=sys.stderr)
        return 2

    KEY_DIR.mkdir(parents=True, exist_ok=True)
    signing_key = Ed25519PrivateKey.generate()
    private_pem = signing_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = signing_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    PRIVATE_KEY.write_bytes(private_pem)
    (KEY_DIR / "local_demo_signing_public_key.pem").write_bytes(public_pem)
    try:
        os.chmod(PRIVATE_KEY, 0o600)
    except OSError:
        pass

    postgres_password = secrets.token_urlsafe(36)
    hr_password = secrets.token_urlsafe(36)
    auditor_password = secrets.token_urlsafe(36)
    if len({postgres_password, hr_password, auditor_password}) != 3:
        raise RuntimeError("Generated database passwords were not unique.")

    values = {
        "APP_ENV": "development",
        "ARGUS_DATABASE_PORT": "5438",
        "ARGUS_API_PORT": "8008",
        "ARGUS_WEB_PORT": "8088",
        "POSTGRES_PASSWORD": postgres_password,
        "HR_ADMIN_PASSWORD": hr_password,
        "COMPLIANCE_AUDITOR_PASSWORD": auditor_password,
        "MIGRATIONS_DATABASE_URL": f"postgresql://postgres:{postgres_password}@db:5432/argus",
        "DATABASE_URL_MIGRATIONS": f"postgresql://postgres:{postgres_password}@localhost:5438/argus",
        "DATABASE_URL_HR_ADMIN": f"postgresql+asyncpg://hr_admin:{hr_password}@localhost:5438/argus",
        "DATABASE_URL_COMPLIANCE_AUDITOR": f"postgresql+asyncpg://compliance_auditor:{auditor_password}@localhost:5438/argus",
        "COMPOSE_DATABASE_URL_HR_ADMIN": "",
        "COMPOSE_DATABASE_URL_COMPLIANCE_AUDITOR": "",
        "VITE_CLERK_PUBLISHABLE_KEY": publishable_key,
        "VITE_API_URL": "/api",
        "CLERK_JWT_KEY": source["CLERK_JWT_KEY"],
        "CLERK_ISSUER": issuer,
        "CLERK_AUTHORIZED_PARTIES": "http://localhost:8088",
        "HR_ADMIN_EMAILS": source["HR_ADMIN_EMAILS"],
        "COMPLIANCE_AUDITOR_EMAILS": source["COMPLIANCE_AUDITOR_EMAILS"],
        "CORS_ORIGINS": "http://localhost:8088",
        "DB_POOL_SIZE": "2",
        "DB_MAX_OVERFLOW": "1",
        "PII_ENCRYPTION_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("="),
        "AUDIT_SALT": secrets.token_urlsafe(32),
        "AUDIT_CONTEXT_SECRET": secrets.token_hex(32),
        "AUDIT_CONTEXT_KEY_ID": "v1",
        "SIGNING_PRIVATE_KEY_FILE": "./keys/local_demo_signing_private_key.pem",
        "ANCHOR_STORE": "local_file",
        "ANCHOR_FILE_PATH": "/app/anchor/chain_anchor.log",
        "CHECKPOINT_INTERVAL": "25",
        "SUSPICIOUS_ACTIVITY_REFRESH_SECONDS": "30",
    }

    def env_line(key: str, value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "\\r").replace("\n", "\\n")
        return f'{key}="{escaped}"'

    DEMO_ENV.write_text(
        "\n".join(env_line(key, value) for key, value in values.items()) + "\n",
        encoding="utf-8",
    )

    print("Created .env.demo with local database URLs and Clerk Development settings.")
    print("Created a separate local-demo signing key under keys/.")
    print("No database credentials or cryptographic keys were copied from .env.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
