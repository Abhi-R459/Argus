"""Provision or retire database verifier keys during an actor-key rotation."""

from __future__ import annotations

import argparse
import os
import sys

import psycopg2
from dotenv import load_dotenv

from db.crypto.actor_context import parse_context_secret, canonical_actor_payload


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("add", "disable"))
    parser.add_argument("--key-id", required=True)
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL_MIGRATIONS")
    if not database_url:
        print("DATABASE_URL_MIGRATIONS is required.", file=sys.stderr)
        return 2

    connection = psycopg2.connect(database_url)
    try:
        with connection.cursor() as cursor:
            if args.action == "add":
                key_id = os.environ.get("AUDIT_CONTEXT_KEY_ID", "")
                secret = parse_context_secret(os.environ.get("AUDIT_CONTEXT_SECRET", ""))
                if key_id != args.key_id:
                    raise ValueError("--key-id must match AUDIT_CONTEXT_KEY_ID in the environment.")
                canonical_actor_payload(
                    key_id=key_id,
                    actor_user_id=1,
                    actor_employee_id=0,
                    db_role="hr_admin",
                    nonce="00000000-0000-0000-0000-000000000000",
                    issued_at=1,
                    expires_at=2,
                )
                cursor.execute(
                    "INSERT INTO argus_private.actor_context_keys (key_id, key_material, enabled) "
                    "VALUES (%s, %s, TRUE)",
                    (key_id, secret),
                )
            else:
                cursor.execute(
                    "SELECT count(*) FROM argus_private.actor_context_keys "
                    "WHERE enabled AND key_id <> %s",
                    (args.key_id,),
                )
                if cursor.fetchone()[0] < 1:
                    raise ValueError("Refusing to disable the last enabled actor-context key.")
                cursor.execute(
                    "UPDATE argus_private.actor_context_keys SET enabled = FALSE WHERE key_id = %s AND enabled",
                    (args.key_id,),
                )
                if cursor.rowcount != 1:
                    raise ValueError("The requested enabled key ID was not found.")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    print(f"Actor-context key {args.action} operation completed for key ID {args.key_id}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
