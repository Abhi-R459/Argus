"""Set runtime role passwords from deployment secrets without storing defaults."""

from __future__ import annotations

import os
import sys

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    admin_url = os.environ.get("DATABASE_URL_MIGRATIONS")
    credentials = {
        "hr_admin": os.environ.get("HR_ADMIN_PASSWORD", ""),
        "compliance_auditor": os.environ.get("COMPLIANCE_AUDITOR_PASSWORD", ""),
    }
    if not admin_url:
        print("DATABASE_URL_MIGRATIONS is required.", file=sys.stderr)
        return 2
    if any(len(password) < 32 for password in credentials.values()):
        print(
            "Set HR_ADMIN_PASSWORD and COMPLIANCE_AUDITOR_PASSWORD to distinct random values of at least 32 characters.",
            file=sys.stderr,
        )
        return 2
    if len(set(credentials.values())) != len(credentials):
        print("Runtime database roles must use different passwords.", file=sys.stderr)
        return 2

    connection = psycopg2.connect(admin_url)
    try:
        with connection.cursor() as cursor:
            for role, password in credentials.items():
                statement = sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
                cursor.execute(statement)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    print("Runtime database role passwords have been provisioned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
