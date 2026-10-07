"""Shared database URL resolution for command-line database tools."""

from __future__ import annotations

import os


def resolve_db_url(db_url: str | None = None) -> str:
    """Resolve an explicit or configured database URL without unsafe defaults.

    Administrative CLIs require the dedicated migration/administration URL.
    Generic ``DATABASE_URL`` may refer to a less privileged runtime role and is
    deliberately not used implicitly. A URL is never synthesized from defaults.
    """
    url = db_url
    if not url:
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass
        url = os.environ.get("DATABASE_URL_MIGRATIONS")

    if not url:
        raise ValueError(
            "Database URL is required. Pass --db-url or configure DATABASE_URL_MIGRATIONS."
        )

    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    elif url.startswith("postgresql+psycopg2://"):
        url = url.replace("postgresql+psycopg2://", "postgresql://", 1)
    return url
