from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL_MIGRATIONS: str
    DATABASE_URL_HR_ADMIN: str
    DATABASE_URL_COMPLIANCE_AUDITOR: str
    VITE_CLERK_PUBLISHABLE_KEY: str = ""
    CLERK_SECRET_KEY: str = ""
    CLERK_JWT_KEY: str = ""
    CLERK_WEBHOOK_SIGNING_SECRET: str = ""
    SIGNING_PRIVATE_KEY_PATH: str = "./keys/verifier_private_key.pem"
    ANCHOR_STORE: str = "local_file"
    ANCHOR_FILE_PATH: str = "./anchor/chain_anchor.log"
    GITHUB_ANCHOR_REPOSITORY: str = ""
    GITHUB_ANCHOR_TOKEN: str = ""
    CHECKPOINT_INTERVAL: int = 25
    AUDIT_SALT: str = "argus_default_blind_index_salt_2026"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()
