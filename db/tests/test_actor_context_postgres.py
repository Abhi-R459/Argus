"""Opt-in adversarial checks for a disposable PostgreSQL database only."""

from __future__ import annotations

import os
import time
import uuid

import psycopg2
import pytest

from db.crypto.actor_context import create_actor_context


pytestmark = pytest.mark.skipif(
    os.getenv("ARGUS_RUN_DB_SECURITY_TESTS") != "1",
    reason="Set ARGUS_RUN_DB_SECURITY_TESTS=1 only for an isolated disposable PostgreSQL database.",
)


def _psycopg_dsn(value: str) -> str:
    return value.replace("postgresql+asyncpg://", "postgresql://", 1)


def _set_actor_context(cursor, context: dict[str, str]) -> None:
    cursor.execute(
        "SELECT set_config('argus.actor_context_version', %(version)s, true), "
        "set_config('argus.actor_context_key_id', %(key_id)s, true), "
        "set_config('argus.actor_user_id', %(actor_user_id)s, true), "
        "set_config('argus.actor_employee_id', %(actor_employee_id)s, true), "
        "set_config('argus.actor_db_role', %(db_role)s, true), "
        "set_config('argus.actor_nonce', %(nonce)s, true), "
        "set_config('argus.actor_issued_at', %(issued_at)s, true), "
        "set_config('argus.actor_expires_at', %(expires_at)s, true), "
        "set_config('argus.actor_signature', %(signature)s, true), "
        "set_config('argus.audit_salt', %(salt)s, true)",
        {**context, "salt": os.environ["AUDIT_SALT"]},
    )


def test_runtime_db_role_rejects_spoofed_guc_and_accepts_signed_actor_context():
    migration_dsn = _psycopg_dsn(os.environ["DATABASE_URL_MIGRATIONS"])
    runtime_dsn = _psycopg_dsn(os.environ["DATABASE_URL_HR_ADMIN"])
    key = os.environ["AUDIT_CONTEXT_SECRET"]
    key_id = os.getenv("AUDIT_CONTEXT_KEY_ID", "v1")
    admin = psycopg2.connect(migration_dsn)
    runtime = psycopg2.connect(runtime_dsn)
    actor_email = f"actor-context-{uuid.uuid4()}@argus.invalid"
    actor_id = None
    try:
        with admin.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (clerk_user_id, full_name, email, role, is_active) "
                "VALUES (%s, %s, %s, 'hr_admin', FALSE) RETURNING user_id",
                (f"test:{uuid.uuid4()}", "Actor Context Test", actor_email),
            )
            actor_id = cursor.fetchone()[0]
            cursor.execute("SELECT employee_id FROM employees ORDER BY employee_id LIMIT 1")
            employee_id = cursor.fetchone()[0]
        admin.commit()

        # A database client can set the legacy GUCs, but cannot authenticate with them.
        with runtime.cursor() as cursor:
            cursor.execute("SELECT set_config('argus.actor_user_id', %s, true)", (str(actor_id),))
            cursor.execute("SELECT set_config('argus.actor_employee_id', '0', true)")
            cursor.execute("SELECT set_config('argus.audit_salt', %s, true)", (os.environ["AUDIT_SALT"],))
            with pytest.raises(psycopg2.Error, match="signed actor context"):
                cursor.execute(
                    "UPDATE employees SET full_name = full_name WHERE employee_id = %s",
                    (employee_id,),
                )
        runtime.rollback()

        context = create_actor_context(
            actor_user_id=actor_id,
            actor_employee_id=0,
            db_role="hr_admin",
            secret_hex=key,
            key_id=key_id,
        )
        with runtime.cursor() as cursor:
            _set_actor_context(cursor, context)
            cursor.execute(
                "UPDATE employees SET full_name = full_name WHERE employee_id = %s",
                (employee_id,),
            )
            cursor.execute(
                "SELECT actor_user_id FROM audit_log "
                "WHERE table_name = 'employees' AND row_id = %s "
                "ORDER BY sequence_id DESC LIMIT 1",
                (employee_id,),
            )
            assert cursor.fetchone()[0] == actor_id
        runtime.rollback()
    finally:
        runtime.close()
        if actor_id is not None:
            with admin.cursor() as cursor:
                cursor.execute("DELETE FROM users WHERE user_id = %s", (actor_id,))
            admin.commit()
        admin.close()


