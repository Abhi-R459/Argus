import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace

pytestmark = pytest.mark.asyncio

async def test_dashboard_stats_hr(client_hr: AsyncClient, mock_db_session: AsyncMock):
    m_active = MagicMock(); m_active.scalar.return_value = 15
    m_total = MagicMock(); m_total.scalar.return_value = 17
    m_audits = MagicMock(); m_audits.scalar.return_value = 49
    m_flags = MagicMock(); m_flags.scalar.return_value = 2
    m_recent = MagicMock(); m_recent.all.return_value = [
        (101, 'INSERT', 'employees', 'HR Admin', 'INFO', '2026-09-12T10:00:00Z')
    ]
    mock_db_session.execute.side_effect = [m_active, m_total, m_audits, m_flags, m_recent]

    response = await client_hr.get('/api/dashboard/stats')
    assert response.status_code == 200
    data = response.json()
    assert data['total_employees'] == 17
    assert data['active_employees'] == 15
    assert data['total_audit_events'] == 49
    assert data['unreviewed_flags'] == 2
    assert len(data['recent_activity']) == 1
    assert data['recent_activity'][0]['actor_name'] == 'HR Admin'

async def test_dashboard_stats_unauth(client_unauth: AsyncClient):
    response = await client_unauth.get('/api/dashboard/stats')
    assert response.status_code == 401

async def test_departments_and_roles(client_hr: AsyncClient, mock_db_session: AsyncMock):
    m_dept = MagicMock()
    m_dept.all.return_value = [(1, 'Engineering'), (2, 'HR')]
    m_roles = MagicMock()
    m_roles.all.return_value = [(1, 'Senior Dev', 1, 'Engineering', 80000, 150000)]
    
    mock_db_session.execute.side_effect = [m_dept, m_roles]

    dept_res = await client_hr.get('/api/departments')
    assert dept_res.status_code == 200
    assert len(dept_res.json()) == 2
    assert dept_res.json()[0]['name'] == 'Engineering'

    roles_res = await client_hr.get('/api/roles')
    assert roles_res.status_code == 200
    assert len(roles_res.json()) == 1
    assert roles_res.json()[0]['title'] == 'Senior Dev'

async def test_system_metrics_auditor(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    m_hit = MagicMock(); m_hit.scalar.return_value = 98.5
    m_sz = MagicMock(); m_sz.first.return_value = ('8500 kB', '250 kB')
    m_cnt = MagicMock(); m_cnt.scalar.return_value = 49
    m_chk_cnt = MagicMock(); m_chk_cnt.scalar.return_value = 2
    m_tables = MagicMock(); m_tables.all.return_value = [
        ('audit_log', 10, 25, 45, 0)
    ]
    m_pgcrypto = MagicMock(); m_pgcrypto.scalar.return_value = 1
    m_perm = MagicMock(); m_perm.scalar.return_value = True
    m_match = MagicMock(); m_match.scalar.return_value = True
    no_checkpoint = MagicMock(); no_checkpoint.first.return_value = None
    no_tail = MagicMock(); no_tail.first.return_value = (105,)

    mock_db_session.execute.side_effect = [
        m_hit, m_sz, m_cnt, m_chk_cnt, m_tables, m_pgcrypto, m_perm, m_match,
        no_checkpoint, no_tail,
    ]
    nested = MagicMock()
    nested.__aenter__ = AsyncMock(return_value=None)
    nested.__aexit__ = AsyncMock(return_value=False)
    mock_db_session.begin_nested = MagicMock(return_value=nested)

    from api.routers import audits
    verification = SimpleNamespace(verification_checks={
        'hash_chain': 'pass',
        'external_anchor': 'pass',
        'checkpoint_signatures': 'pass',
    })
    test_settings = audits.get_settings().model_copy(update={'CLERK_JWT_KEY': 'test-public-key'})
    with patch('api.routers.audits.get_settings', return_value=test_settings), \
         patch('api.routers.audits.run_verification', return_value=verification):
        response = await client_auditor.get('/api/analytics/system-metrics')
    assert response.status_code == 200
    data = response.json()
    assert data['cache_hit_rate'] == 98.5
    assert data['db_size'] == '8500 kB'
    assert data['audit_log_size'] == '250 kB'
    assert len(data['table_stats']) == 1
    assert data['security_score'] == 88
    assert data['security_checks']['pgcrypto_active'] is True
    assert data['security_checks']['role_isolation'] is True
    assert data['security_checks']['chain_continuous'] is True
    assert data['security_check_details']['auth_enforced'] == 'pass'


async def test_system_metrics_reports_unknown_checks_without_false_green(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    hit = MagicMock(); hit.scalar.return_value = 90.0
    size = MagicMock(); size.first.return_value = ('10 MB', '1 MB')
    count = MagicMock(); count.scalar.return_value = 10
    checkpoints = MagicMock(); checkpoints.scalar.return_value = 1
    tables = MagicMock(); tables.all.return_value = []
    mock_db_session.execute.side_effect = [
        hit, size, count, checkpoints, tables,
        RuntimeError('extension check unavailable'),
        RuntimeError('privilege check unavailable'),
        RuntimeError('chain check unavailable'),
    ]
    nested = MagicMock()
    nested.__aenter__ = AsyncMock(return_value=None)
    nested.__aexit__ = AsyncMock(return_value=False)
    mock_db_session.begin_nested = MagicMock(return_value=nested)

    from api.routers import audits
    verification = SimpleNamespace(verification_checks={
        'hash_chain': 'unknown',
        'external_anchor': 'unknown',
        'checkpoint_signatures': 'unknown',
    })
    test_settings = audits.get_settings().model_copy(update={'CLERK_JWT_KEY': 'test-public-key'})
    with patch('api.routers.audits.get_settings', return_value=test_settings), \
         patch('api.routers.audits.run_verification', return_value=verification):
        response = await client_auditor.get('/api/analytics/system-metrics')
    assert response.status_code == 200
    data = response.json()
    assert data['security_score'] == 12
    assert data['security_check_details']['pgcrypto_active'] == 'unknown'
    assert data['security_checks']['pgcrypto_active'] is False

async def test_system_metrics_hr_forbidden(client_hr: AsyncClient):
    response = await client_hr.get('/api/analytics/system-metrics')
    assert response.status_code == 403

async def test_concurrency_run_auditor(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    def make_worker_session():
        worker_session = AsyncMock()
        worker_session.__aenter__.return_value = worker_session
        worker_session.__aexit__.return_value = None
        result = MagicMock()
        result.one.return_value = (49, 100, True)
        worker_session.execute.return_value = result
        return worker_session

    with patch('api.routers.audits.get_session_factory', return_value=MagicMock(side_effect=make_worker_session)):
        response = await client_auditor.post('/api/analytics/diagnostics/concurrency-benchmark', json={'workers': 3})
    assert response.status_code == 200

    data = response.json()
    assert data['workers'] == 3
    assert data['success_count'] == 3
    assert len(data['logs']) == 3
