"""Launch checks that may run only against an explicitly disposable database."""

import os
import time
from concurrent.futures import ThreadPoolExecutor

import psycopg2
import pytest
from sqlalchemy.engine import make_url

from db.crypto.actor_context import create_actor_context
from db.cli import actor_context_keys
from db.crypto.pii import encrypt_pii, set_employee_audit_context


@pytest.fixture(scope="module")
def launch_database():
    dsn = os.environ.get("ARGUS_TEST_DATABASE_URL", "")
    expected = os.environ.get("ARGUS_TEST_DATABASE_NAME", "")
    if not dsn or os.environ.get("ARGUS_ENABLE_DESTRUCTIVE_TESTS") != "I_CONFIRM_DISPOSABLE_DATABASE":
        pytest.skip("Explicit disposable database configuration is required.")
    url = make_url(dsn)
    if not expected.endswith("_test") or url.database != expected:
        pytest.fail("Refusing launch checks against an unconfirmed test database.")
    with psycopg2.connect(dsn) as conn, conn.cursor() as cursor:
        cursor.execute("SELECT version_num FROM alembic_version")
        assert cursor.fetchone()[0] == "030_definer_schema_usage"
        cursor.execute("INSERT INTO departments(name) VALUES ('Launch Check') RETURNING department_id")
        department = cursor.fetchone()[0]
        cursor.execute("INSERT INTO roles(title,department_id,salary_band_min,salary_band_max) VALUES ('Engineer',%s,1,1000000) RETURNING role_id", (department,))
        role = cursor.fetchone()[0]
        cursor.execute("INSERT INTO users(clerk_user_id,full_name,email,role,is_active) VALUES ('launch:test','Launch Test','launch@example.test','hr_admin',true) RETURNING user_id")
        actor = cursor.fetchone()[0]
        set_employee_audit_context(cursor, 'test-national-id')
        cursor.execute("INSERT INTO employees(full_name,email,role_id,national_id_encrypted,contact_info_encrypted,date_hired) VALUES ('Test Person','person@example.test',%s,%s,%s,CURRENT_DATE) RETURNING employee_id", (
            role, encrypt_pii('test-national-id', 'national_id', os.environ['PII_ENCRYPTION_KEY']),
            encrypt_pii('test-contact', 'contact_info', os.environ['PII_ENCRYPTION_KEY'])))
        employee = cursor.fetchone()[0]
    return {"actor": actor, "employee": employee}


def _runtime(role):
    name = "DATABASE_URL_HR_ADMIN" if role == "hr_admin" else "DATABASE_URL_COMPLIANCE_AUDITOR"
    return make_url(os.environ[name]).set(drivername="postgresql").render_as_string(hide_password=False)


def test_runtime_request_budget_works_under_schema_lockdown(launch_database):
    with psycopg2.connect(_runtime('hr_admin')) as conn, conn.cursor() as cursor:
        cursor.execute("SELECT has_schema_privilege('public','USAGE')")
        assert cursor.fetchone()[0] is True
        cursor.execute("SELECT allowed,retry_after FROM argus_private.consume_request_budget(%s,'api',120)", (launch_database['actor'],))
        allowed, retry_after = cursor.fetchone()
        assert allowed is True and 1 <= retry_after <= 60
        conn.rollback()


