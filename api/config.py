from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs, urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

from db.crypto.actor_context import parse_context_secret
from db.crypto.pii import require_pii_encryption_key, validate_audit_salt

class Settings(BaseSettings):
    APP_ENV: Literal["development", "staging", "production"] = "development"
    # Migration credentials are only needed by Alembic, never by the API runtime.
    DATABASE_URL_MIGRATIONS: str = ""
    DATABASE_URL_HR_ADMIN: str
    DATABASE_URL_COMPLIANCE_AUDITOR: str
    CLERK_JWT_KEY: str = ""
    CLERK_ISSUER: str = ""
    CLERK_AUTHORIZED_PARTIES: str = ""
    SIGNING_PRIVATE_KEY_PATH: str = "./keys/verifier_private_key.pem"
    CHECKPOINT_PUBLIC_KEYS_DIR: str = "./keys"
    WITNESS_PUBLIC_KEYS_DIR: str = "./trusted-witness-keys"
    WITNESS_STORE_PATH: str = ""
    ANCHOR_STORE: str = "local_file"
    ANCHOR_FILE_PATH: str = "./anchor/chain_anchor.log"
    GITHUB_ANCHOR_REPOSITORY: str = ""
    GITHUB_ANCHOR_TOKEN: str = ""
    CHECKPOINT_INTERVAL: int = 25
    AUDIT_SALT: str = ""
    AUDIT_CONTEXT_SECRET: str = ""
    AUDIT_CONTEXT_KEY_ID: str = "v1"
    BLIND_INDEX_ITERATIONS: int = 1000
    BLIND_INDEX_MODE: str = "pbkdf2"  # "pbkdf2" or "hmac"
    BLIND_INDEX_RATE_LIMIT_PER_MINUTE: int = 10
    PII_ENCRYPTION_KEY: str = ""
    ALLOW_DEMO_ROLE_SWITCH: bool = False
    HR_ADMIN_EMAILS: str = ""
    COMPLIANCE_AUDITOR_EMAILS: str = ""
    SUSPICIOUS_ACTIVITY_REFRESH_SECONDS: int = 30
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    DB_POOL_SIZE: int = 2
    DB_MAX_OVERFLOW: int = 1

    @property
    def authorized_parties(self) -> set[str]:
        return {value.strip().rstrip("/") for value in self.CLERK_AUTHORIZED_PARTIES.split(",") if value.strip()}

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        """Fail closed when deployment declares production but lacks security controls."""
        if self.APP_ENV == "development":
            return self

        missing = []
        for name, value in (
            ("CLERK_JWT_KEY", self.CLERK_JWT_KEY),
            ("CLERK_ISSUER", self.CLERK_ISSUER),
            ("CLERK_AUTHORIZED_PARTIES", self.CLERK_AUTHORIZED_PARTIES),
            ("HR_ADMIN_EMAILS", self.HR_ADMIN_EMAILS),
            ("COMPLIANCE_AUDITOR_EMAILS", self.COMPLIANCE_AUDITOR_EMAILS),
            ("PII_ENCRYPTION_KEY", self.PII_ENCRYPTION_KEY),
            ("AUDIT_SALT", self.AUDIT_SALT),
            ("AUDIT_CONTEXT_SECRET", self.AUDIT_CONTEXT_SECRET),
        ):
            if not value.strip():
                missing.append(name)

        if missing:
            raise ValueError("Production configuration is missing: " + ", ".join(missing))

        issuer = urlsplit(self.CLERK_ISSUER)
        parties = self.authorized_parties
        if issuer.scheme != "https" or not issuer.netloc:
            raise ValueError("CLERK_ISSUER must be an HTTPS issuer URL.")
        if not parties or any(
            urlsplit(party).scheme != "https"
            or not urlsplit(party).netloc
            or "*" in party
            or urlsplit(party).path not in ("", "/")
            for party in parties
        ):
            raise ValueError("CLERK_AUTHORIZED_PARTIES must contain exact HTTPS application origins.")
        try:
            jwt_public_key = load_pem_public_key(self.CLERK_JWT_KEY.encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise ValueError("CLERK_JWT_KEY must contain Clerk's PEM public key.") from exc
        if not isinstance(jwt_public_key, RSAPublicKey):
            raise ValueError("CLERK_JWT_KEY must contain Clerk's PEM public key.")

        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        if not origins or any(
            urlsplit(origin).scheme != "https"
            or not urlsplit(origin).netloc
            or "*" in origin
            or urlsplit(origin).path not in ("", "/")
            for origin in origins
        ):
            raise ValueError("Production CORS_ORIGINS must contain exact HTTPS origins only.")

        for name, value in (
            ("DATABASE_URL_HR_ADMIN", self.DATABASE_URL_HR_ADMIN),
            ("DATABASE_URL_COMPLIANCE_AUDITOR", self.DATABASE_URL_COMPLIANCE_AUDITOR),
        ):
            parsed = urlsplit(value)
            query = parse_qs(parsed.query)
            ssl_value = (query.get("ssl") or query.get("sslmode") or [""])[0].lower()
            if parsed.scheme != "postgresql+asyncpg" or not parsed.hostname or ssl_value not in {"require", "verify-ca", "verify-full"}:
                raise ValueError(f"{name} must use PostgreSQL asyncpg with TLS required.")

        try:
            require_pii_encryption_key(self.PII_ENCRYPTION_KEY)
            validate_audit_salt(self.AUDIT_SALT)
            parse_context_secret(self.AUDIT_CONTEXT_SECRET)
        except ValueError as exc:
            raise ValueError("Production cryptographic configuration is invalid.") from exc

        if self.ALLOW_DEMO_ROLE_SWITCH:
            raise ValueError("ALLOW_DEMO_ROLE_SWITCH must remain disabled in production.")
        if self.DB_POOL_SIZE < 1 or self.DB_MAX_OVERFLOW < 0:
            raise ValueError("Production database pool limits are invalid.")

        signing_key = Path(self.SIGNING_PRIVATE_KEY_PATH)
        if not signing_key.is_file():
            raise ValueError("SIGNING_PRIVATE_KEY_PATH must point to the mounted signing key.")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        # The repository shares one .env across the API, Compose, migrations,
        # and maintenance CLIs. Ignore keys owned by other processes.
        extra="ignore",
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()
