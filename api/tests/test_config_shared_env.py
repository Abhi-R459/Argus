from api.config import Settings


def test_settings_ignore_configuration_owned_by_other_services():
    settings = Settings(
        _env_file=None,
        DATABASE_URL_HR_ADMIN="postgresql+asyncpg://hr_admin@localhost/argus",
        DATABASE_URL_COMPLIANCE_AUDITOR=(
            "postgresql+asyncpg://compliance_auditor@localhost/argus"
        ),
        POSTGRES_PASSWORD="local-only",
        MIGRATIONS_DATABASE_URL="postgresql://migration-only",
        VITE_API_URL="/api",
    )

    assert settings.DATABASE_URL_HR_ADMIN.endswith("localhost/argus")
    assert settings.DATABASE_URL_COMPLIANCE_AUDITOR.endswith("localhost/argus")