def test_supabase_session_helper_revokes_logout_and_banned_users(launch_database):
    """Simulate Auth tables only in the explicitly disposable database."""
    user_id = '1ac1a96e-09fb-4dc8-a34a-cc2ac0dbe699'
    session_id = 'ab8c1e92-e2c0-44ea-8f31-6fb78bddba4f'
    admin = os.environ['ARGUS_TEST_DATABASE_URL']
    with psycopg2.connect(admin) as conn, conn.cursor() as cursor:
        cursor.execute("CREATE SCHEMA auth")
        cursor.execute("CREATE TABLE auth.users(id uuid PRIMARY KEY, banned_until timestamptz, deleted_at timestamptz, encrypted_password text)")
        cursor.execute("CREATE TABLE auth.sessions(id uuid PRIMARY KEY, user_id uuid, not_after timestamptz, refresh_token_hmac_key text)")
        cursor.execute("GRANT SELECT(id,user_id,not_after) ON auth.sessions TO argus_auth_reader")
        cursor.execute("GRANT SELECT(id,banned_until,deleted_at) ON auth.users TO argus_auth_reader")
        import importlib
        cursor.execute(importlib.import_module('db.alembic.versions.028_bound_auth_session_check').SQL)
        cursor.execute("SELECT has_schema_privilege('argus_auth_reader','auth','USAGE')")
        assert cursor.fetchone()[0] is False
        cursor.execute("INSERT INTO auth.users(id) VALUES (%s)", (user_id,))
        cursor.execute("INSERT INTO auth.sessions(id,user_id) VALUES (%s,%s)", (session_id,user_id))
        # Supabase Auth tables use managed RLS without policies for custom roles.
        cursor.execute("ALTER TABLE auth.users ENABLE ROW LEVEL SECURITY")
        cursor.execute("ALTER TABLE auth.sessions ENABLE ROW LEVEL SECURITY")
        cursor.execute(importlib.import_module('db.alembic.versions.029_managed_auth_rls').SQL)
        cursor.execute("SELECT has_function_privilege('hr_admin','argus_private.supabase_session_active(uuid,uuid)','EXECUTE'), has_table_privilege('hr_admin','auth.users','SELECT')")
        assert cursor.fetchone() == (True, False)
        cursor.execute("SELECT rolcanlogin,rolsuper,rolbypassrls FROM pg_roles WHERE rolname='argus_auth_reader'")
        assert cursor.fetchone() == (False,False,False)
        cursor.execute("SELECT has_column_privilege('argus_auth_reader','auth.sessions','refresh_token_hmac_key','SELECT'), has_column_privilege('argus_auth_reader','auth.users','encrypted_password','SELECT')")
        assert cursor.fetchone() == (False,False)
        cursor.execute("SELECT has_function_privilege('compliance_auditor','argus_private.supabase_session_active(uuid,uuid)','EXECUTE')")
        assert cursor.fetchone()[0] is False

    def active(candidate_user=user_id):
        with psycopg2.connect(_runtime('hr_admin')) as conn, conn.cursor() as cursor:
            cursor.execute("SELECT argus_private.supabase_session_active(%s,%s)", (candidate_user,session_id))
            return cursor.fetchone()[0]
    assert active() is True
    assert active(session_id) is False
    for column in ('banned_until','deleted_at'):
        with psycopg2.connect(admin) as conn, conn.cursor() as cursor:
            cursor.execute(f"UPDATE auth.users SET {column}=now()+interval '1 hour'")
        assert active() is False
        with psycopg2.connect(admin) as conn, conn.cursor() as cursor:
            cursor.execute(f"UPDATE auth.users SET {column}=NULL")
    with psycopg2.connect(admin) as conn, conn.cursor() as cursor:
        cursor.execute("UPDATE auth.sessions SET not_after=now()-interval '1 minute'")
    assert active() is False

    with psycopg2.connect(admin) as conn, conn.cursor() as cursor:
        cursor.execute("UPDATE auth.sessions SET not_after=NULL")
    assert active() is True
    with psycopg2.connect(_runtime('hr_admin')) as conn, conn.cursor() as cursor:
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cursor.execute("SELECT * FROM auth.sessions")
    with psycopg2.connect(admin) as conn, conn.cursor() as cursor:
        cursor.execute("DELETE FROM auth.sessions")
    assert active() is False

