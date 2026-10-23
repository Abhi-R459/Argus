from functools import lru_cache
import re
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs, urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from cryptography.hazmat.primitives.serialization import load_pem_public_key, load_pem_private_key
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from db.crypto.actor_context import parse_context_secret
from db.crypto.pii import require_pii_encryption_key, validate_audit_salt

class Settings(BaseSettings):
    APP_ENV: Literal["development", "staging", "production"] = "development"
    # Migration credentials are only needed by Alembic, never by the API runtime.
    DATABASE_URL_MIGRATIONS: str = ""
    DATABASE_URL_HR_ADMIN: str
    DATABASE_URL_COMPLIANCE_AUDITOR: str
    CLERK_JWT_KEY: str = Field(default="", repr=False)
    CLERK_SECRET_KEY: str = Field(default="", repr=False)
    CLERK_ISSUER: str = ""
    CLERK_AUTHORIZED_PARTIES: str = ""
    SIGNING_PRIVATE_KEY_PATH: str = "./keys/verifier_private_key.pem"
    CHECKPOINT_PUBLIC_KEYS_DIR: str = "./keys"
    WITNESS_PUBLIC_KEYS_DIR: str = "./trusted-witness-keys"
    WITNESS_TRUST_CONFIG_JSON: str = Field(default="", repr=False)
    WITNESS_STORE_PATH: str = ""
    WITNESS_REQUIRED_THRESHOLD: int = Field(default=2, ge=2, le=20)
    ANCHOR_STORE: str = "local_file"
    ANCHOR_FILE_PATH: str = "./anchor/chain_anchor.log"
    GITHUB_ANCHOR_REPOSITORY: str = ""
    GITHUB_ANCHOR_TOKEN: str = Field(default="", repr=False)
    GITHUB_ANCHOR_BRANCH: str = "main"
    GITHUB_ANCHOR_MIN_SEQUENCE: int = 0
    CHECKPOINT_INTERVAL: int = 25
    AUDIT_SALT: str = ""
    AUDIT_CONTEXT_SECRET: str = ""
    AUDIT_CONTEXT_KEY_ID: str = "v1"
    BLIND_INDEX_ITERATIONS: int = 1000
    BLIND_INDEX_MODE: str = "pbkdf2"  # "pbkdf2" or "hmac"
    BLIND_INDEX_RATE_LIMIT_PER_MINUTE: int = 10
    PII_ENCRYPTION_KEY: str = ""
    ALLOW_CONCURRENCY_DIAGNOSTICS: bool = False
    SUSPICIOUS_ACTIVITY_REFRESH_SECONDS: int = 30
    INTEGRITY_MONITOR_ENABLED: bool = False
    INTEGRITY_MONITOR_INTERVAL_SECONDS: int = Field(default=300, ge=60, le=3600)
    SECURITY_ALERT_WEBHOOK_URL: str = Field(default="", repr=False)
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    DB_POOL_SIZE: int = 2
    DB_MAX_OVERFLOW: int = 1
    DB_STATEMENT_TIMEOUT_MS: int = 30000
    DB_LOCK_TIMEOUT_MS: int = 5000
    MAX_REQUEST_BODY_BYTES: int = 1048576

    @staticmethod
    def _is_https_origin(value: str) -> bool:
        parsed = urlsplit(value)
        return bool(
            parsed.scheme == "https" and parsed.hostname
            and not parsed.username and not parsed.password
            and not parsed.query and not parsed.fragment
            and parsed.path in ("", "/") and "*" not in value
        )

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        """Fail closed when deployment declares production but lacks security controls."""
        if self.SECURITY_ALERT_WEBHOOK_URL:
            alert_url = urlsplit(self.SECURITY_ALERT_WEBHOOK_URL)
            if (
                alert_url.scheme != "https"
                or not alert_url.hostname
                or alert_url.username
                or alert_url.password
                or alert_url.fragment
            ):
                raise ValueError("SECURITY_ALERT_WEBHOOK_URL must be an HTTPS URL without embedded credentials or fragments.")
        if self.APP_ENV == "development":
            return self

        missing = []
        for name, value in (
            ("PII_ENCRYPTION_KEY", self.PII_ENCRYPTION_KEY),
            ("AUDIT_SALT", self.AUDIT_SALT),
            ("AUDIT_CONTEXT_SECRET", self.AUDIT_CONTEXT_SECRET),
        ):
            if not value.strip():
                missing.append(name)

        if missing:
            raise ValueError("Production configuration is missing: " + ", ".join(missing))

        for name, value in (
            ("CLERK_JWT_KEY", self.CLERK_JWT_KEY),
            ("CLERK_SECRET_KEY", self.CLERK_SECRET_KEY),
            ("CLERK_ISSUER", self.CLERK_ISSUER),
            ("CLERK_AUTHORIZED_PARTIES", self.CLERK_AUTHORIZED_PARTIES),
        ):
            if not value.strip():
                raise ValueError(name + " is required with Clerk authentication.")
        if self.APP_ENV == "production" and not self.CLERK_SECRET_KEY.startswith("sk_live_"):
            raise ValueError("CLERK_SECRET_KEY must be a Clerk production secret key.")
        if not self.CLERK_ISSUER.startswith("https://"):
            raise ValueError("CLERK_ISSUER must be HTTPS.")
        parties = [value.strip() for value in self.CLERK_AUTHORIZED_PARTIES.split(",") if value.strip()]
        if not parties or any(not self._is_https_origin(value) for value in parties):
            raise ValueError("CLERK_AUTHORIZED_PARTIES must contain exact HTTPS origins.")

        if self.ANCHOR_STORE == "github_repo":
            if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.GITHUB_ANCHOR_REPOSITORY):
                raise ValueError("GITHUB_ANCHOR_REPOSITORY must be owner/repository.")
            if not self.GITHUB_ANCHOR_TOKEN.strip():
                raise ValueError("GITHUB_ANCHOR_TOKEN is required for a private anchor repository.")
            if not re.fullmatch(r"[A-Za-z0-9_./-]+", self.GITHUB_ANCHOR_BRANCH) or ".." in self.GITHUB_ANCHOR_BRANCH:
                raise ValueError("GITHUB_ANCHOR_BRANCH is invalid.")
            if self.GITHUB_ANCHOR_MIN_SEQUENCE < 1:
                raise ValueError("GITHUB_ANCHOR_MIN_SEQUENCE must pin a published checkpoint sequence.")


        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        if not origins or any(
            not self._is_https_origin(origin)
            for origin in origins
        ):
            raise ValueError("Production CORS_ORIGINS must contain exact HTTPS origins only.")

        database_targets = []
        for name, value, expected_role in (
            ("DATABASE_URL_HR_ADMIN", self.DATABASE_URL_HR_ADMIN, "hr_admin"),
            ("DATABASE_URL_COMPLIANCE_AUDITOR", self.DATABASE_URL_COMPLIANCE_AUDITOR, "compliance_auditor"),
        ):
            parsed = urlsplit(value)
            query = parse_qs(parsed.query)
            ssl_value = (query.get("ssl") or query.get("sslmode") or [""])[0].lower()
            if parsed.scheme != "postgresql+asyncpg" or not parsed.hostname or ssl_value not in {"require", "verify-ca", "verify-full"}:
                raise ValueError(f"{name} must use PostgreSQL asyncpg with TLS required.")
            if (parsed.username or "").split(".")[0] != expected_role:
                raise ValueError(f"{name} must use the dedicated {expected_role} database login.")
            database_targets.append((parsed.hostname, parsed.port, parsed.path))
        if database_targets[0] != database_targets[1]:
            raise ValueError("Both runtime roles must connect to the same database.")

        try:
            require_pii_encryption_key(self.PII_ENCRYPTION_KEY)
            validate_audit_salt(self.AUDIT_SALT)
            parse_context_secret(self.AUDIT_CONTEXT_SECRET)
        except ValueError as exc:
            raise ValueError("Production cryptographic configuration is invalid.") from exc

        if self.ALLOW_CONCURRENCY_DIAGNOSTICS:
            raise ValueError("ALLOW_CONCURRENCY_DIAGNOSTICS must remain disabled in production.")
        if self.DB_POOL_SIZE < 1 or self.DB_MAX_OVERFLOW < 0:
            raise ValueError("Production database pool limits are invalid.")
        if not (1000 <= self.DB_STATEMENT_TIMEOUT_MS <= 120000) or not (100 <= self.DB_LOCK_TIMEOUT_MS <= self.DB_STATEMENT_TIMEOUT_MS):
            raise ValueError("Production database timeouts are invalid.")
        if not 1024 <= self.MAX_REQUEST_BODY_BYTES <= 10485760:
            raise ValueError("MAX_REQUEST_BODY_BYTES must be between 1 KiB and 10 MiB.")

        if not 1 <= self.BLIND_INDEX_RATE_LIMIT_PER_MINUTE <= 300:
            raise ValueError("BLIND_INDEX_RATE_LIMIT_PER_MINUTE must be between 1 and 300.")

        signing_key = Path(self.SIGNING_PRIVATE_KEY_PATH)
        if not signing_key.is_file():
            raise ValueError("SIGNING_PRIVATE_KEY_PATH must point to the mounted signing key.")
        try:
            private_key = load_pem_private_key(signing_key.read_bytes(), password=None)
        except (OSError, TypeError, ValueError) as exc:
            raise ValueError("SIGNING_PRIVATE_KEY_PATH must contain a valid Ed25519 private key.") from exc
        if not isinstance(private_key, Ed25519PrivateKey):
            raise ValueError("SIGNING_PRIVATE_KEY_PATH must contain a valid Ed25519 private key.")
        try:
            trusted_key = load_pem_public_key((Path(self.CHECKPOINT_PUBLIC_KEYS_DIR) / 'public_key.pem').read_bytes())
            if trusted_key.public_bytes(Encoding.Raw, PublicFormat.Raw) != private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw):
                raise ValueError('Signing key does not match the trusted checkpoint public key.')
        except (OSError, TypeError, ValueError) as exc:
            raise ValueError('CHECKPOINT_PUBLIC_KEYS_DIR must include a matching Ed25519 public_key.pem.') from exc
        return self

    model_config = SettingsConfigDict(
        # .env.local is an ignored per-machine override for the usual host-run
        # Uvicorn workflow. Keep .env as the shared source; local values override it.
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        hide_input_in_errors=True,
        # The repository shares one .env across the API, Compose, migrations,
        # and maintenance CLIs. Ignore keys owned by other processes.
        extra="ignore",
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()