def test_actor_verifier_objects_are_not_readable_or_mutable_by_hr_role():
    runtime = psycopg2.connect(_psycopg_dsn(os.environ["DATABASE_URL_HR_ADMIN"]))
    try:
        with runtime.cursor() as cursor:
            with pytest.raises(psycopg2.Error):
                cursor.execute("SELECT key_material FROM argus_private.actor_context_keys")
            runtime.rollback()
            with pytest.raises(psycopg2.Error):
                cursor.execute("DELETE FROM argus_private.actor_context_nonces")
            runtime.rollback()
    finally:
        runtime.close()


def test_actor_context_rejects_expired_altered_and_replayed_assertions():
    migration = psycopg2.connect(_psycopg_dsn(os.environ["DATABASE_URL_MIGRATIONS"]))
    runtime = psycopg2.connect(_psycopg_dsn(os.environ["DATABASE_URL_HR_ADMIN"]))
    actor_email = f"actor-context-replay-{uuid.uuid4()}@argus.invalid"
    actor_id = None
    replay_nonce = None
    try:
        with migration.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (clerk_user_id, full_name, email, role, is_active) "
                "VALUES (%s, %s, %s, 'hr_admin', FALSE) RETURNING user_id",
                (f"test:{uuid.uuid4()}", "Actor Context Replay Test", actor_email),
            )
            actor_id = cursor.fetchone()[0]
            cursor.execute("SELECT employee_id FROM employees ORDER BY employee_id LIMIT 1")
            employee_id = cursor.fetchone()[0]
        migration.commit()

        expired = create_actor_context(
            actor_user_id=actor_id,
            actor_employee_id=0,
            db_role="hr_admin",
            secret_hex=os.environ["AUDIT_CONTEXT_SECRET"],
            key_id=os.getenv("AUDIT_CONTEXT_KEY_ID", "v1"),
            now=int(time.time()) - 120,
        )
        with runtime.cursor() as cursor:
            _set_actor_context(cursor, expired)
            with pytest.raises(psycopg2.Error, match="expired"):
                cursor.execute(
                    "UPDATE employees SET full_name = full_name WHERE employee_id = %s",
                    (employee_id,),
                )
        runtime.rollback()

        altered = create_actor_context(
            actor_user_id=actor_id,
            actor_employee_id=0,
            db_role="hr_admin",
            secret_hex=os.environ["AUDIT_CONTEXT_SECRET"],
            key_id=os.getenv("AUDIT_CONTEXT_KEY_ID", "v1"),
        )
        altered["actor_user_id"] = str(actor_id + 1)
        with runtime.cursor() as cursor:
            _set_actor_context(cursor, altered)
            with pytest.raises(psycopg2.Error, match="failed verification"):
                cursor.execute(
                    "UPDATE employees SET full_name = full_name WHERE employee_id = %s",
                    (employee_id,),
                )
        runtime.rollback()

        replayed = create_actor_context(
            actor_user_id=actor_id,
            actor_employee_id=0,
            db_role="hr_admin",
            secret_hex=os.environ["AUDIT_CONTEXT_SECRET"],
            key_id=os.getenv("AUDIT_CONTEXT_KEY_ID", "v1"),
        )
        replay_nonce = replayed["nonce"]
        with migration.cursor() as cursor:
            cursor.execute(
                "INSERT INTO argus_private.actor_context_nonces "
                "(nonce, transaction_id, actor_user_id, actor_employee_id, db_role, signature, expires_at) "
                "VALUES (%s, pg_current_xact_id(), %s, 0, 'hr_admin', decode(%s, 'hex'), to_timestamp(%s))",
                (replay_nonce, actor_id, replayed["signature"], replayed["expires_at"]),
            )
        migration.commit()
        with runtime.cursor() as cursor:
            _set_actor_context(cursor, replayed)
            with pytest.raises(psycopg2.Error, match="already been used"):
                cursor.execute(
                    "UPDATE employees SET full_name = full_name WHERE employee_id = %s",
                    (employee_id,),
                )
        runtime.rollback()
    finally:
        runtime.close()
        if actor_id is not None:
            with migration.cursor() as cursor:
                if replay_nonce:
                    cursor.execute(
                        "DELETE FROM argus_private.actor_context_nonces WHERE nonce = %s",
                        (replay_nonce,),
                    )
                cursor.execute("DELETE FROM users WHERE user_id = %s", (actor_id,))
            migration.commit()
        migration.close()