def test_session_migration_restores_restricted_migration_owner(launch_database):
    import importlib
    migration_sql = importlib.import_module('db.alembic.versions.027_supabase_sessions').SQL
    migration_sql = migration_sql.replace('argus_auth_reader', 'argus_auth_reader_test').replace('supabase_session_active', 'supabase_session_active_test')
    admin = os.environ['ARGUS_TEST_DATABASE_URL']
    with psycopg2.connect(admin) as conn, conn.cursor() as cursor:
        cursor.execute("CREATE ROLE launch_auth_migrator LOGIN CREATEROLE NOSUPERUSER NOINHERIT PASSWORD 'disposable-auth-migration-only'")
        cursor.execute("GRANT argus_audit_owner TO launch_auth_migrator WITH ADMIN TRUE, INHERIT FALSE, SET FALSE")
        cursor.execute("GRANT USAGE ON SCHEMA auth TO launch_auth_migrator WITH GRANT OPTION")
        cursor.execute("GRANT SELECT(id,user_id,not_after) ON auth.sessions TO launch_auth_migrator WITH GRANT OPTION")
        cursor.execute("GRANT SELECT(id,banned_until,deleted_at) ON auth.users TO launch_auth_migrator WITH GRANT OPTION")
    url = make_url(admin).set(drivername='postgresql',username='launch_auth_migrator',password='disposable-auth-migration-only')
    try:
        with psycopg2.connect(url.render_as_string(hide_password=False)) as conn, conn.cursor() as cursor:
            cursor.execute(migration_sql)
            bound_sql = importlib.import_module('db.alembic.versions.028_bound_auth_session_check').SQL
            bound_sql = bound_sql.replace('argus_auth_reader', 'argus_auth_reader_test').replace('supabase_session_active', 'supabase_session_active_test')
            cursor.execute(bound_sql)
            cursor.execute("SELECT pg_has_role(current_user,'argus_audit_owner','USAGE'),pg_has_role(current_user,'argus_audit_owner','SET')")
            assert cursor.fetchone() == (False,False)
    finally:
        with psycopg2.connect(admin) as conn, conn.cursor() as cursor:
            cursor.execute("SELECT to_regrole('argus_auth_reader_test')")
            if cursor.fetchone()[0] is not None:
                # Column grants belong to the restricted migration administrator.
                # Revoke as that grantor before removing this disposable test role.
                cursor.execute("SET ROLE launch_auth_migrator")
                cursor.execute("REVOKE SELECT(id,user_id,not_after) ON auth.sessions FROM argus_auth_reader_test")
                cursor.execute("REVOKE SELECT(id,banned_until,deleted_at) ON auth.users FROM argus_auth_reader_test")
                cursor.execute("REVOKE USAGE ON SCHEMA auth FROM argus_auth_reader_test")
                cursor.execute("RESET ROLE")
                cursor.execute("DROP OWNED BY argus_auth_reader_test")
                cursor.execute("DROP ROLE argus_auth_reader_test")
            cursor.execute("DROP OWNED BY launch_auth_migrator")
            cursor.execute("DROP ROLE launch_auth_migrator")



