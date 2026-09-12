"""Tests for Dedicated Chain Explorer API (PORTAL-002).

Validates:
- GET /api/audit-logs/chain with limit and offset pagination.
- GET /api/audit-logs/chain with around_seq windowing.
- GET /api/audit-logs/chain with table_name and action filters.
- Total count header X-Total-Count.
- Role-based access control (403 Forbidden for hr_admin).
"""

import pytest
from datetime import datetime, timezone
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock

pytestmark = pytest.mark.asyncio


class MockRow:
    """Mock database row for audit_log entries."""
    def __init__(self, seq, h, prev, tbl, act, email="auditor@argus.test", role="compliance_auditor"):
        self.sequence_id = seq
        self.entry_hash = h
        self.previous_hash = prev
        self.table_name = tbl
        self.action = act
        self.actor_email = email
        self.actor_role = role
        self.created_at = datetime.now(timezone.utc)
        self.severity = "INFO"
        self.old_value = None
        self.new_value = {"id": seq, "val": "test"}


async def test_chain_explorer_pagination(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    """Test offset and limit pagination on /api/audit-logs/chain with X-Total-Count header."""
    mock_count_res = MagicMock()
    mock_count_res.scalar.return_value = 50

    mock_rows_res = MagicMock()
    mock_rows_res.all.return_value = [
        MockRow(seq=30, h="3"*64, prev="2"*64, tbl="employees", act="UPDATE"),
        MockRow(seq=29, h="2"*64, prev="1"*64, tbl="salary_history", act="INSERT"),
    ]

    # Session.execute will be called twice: once for count, once for rows
    mock_db_session.execute.side_effect = [mock_count_res, mock_rows_res]

    response = await client_auditor.get("/api/audit-logs/chain?offset=10&limit=20")
    assert response.status_code == 200
    assert response.headers.get("X-Total-Count") == "50"
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["entry_id"] == 30
    assert data[1]["entry_id"] == 29


async def test_chain_explorer_around_seq_windowing(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    """Test around_seq parameter centers the window around target sequence ID."""
    mock_count_res = MagicMock()
    mock_count_res.scalar.return_value = 100

    mock_rows_res = MagicMock()
    # Centered on seq 29 with limit 10 (range 24..33)
    mock_rows_res.all.return_value = [
        MockRow(seq=31, h="b"*64, prev="a"*64, tbl="employees", act="UPDATE"),
        MockRow(seq=30, h="a"*64, prev="9"*64, tbl="employees", act="UPDATE"),
        MockRow(seq=29, h="9"*64, prev="8"*64, tbl="salary_history", act="UPDATE"),
    ]

    mock_db_session.execute.side_effect = [mock_count_res, mock_rows_res]

    response = await client_auditor.get("/api/audit-logs/chain?around_seq=29&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[2]["entry_id"] == 29


async def test_chain_explorer_filters(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    """Test filtering by table_name and action."""
    mock_count_res = MagicMock()
    mock_count_res.scalar.return_value = 5

    mock_rows_res = MagicMock()
    mock_rows_res.all.return_value = [
        MockRow(seq=15, h="c"*64, prev="b"*64, tbl="salary_history", act="INSERT"),
    ]

    mock_db_session.execute.side_effect = [mock_count_res, mock_rows_res]

    response = await client_auditor.get("/api/audit-logs/chain?table_name=salary_history&action=INSERT")
    assert response.status_code == 200
    assert response.headers.get("X-Total-Count") == "5"
    data = response.json()
    assert len(data) == 1
    assert data[0]["table_name"] == "salary_history"
    assert data[0]["operation"] == "INSERT"


async def test_chain_explorer_role_isolation(client_hr: AsyncClient):
    """Assert non-auditors (hr_admin) are rejected with 403 Forbidden."""
    response = await client_hr.get("/api/audit-logs/chain")
    assert response.status_code == 403


async def test_audit_logs_employee_and_sequence_filters(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    """Test employee_id and sequence_id filtering on GET /api/audit-logs."""
    mock_db_session.scalar.return_value = 1
    
    mock_row = MagicMock()
    mock_row.sequence_id = 42
    mock_row.actor_name = "Jane Auditor"
    mock_row.employee_id = 7
    mock_row.action = "UPDATE"
    mock_row.table_name = "employees"
    mock_row.row_id = 7
    mock_row.old_value = {"role_id": 1}
    mock_row.new_value = {"role_id": 2}
    mock_row.severity = "INFO"
    mock_row.entry_hash = "a" * 64
    mock_row.previous_hash = "0" * 64
    mock_row.created_at = datetime.now(timezone.utc)

    mock_res = MagicMock()
    mock_res.all.return_value = [mock_row]
    mock_db_session.execute.return_value = mock_res

    # Test sequence_id filter
    resp_seq = await client_auditor.get("/api/audit-logs?sequence_id=42")
    assert resp_seq.status_code == 200
    data_seq = resp_seq.json()
    assert data_seq["total"] == 1
    assert data_seq["items"][0]["sequence_id"] == 42

    # Test employee_id filter
    resp_emp = await client_auditor.get("/api/audit-logs?employee_id=7")
    assert resp_emp.status_code == 200
    data_emp = resp_emp.json()
    assert data_emp["total"] == 1
    assert data_emp["items"][0]["employee_id"] == 7

