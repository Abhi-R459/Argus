"""Migrate and test an explicitly disposable, empty PostgreSQL database.

Never use this with the application database. Requires ARGUS_TEST_DATABASE_URL,
ARGUS_TEST_DATABASE_NAME and the explicit destructive-test opt-in used by CI.
"""

import base64
import os
from pathlib import Path
import secrets
import subprocess
import sys

import psycopg2
from psycopg2 import sql
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def main():
    env = os.environ.copy()
    env['APP_ENV'] = 'development'
    expected = env.get('ARGUS_TEST_DATABASE_NAME', '')
    admin = make_url(env.get('ARGUS_TEST_DATABASE_URL', ''))
    if (env.get('ARGUS_ENABLE_DESTRUCTIVE_TESTS') != 'I_CONFIRM_DISPOSABLE_DATABASE'
            or not expected.endswith('_test') or admin.database != expected):
        raise RuntimeError('An explicitly confirmed disposable test database is required.')
    with psycopg2.connect(admin.set(drivername='postgresql').render_as_string(hide_password=False)) as conn, conn.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
        if cursor.fetchone()[0]:
            raise RuntimeError('Launch checks require an empty disposable database.')
        # Match the hosted schema lockdown; stock PostgreSQL otherwise masks
        # missing USAGE grants for non-login SECURITY DEFINER owners.
        cursor.execute('REVOKE USAGE ON SCHEMA public FROM PUBLIC')
        for role, name in [('hr_admin', 'DATABASE_URL_HR_ADMIN'), ('compliance_auditor', 'DATABASE_URL_COMPLIANCE_AUDITOR')]:
            runtime = make_url(env[name])
            if (runtime.username != role or runtime.database != expected
                    or runtime.host != admin.host or runtime.port != admin.port or not runtime.password):
                raise RuntimeError('Runtime roles must target the same disposable database.')
            cursor.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (role,))
            if cursor.fetchone() is None:
                cursor.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD {}').format(
                    sql.Identifier(role), sql.Literal(runtime.password)))
    env['DATABASE_URL_MIGRATIONS'] = admin.set(drivername='postgresql').render_as_string(hide_password=False)
    env.setdefault('AUDIT_CONTEXT_SECRET', secrets.token_hex(32))
    env.setdefault('AUDIT_CONTEXT_KEY_ID', 'v1')
    env.setdefault('AUDIT_SALT', secrets.token_hex(32))
    env.setdefault('PII_ENCRYPTION_KEY', base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
    subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=ROOT, env=env, check=True)
    subprocess.run([sys.executable, '-m', 'db.cli.setup_roles'], cwd=ROOT, env=env, check=True)
    subprocess.run([sys.executable, '-m', 'pytest', 'db/tests/test_launch_postgres.py', '-q'], cwd=ROOT, env=env, check=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('Disposable launch checks stopped:', type(exc).__name__, file=sys.stderr)
        raise SystemExit(1)