@pytest.mark.parametrize('own_grant', [False, True])
def test_actor_key_rotation_restores_restricted_administrator_membership(launch_database, monkeypatch, own_grant):
    import sys

    dsn = os.environ['ARGUS_TEST_DATABASE_URL']
    original_key = os.environ.get('AUDIT_CONTEXT_KEY_ID', 'v1')
    rotation_key = 'rotation-own' if own_grant else 'rotation-admin'
    with psycopg2.connect(dsn) as conn, conn.cursor() as cursor:
        cursor.execute("SELECT current_setting('server_version_num')::integer")
        if cursor.fetchone()[0] < 160000:
            pytest.skip('PostgreSQL 16+ membership options are required.')
        cursor.execute("CREATE ROLE launch_key_admin LOGIN CREATEROLE NOSUPERUSER PASSWORD 'isolated-key-admin-only'")
        cursor.execute("GRANT argus_audit_owner TO launch_key_admin WITH ADMIN TRUE, INHERIT FALSE, SET FALSE")
    try:
        url = make_url(dsn).set(username='launch_key_admin', password='isolated-key-admin-only', drivername='postgresql')
        if own_grant:
            with psycopg2.connect(url.render_as_string(hide_password=False)) as conn, conn.cursor() as cursor:
                # PostgreSQL prohibits a role from granting ADMIN back to itself.
                # Keep the original external ADMIN grant and a restricted own grant.
                cursor.execute("GRANT argus_audit_owner TO CURRENT_USER WITH ADMIN FALSE, INHERIT FALSE, SET FALSE")
        with psycopg2.connect(dsn) as conn, conn.cursor() as cursor:
            cursor.execute("SELECT grantor, admin_option, inherit_option, set_option FROM pg_auth_members WHERE roleid='argus_audit_owner'::regrole AND member='launch_key_admin'::regrole ORDER BY grantor")
            original_grants = cursor.fetchall()
        monkeypatch.setenv('DATABASE_URL_MIGRATIONS', url.render_as_string(hide_password=False))
        monkeypatch.setenv('AUDIT_CONTEXT_KEY_ID', rotation_key)
        monkeypatch.setenv('AUDIT_CONTEXT_SECRET', 'ab' * 32)
        monkeypatch.setattr(sys, 'argv', ['actor_context_keys', 'add', '--key-id', rotation_key])
        assert actor_context_keys.main() == 0
        monkeypatch.setattr(sys, 'argv', ['actor_context_keys', 'disable', '--key-id', rotation_key])
        assert actor_context_keys.main() == 0
        monkeypatch.setattr(sys, 'argv', ['actor_context_keys', 'disable', '--key-id', original_key])
        with pytest.raises(ValueError, match='last enabled'):
            actor_context_keys.main()
        with psycopg2.connect(dsn) as conn, conn.cursor() as cursor:
            cursor.execute("SELECT grantor, admin_option, inherit_option, set_option FROM pg_auth_members WHERE roleid='argus_audit_owner'::regrole AND member='launch_key_admin'::regrole ORDER BY grantor")
            assert cursor.fetchall() == original_grants
            cursor.execute("SELECT pg_has_role('launch_key_admin','argus_audit_owner','SET'), pg_has_role('hr_admin','argus_audit_owner','MEMBER'), pg_has_role('compliance_auditor','argus_audit_owner','MEMBER')")
            assert cursor.fetchone() == (False, False, False)
            cursor.execute("SELECT count(*) FROM argus_private.actor_context_keys WHERE enabled AND key_id=%s", (original_key,))
            assert cursor.fetchone()[0] == 1
    finally:
        with psycopg2.connect(dsn) as conn, conn.cursor() as cursor:
            cursor.execute('DROP ROLE launch_key_admin')


def test_rls_keeps_runtime_reads_and_auditor_pii_isolation(launch_database):
    with psycopg2.connect(os.environ['ARGUS_TEST_DATABASE_URL']) as conn, conn.cursor() as cursor:
        cursor.execute("SELECT bool_and(relrowsecurity) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r'")
        assert cursor.fetchone()[0] is True
    with psycopg2.connect(_runtime('hr_admin')) as conn, conn.cursor() as cursor:
        cursor.execute("SELECT email FROM employees WHERE employee_id=%s", (launch_database['employee'],))
        assert cursor.fetchone()[0] == 'person@example.test'
    with psycopg2.connect(_runtime('compliance_auditor')) as conn, conn.cursor() as cursor:
        cursor.execute("SELECT email FROM v_compliance_employee_directory WHERE employee_id=%s", (launch_database['employee'],))
        assert cursor.fetchone()[0] != 'person@example.test'
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cursor.execute('SELECT email FROM employees')


