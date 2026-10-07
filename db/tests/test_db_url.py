"""Tests for safe database URL resolution used by command-line tools."""

import pytest

from db.cli.db_url import resolve_db_url


def test_explicit_url_takes_precedence_over_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL_MIGRATIONS", "postgresql://env/db")
    monkeypatch.setenv("DATABASE_URL", "postgresql://compat/db")

    assert resolve_db_url("postgresql+asyncpg://explicit/db") == "postgresql://explicit/db"


def test_migration_url_is_used_when_runtime_url_is_also_present(monkeypatch):
    monkeypatch.setenv("DATABASE_URL_MIGRATIONS", "postgresql://migration/db")
    monkeypatch.setenv("DATABASE_URL", "postgresql://compat/db")
    monkeypatch.setattr("dotenv.load_dotenv", lambda: None)

    assert resolve_db_url() == "postgresql://migration/db"


def test_generic_runtime_url_is_not_used_implicitly(monkeypatch):
    monkeypatch.delenv("DATABASE_URL_MIGRATIONS", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://runtime-role/db")
    monkeypatch.setattr("dotenv.load_dotenv", lambda: None)

    with pytest.raises(ValueError, match="DATABASE_URL_MIGRATIONS"):
        resolve_db_url()


def test_missing_database_url_fails_without_default_credentials(monkeypatch):
    monkeypatch.delenv("DATABASE_URL_MIGRATIONS", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda: None)

    with pytest.raises(ValueError, match="Database URL is required"):
        resolve_db_url()


def test_sqlalchemy_psycopg2_scheme_is_normalized_for_libpq():
    assert resolve_db_url("postgresql+psycopg2://dbuser@db/argus") == "postgresql://dbuser@db/argus"
