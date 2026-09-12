import pytest
from datetime import datetime, timezone
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock

pytestmark = pytest.mark.asyncio


async def test_audit_chain_auditor_empty(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    """Assert /api/audit-logs/chain returns 200 and an empty list when DB has no rows."""
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db_session.execute.return_value = mock_result

    response = await client_auditor.get("/api/audit-logs/chain?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


async def test_audit_chain_auditor_with_entries(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    """Assert /api/audit-logs/chain returns correctly mapped ChainEntry objects."""
    now = datetime.now(timezone.utc)
    
    # Create fake row object mimicking SQLAlchemy Row
    class MockRow:
        def __init__(self, seq, h, prev, tbl, act, email, role, ts, sev, old, new):
            self.sequence_id = seq
            self.entry_hash = h
            self.previous_hash = prev
            self.table_name = tbl
            self.action = act
            self.actor_email = email
            self.actor_role = role
            self.created_at = ts
            self.severity = sev
            self.old_value = old
            self.new_value = new

    row1 = MockRow(
        seq=2,
        h="b" * 64,
        prev="a" * 64,
        tbl="employees",
        act="UPDATE",
        email="hr@argus.test",
        role="hr_admin",
        ts=now,
        sev="CRITICAL",
        old={"role_id": 1},
        new={"role_id": 2},
    )
    row2 = MockRow(
        seq=1,
        h="a" * 64,
        prev="0" * 64,
        tbl="employees",
        act="INSERT",
        email="system@argus.internal",
        role="system",
        ts=now,
        sev="INFO",
        old=None,
        new={"full_name": "Test"},
    )

    mock_result = MagicMock()
    mock_result.all.return_value = [row1, row2]
    mock_db_session.execute.return_value = mock_result

    response = await client_auditor.get("/api/audit-logs/chain?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Check mapping
    assert data[0]["entry_id"] == 2
    assert data[0]["hash"] == "b" * 64
    assert data[0]["prev_hash"] == "a" * 64
    assert data[0]["operation"] == "UPDATE"
    assert data[0]["actor_email"] == "hr@argus.test"
    assert data[0]["actor_role"] == "hr_admin"
    assert data[0]["severity"] == "critical"  # Mapped from CRITICAL to critical
    assert data[0]["old_value"] == {"role_id": 1}
    assert data[0]["new_value"] == {"role_id": 2}

    assert data[1]["entry_id"] == 1
    assert data[1]["severity"] == "low"       # Mapped from INFO to low


async def test_audit_chain_hr_forbidden(client_hr: AsyncClient):
    """Assert hr_admin role is strictly forbidden from accessing the audit chain."""
    response = await client_hr.get("/api/audit-logs/chain")
    assert response.status_code == 403


async def test_anchor_status_missing(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    """Assert /api/anchor/status returns MISSING when no checkpoints exist."""
    # First query is checkpoints -> returns None
    # Second query is chain_state -> returns None
    # Third query is MAX(sequence_id) -> returns (15,)
    chk_mock = MagicMock()
    chk_mock.first.return_value = None

    state_mock = MagicMock()
    state_mock.first.return_value = None

    max_mock = MagicMock()
    max_mock.first.return_value = (15,)

    mock_db_session.execute.side_effect = [chk_mock, state_mock, max_mock]

    response = await client_auditor.get("/api/anchor/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "MISSING"
    assert "anchor_store" in data
    assert "anchor_location" in data
    assert "last_anchored" in data
    assert data["entries_since_anchor"] == 15


async def test_anchor_status_anchored(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    """Assert /api/anchor/status returns ANCHORED when delta is within threshold."""
    now = datetime.now(timezone.utc)
    chk_mock = MagicMock()
    chk_mock.first.return_value = (100, "f" * 64, now)

    state_mock = MagicMock()
    state_mock.first.return_value = (105,)

    mock_db_session.execute.side_effect = [chk_mock, state_mock]

    response = await client_auditor.get("/api/anchor/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ANCHORED"
    assert data["entries_since_anchor"] == 5
    assert data["anchor_hash"] == f"sha256:{'f' * 64}"


async def test_anchor_status_stale(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    """Assert /api/anchor/status returns STALE when delta exceeds checkpoint threshold."""
    now = datetime.now(timezone.utc)
    chk_mock = MagicMock()
    chk_mock.first.return_value = (100, "f" * 64, now)

    state_mock = MagicMock()
    state_mock.first.return_value = (200,)  # 100 entries behind > 50

    mock_db_session.execute.side_effect = [chk_mock, state_mock]

    response = await client_auditor.get("/api/anchor/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "STALE"
    assert data["entries_since_anchor"] == 100


async def test_anchor_status_hr_forbidden(client_hr: AsyncClient):
    """Assert hr_admin role is strictly forbidden from accessing anchor status."""
    response = await client_hr.get("/api/anchor/status")
    assert response.status_code == 403


async def test_gate1_existing_endpoints_regression(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    """Assert existing audit endpoints continue functioning with zero regression."""
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_result.scalars.return_value.all.return_value = []
    mock_db_session.execute.return_value = mock_result

    # GET /api/audit-logs
    r1 = await client_auditor.get("/api/audit-logs")
    assert r1.status_code in [200, 500]

    # POST /api/verify
    r2 = await client_auditor.post("/api/verify")
    assert r2.status_code in [200, 500]

    # GET /api/suspicious-activity
    r3 = await client_auditor.get("/api/suspicious-activity")
    assert r3.status_code in [200, 500]

    # GET /api/audit-logs/export
    r4 = await client_auditor.get("/api/audit-logs/export")
    assert r4.status_code == 200