def test_hr_writes_still_require_signed_actor_and_append_audit(launch_database):
    dsn = _runtime('hr_admin')
    with psycopg2.connect(dsn) as conn, conn.cursor() as cursor:
        with pytest.raises(psycopg2.Error, match='signed actor context'):
            cursor.execute('UPDATE employees SET full_name=full_name WHERE employee_id=%s', (launch_database['employee'],))
        conn.rollback()
        context = create_actor_context(actor_user_id=launch_database['actor'], actor_employee_id=0,
            db_role='hr_admin', secret_hex=os.environ['AUDIT_CONTEXT_SECRET'], key_id=os.environ.get('AUDIT_CONTEXT_KEY_ID','v1'))
        for key, value in context.items():
            setting = {'version':'actor_context_version', 'key_id':'actor_context_key_id', 'db_role':'actor_db_role', 'nonce':'actor_nonce', 'issued_at':'actor_issued_at', 'expires_at':'actor_expires_at', 'signature':'actor_signature'}.get(key, key)
            cursor.execute('SELECT set_config(%s,%s,true)', ('argus.'+setting, value))
        cursor.execute('SELECT set_config(%s,%s,true)', ('argus.audit_salt',os.environ['AUDIT_SALT']))
        set_employee_audit_context(cursor, 'test-national-id')
        cursor.execute("UPDATE employees SET full_name='Updated Test Person' WHERE employee_id=%s", (launch_database['employee'],))
        cursor.execute('SELECT actor_user_id FROM audit_log ORDER BY sequence_id DESC LIMIT 1')
        assert cursor.fetchone()[0] == launch_database['actor']
        conn.rollback()


def test_request_budgets_are_atomic_across_connections(launch_database):
    window = int(time.time()) // 60
    def consume(_):
        with psycopg2.connect(_runtime('hr_admin')) as conn, conn.cursor() as cursor:
            cursor.execute("SELECT allowed,retry_after FROM argus_private.consume_request_budget(%s,'api',3)", (launch_database['actor'],))
            return cursor.fetchone()[0]
    with ThreadPoolExecutor(max_workers=6) as executor:
        allowed = list(executor.map(consume, range(12)))
    if int(time.time()) // 60 != window:
        pytest.skip('The wall clock crossed a request-budget window during this concurrency check.')
    assert sum(allowed) == 3
    assert consume(None) is False
    with psycopg2.connect(_runtime('hr_admin')) as conn, conn.cursor() as cursor:
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cursor.execute('SELECT * FROM argus_private.request_budgets')


