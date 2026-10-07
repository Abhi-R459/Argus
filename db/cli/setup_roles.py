"""Apply the Argus least-privilege runtime role grants to the current database."""

from __future__ import annotations

from pathlib import Path

import psycopg2
from dotenv import load_dotenv

from db.cli.db_url import resolve_db_url


def main() -> int:
    """Run the reviewed role grant script using the migration connection."""
    load_dotenv()
    database_url = resolve_db_url()
    sql_path = Path(__file__).resolve().parents[1] / "scripts" / "setup_roles.sql"
    role_sql = sql_path.read_text(encoding="utf-8")

    connection = psycopg2.connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(role_sql)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    print("Argus runtime role grants have been applied to the selected database.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
