"""Launch checks that may run only against an explicitly disposable database."""

import os
import time
from concurrent.futures import ThreadPoolExecutor

import psycopg2
import pytest
from sqlalchemy.engine import make_url

from db.crypto.actor_context import create_actor_context
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
        assert cursor.fetchone()[0] == "026_checkpoint_boundary_lock"
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
    """Use actual SQL roles and triggers; only external Clerk verification is replaced."""
    import asyncio
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from httpx import AsyncClient, ASGITransport
    from api.main import app
    from api.middleware.clerk import verify_clerk_token
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
    app.dependency_overrides[verify_clerk_token] = lambda: {'sub': 'launch:test'}

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
                app.dependency_overrides[verify_clerk_token] = lambda: {'sub': 'launch:auditor'}
                directory = await client.get('/api/employees')
                assert directory.status_code == 200, directory.text
                assert all(row['email'] != 'api-test@example.com' for row in directory.json()['items'])
                assert (await client.post('/api/checkpoints/create')).status_code == 403
                capsule = await client.get(f"/api/audit-logs/{checkpoint.json()['sequence_id']}/capsule")
                assert capsule.status_code == 200, capsule.text
                from db.cli.verify_capsule import verify_capsule
                valid, message, _ = verify_capsule(capsule.content, trusted_public_key_pem=(tmp_path / 'public_key.pem').read_text())
                assert valid, message
        finally:
            app.dependency_overrides.clear()
            await dispose_engines()
    asyncio.run(run())