def test_real_api_bootstrap_employee_and_checkpoint(launch_database, tmp_path, monkeypatch):
    """Use actual SQL roles and triggers; only external Auth verification is replaced."""
    import asyncio
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from httpx import AsyncClient, ASGITransport
    from api.main import app
    from api.middleware.supabase_auth import verify_supabase_token
    from api.config import get_settings
    from api.database import init_engines, dispose_engines

    key = Ed25519PrivateKey.generate()
    key_path = tmp_path / 'private.pem'
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    monkeypatch.setattr(get_settings(), 'SIGNING_PRIVATE_KEY_PATH', str(key_path))
    monkeypatch.setattr(get_settings(), 'CHECKPOINT_PUBLIC_KEYS_DIR', str(tmp_path))
    (tmp_path / 'public_key.pem').write_bytes(key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    app.dependency_overrides[verify_supabase_token] = lambda: {'sub': 'launch:test', 'email': 'launch@example.test', 'email_verified': True, 'argus_role': 'hr_admin'}

    async def run():
        await init_engines()
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url='http://launch.test') as client:
                assert (await client.get('/api/health/ready')).status_code == 200
                department = await client.post('/api/departments', json={'name': 'API Bootstrap'})
                assert department.status_code == 201, department.text
                role = await client.post('/api/roles', json={'title': 'API Engineer',
                    'department_id': department.json()['department_id'],
                    'salary_band_min': '100000', 'salary_band_max': '900000'})
                assert role.status_code == 201, role.text
                employee = await client.post('/api/employees', json={'full_name': 'API Test Person',
                    'email': 'api-test@example.com', 'role_id': role.json()['role_id'],
                    'national_id': 'api-test-national-id', 'contact_info': 'api-test-contact',
                    'date_hired': '2020-01-01', 'salary': '500000'})
                assert employee.status_code == 201, employee.text
                employee_id = employee.json()['employee_id']
                salary = await client.post(f'/api/employees/{employee_id}/salary', json={
                    'amount': '600000', 'effective_date': '2020-02-01'})
                assert salary.status_code in (200, 201), salary.text
                rejected_salary = await client.post(f'/api/employees/{employee_id}/salary', json={
                    'amount': '100000', 'effective_date': '2020-03-01'})
                assert rejected_salary.status_code == 422, rejected_salary.text
                profile = await client.patch(f'/api/employees/{employee_id}', json={
                    'full_name': 'API Test Person Updated'})
                assert profile.status_code == 200, profile.text
                deactivated = await client.delete(f'/api/employees/{employee_id}')
                assert deactivated.status_code == 200, deactivated.text
                assert deactivated.json()['is_active'] is False
                with psycopg2.connect(os.environ['ARGUS_TEST_DATABASE_URL']) as conn, conn.cursor() as cursor:
                    cursor.execute('SELECT is_active FROM employees WHERE employee_id=%s', (employee_id,))
                    assert cursor.fetchone()[0] is False
                    cursor.execute("SELECT new_value->>'national_id_blind_index' FROM audit_log WHERE employee_id=%s AND table_name='employees' ORDER BY sequence_id", (employee_id,))
                    blind_indexes = [row[0] for row in cursor.fetchall()]
                    assert len(blind_indexes) >= 3
                    assert blind_indexes[0] is not None
                    assert len(set(blind_indexes)) == 1
                batch_template = {'full_name': 'Batch QA Employee',
                    'role_id': role.json()['role_id'], 'contact_info': 'Fictional batch QA contact',
                    'date_hired': '2020-01-01', 'salary': '500000'}
                batch_rows = [{**batch_template, 'email': f'batch-qa-{index}@example.com',
                    'national_id': f'batch-national-id-{index}'} for index in range(2)]
                batch = await client.post('/api/employees/batch', json={'employees': batch_rows})
                assert batch.status_code == 201, batch.text
                assert len(batch.json()) == 2
                exact_directory = await client.get(f"/api/employees?employee_id={batch.json()[-1]['employee_id']}&limit=1")
                assert exact_directory.status_code == 200, exact_directory.text
                assert exact_directory.json()['total'] == 1
                assert exact_directory.json()['items'][0]['employee_id'] == batch.json()[-1]['employee_id']
                # A later row failure must undo earlier employee, salary AND audit inserts.
                bad_rows = [{**batch_rows[0], 'email': 'must-rollback@example.com'},
                    {**batch_rows[1], 'email': 'bad-role@example.com', 'role_id': 2147483647}]
                rejected_batch = await client.post('/api/employees/batch', json={'employees': bad_rows})
                assert rejected_batch.status_code == 422, rejected_batch.text
                with psycopg2.connect(os.environ['ARGUS_TEST_DATABASE_URL']) as conn, conn.cursor() as cursor:
                    cursor.execute("SELECT count(*) FROM employees WHERE email IN ('must-rollback@example.com','bad-role@example.com')")
                    assert cursor.fetchone()[0] == 0
                    batch_ids = [row['employee_id'] for row in batch.json()]
                    cursor.execute('SELECT employee_id, national_id_encrypted, contact_info_encrypted FROM employees WHERE employee_id = ANY(%s)', (batch_ids,))
                    stored = cursor.fetchall()
                    assert len(stored) == 2
                    from db.crypto.pii import decrypt_pii
                    for stored_id, national, contact in stored:
                        source = batch_rows[batch_ids.index(stored_id)]
                        assert decrypt_pii(bytes(national), 'national_id', get_settings().PII_ENCRYPTION_KEY) == source['national_id']
                        assert decrypt_pii(bytes(contact), 'contact_info', get_settings().PII_ENCRYPTION_KEY) == source['contact_info']
                    cursor.execute("SELECT new_value->>'national_id_blind_index' FROM audit_log WHERE employee_id = ANY(%s) AND table_name='employees'", (batch_ids,))
                    assert len(set(row[0] for row in cursor.fetchall())) == 2
                    cursor.execute("SELECT count(*) FROM audit_log WHERE new_value->>'email' = 'must-rollback@example.com'")
                    assert cursor.fetchone()[0] == 0
                checkpoint = await client.post('/api/checkpoints/create')
                assert checkpoint.status_code == 200, checkpoint.text
                assert checkpoint.json()['entries_sealed'] >= 3
                with psycopg2.connect(os.environ['ARGUS_TEST_DATABASE_URL']) as conn, conn.cursor() as cursor:
                    cursor.execute('SELECT checkpoint_hash,merkle_root,signature FROM chain_checkpoints WHERE checkpoint_id=%s', (checkpoint.json()['checkpoint_id'],))
                    checkpoint_hash, root, signature = cursor.fetchone()
                    key.public_key().verify(bytes(signature), f'{checkpoint_hash}:{root}'.encode())
                    cursor.execute('SELECT national_id_encrypted FROM employees WHERE employee_id=%s', (employee_id,))
                    assert b'api-test-national-id' not in bytes(cursor.fetchone()[0])
                    cursor.execute("INSERT INTO users(clerk_user_id,full_name,email,role,is_active) VALUES ('launch:auditor','Audit Test','audit-launch@example.test','compliance_auditor',true)")
                app.dependency_overrides[verify_supabase_token] = lambda: {'sub': 'launch:auditor', 'email': 'audit-launch@example.test', 'email_verified': True, 'argus_role': 'compliance_auditor'}
                directory = await client.get('/api/employees')
                assert directory.status_code == 200, directory.text
                assert all(row['email'] != 'api-test@example.com' for row in directory.json()['items'])
                exact_redacted = await client.get(f'/api/employees?employee_id={employee_id}&limit=1')
                assert exact_redacted.status_code == 200, exact_redacted.text
                assert exact_redacted.json()['total'] == 1
                assert exact_redacted.json()['items'][0]['employee_id'] == employee_id
                assert exact_redacted.json()['items'][0]['pii_redacted'] is True
                assert (await client.post('/api/checkpoints/create')).status_code == 403
                assert (await client.post('/api/employees/batch', json={'employees': batch_rows})).status_code == 403
                refreshed = await client.post('/api/suspicious-activity/refresh')
                assert refreshed.status_code == 200, refreshed.text
                # Interactive refresh must report contention with another detector.
                with psycopg2.connect(os.environ['ARGUS_TEST_DATABASE_URL']) as lock_conn, lock_conn.cursor() as cursor:
                    from api.routers.audits import SUSPICIOUS_ACTIVITY_REFRESH_LOCK_KEY
                    cursor.execute('SELECT pg_advisory_xact_lock(%s)', (SUSPICIOUS_ACTIVITY_REFRESH_LOCK_KEY,))
                    busy_refresh = await client.post('/api/suspicious-activity/refresh')
                    assert busy_refresh.status_code == 409, busy_refresh.text
                capsule = await client.get(f"/api/audit-logs/{checkpoint.json()['sequence_id']}/capsule")
                assert capsule.status_code == 200, capsule.text
                from db.cli.verify_capsule import verify_capsule
                valid, message, _ = verify_capsule(capsule.content, trusted_public_key_pem=(tmp_path / 'public_key.pem').read_text())
                assert valid, message
                import io, json, zipfile
                bundle = await client.get('/api/audit-logs/export-pack')
                assert bundle.status_code == 200, bundle.text
                with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
                    exported_checkpoints = json.loads(archive.read('checkpoints.json'))
                exported = next(cp for cp in exported_checkpoints if cp['checkpoint_id'] == checkpoint.json()['checkpoint_id'])
                assert exported['merkle_root'] == root
                key.public_key().verify(bytes.fromhex(exported['signature_hex']),
                    f"{exported['checkpoint_hash']}:{exported['merkle_root']}".encode())
        finally:
            app.dependency_overrides.clear()
            await dispose_engines()
    asyncio.run(run())
