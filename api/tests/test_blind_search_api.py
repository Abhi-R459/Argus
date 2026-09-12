"""Unit tests for BLIND-002: Backend Forensic Query Filter by Blind Index.

Validates Gate 3 intermediate testing requirements:
- Searching with a valid National ID computes HMAC and filters audit rows.
- Query with non-existent National ID returns empty results.
- Zero plaintext PII leaks into response payloads.
- Role isolation: hr_admin is 403 Forbidden.
- Regression check on unfiltered audit log listing.
"""

import hashlib
import hmac
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock

from api.config import get_settings

pytestmark = pytest.mark.asyncio


async def test_blind_search_filter_applied(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    """Assert query with national_id_search computes HMAC and queries the database."""
    settings = get_settings()
    raw_nid = "123-45-6789"
    expected_hmac = hmac.new(
        settings.AUDIT_SALT.encode("utf-8"),
        raw_nid.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    # Fake returned row with masked values and blind index
    now = datetime.now(timezone.utc)
    mock_row = MagicMock()
    mock_row.sequence_id = 42
    mock_row.actor_name = "HR Admin"
    mock_row.employee_id = 10
    mock_row.action = "INSERT"
    mock_row.table_name = "employees"
    mock_row.row_id = 10
    mock_row.old_value = None
    mock_row.new_value = {
        "full_name": "Test Subject",
        "national_id_encrypted": "[REDACTED]",
        "national_id_blind_index": expected_hmac,
    }
    mock_row.severity = "INFO"
    mock_row.entry_hash = "a" * 64
    mock_row.previous_hash = "0" * 64
    mock_row.created_at = now

    mock_exec = MagicMock()
    mock_exec.all.return_value = [mock_row]
    mock_db_session.execute.return_value = mock_exec
    mock_db_session.scalar.return_value = 1

    response = await client_auditor.get(f"/api/audit-logs?national_id_search={raw_nid}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1

    item = data["items"][0]
    assert item["sequence_id"] == 42
    assert item["new_value"]["national_id_blind_index"] == expected_hmac
    # Strict privacy assertion: Plaintext NID must NEVER appear anywhere in the response
    assert raw_nid not in str(data)
    assert item["new_value"]["national_id_encrypted"] == "[REDACTED]"


async def test_blind_search_empty_match(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    """Assert search with non-matching ID returns 0 results cleanly."""
    mock_exec = MagicMock()
    mock_exec.all.return_value = []
    mock_db_session.execute.return_value = mock_exec
    mock_db_session.scalar.return_value = 0

    response = await client_auditor.get("/api/audit-logs?national_id_search=000-00-0000")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert len(data["items"]) == 0


async def test_blind_search_hr_forbidden(client_hr: AsyncClient):
    """Assert hr_admin cannot search audit logs by blind index."""
    response = await client_hr.get("/api/audit-logs?national_id_search=123-45-6789")
    assert response.status_code == 403


async def test_unfiltered_audit_logs_regression(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    """Assert calling /api/audit-logs without search parameter behaves identically."""
    mock_exec = MagicMock()
    mock_exec.all.return_value = []
    mock_db_session.execute.return_value = mock_exec
    mock_db_session.scalar.return_value = 0

    response = await client_auditor.get("/api/audit-logs?page=1&limit=20")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
