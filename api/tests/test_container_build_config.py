from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_api_image_includes_shared_database_package_and_excludes_secrets():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    api_build = compose["services"]["api"]["build"]
    assert api_build["context"] == "."
    assert api_build["dockerfile"] == "api/Dockerfile"

    dockerfile = (ROOT / "api" / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY --chown=argus:argus api/ ./api/" in dockerfile
    assert "COPY --chown=argus:argus db/ ./db/" in dockerfile
    assert '"api.main:app"' in dockerfile

    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert ".env" in dockerignore
    assert "**/.env" in dockerignore
    assert "keys/" in dockerignore
    assert "anchor/" in dockerignore

    requirements = (ROOT / "api" / "requirements.txt").read_text(encoding="utf-8")
    assert "psycopg2-binary" in requirements


def test_migrations_run_in_a_separate_one_shot_job():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    migrate = compose["services"]["migrate"]
    assert "ops" in migrate["profiles"]
    assert migrate["restart"] == "no"
    assert "upgrade" in migrate["command"]
    assert "DATABASE_URL_MIGRATIONS" in migrate["environment"]
    assert "DATABASE_URL_MIGRATIONS" not in compose["services"]["api"]["environment"]
    assert "MIGRATIONS_DATABASE_URL" in migrate["environment"]["DATABASE_URL_MIGRATIONS"]
    assert "BACKUP_DATABASE_USER" in compose["services"]["backup"]["environment"]["PGUSER"]
    assert "RESTORE_DATABASE_USER" in compose["services"]["restore"]["environment"]["PGUSER"]

    dockerfile = (ROOT / "api" / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY --chown=argus:argus alembic.ini ./alembic.ini" in dockerfile

    migration_ini = (ROOT / "alembic.ini").read_text(encoding="utf-8")
    assert "%(here)s/db/alembic" in migration_ini


def test_compose_healthcheck_uses_database_readiness_route():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    healthcheck = compose["services"]["api"]["healthcheck"]["test"]
    assert any("/api/health/ready" in item for item in healthcheck)
