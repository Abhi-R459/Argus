"""Unit tests for HARDEN-009: Tunable PBKDF2 Blind Indexing, Rate Limiting & Security Logging.

Validates:
- PBKDF2-HMAC-SHA256 blind index calculation (NIST SP 800-132) and filtering.
- Strict rate limiting: 10 requests/minute per auditor session; 11th raises HTTP 429 with Retry-After.
- "Audit-the-Auditor" forensic telemetry: SEARCH_BLIND_INDEX event emission and security log inspection.
- Strict privacy: Plaintext National ID NEVER appears in responses, logs, or telemetry records.
- Role isolation: hr_admin receives 403 Forbidden.
- Regression safety on unfiltered audit log listing.
- Work-factor calibration benchmark helper verification.
"""

import hashlib
import hmac
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock

from api.config import get_settings
from api.services.blind_index import (
    compute_blind_index,
    calibrate_work_factor,
    rate_limiter,
    audit_logger,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def reset_service_state(monkeypatch):
    """Reset rate limiter and audit logger before each test."""
    monkeypatch.setenv("AUDIT_SALT", "test-blind-index-salt-is-at-least-32-bytes")
    get_settings.cache_clear()
    rate_limiter.reset()
    audit_logger.clear_audit_events()
    yield
    get_settings.cache_clear()
    rate_limiter.reset()
    audit_logger.clear_audit_events()


async def test_blind_search_filter_applied(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    """Assert query with national_id_search computes PBKDF2 blind index and queries DB."""
    settings = get_settings()
    raw_nid = "123-45-6789"
    expected_digest = compute_blind_index(
        raw_nid,
        salt=settings.AUDIT_SALT,
        iterations=settings.BLIND_INDEX_ITERATIONS,
        mode=settings.BLIND_INDEX_MODE,
    )

    # Fake returned row with masked values and blind index
    now = datetime.now(timezone.utc)
    mock_row = MagicMock()
    mock_row.sequence_id = 42
    mock_row.actor_name = "Compliance Auditor"
    mock_row.employee_id = 10
    mock_row.action = "INSERT"
    mock_row.table_name = "employees"
    mock_row.row_id = 10
    mock_row.old_value = None
    mock_row.new_value = {
        "full_name": "Test Subject",
        "national_id_encrypted": "[REDACTED]",
        "national_id_blind_index": expected_digest,
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
    assert item["new_value"]["national_id_blind_index"] == expected_digest
    # Strict privacy assertion: Plaintext NID must NEVER appear anywhere in the response
    assert raw_nid not in str(data)
    assert item["new_value"]["national_id_encrypted"] == "[REDACTED]"


async def test_blind_search_rate_limiting(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    """Assert rate limiter caps searches at 10 requests/min and raises HTTP 429 on the 11th."""
    mock_exec = MagicMock()
    mock_exec.all.return_value = []
    mock_db_session.execute.return_value = mock_exec
    mock_db_session.scalar.return_value = 0

    # Execute exactly 10 requests - all must succeed with 200 OK
    for i in range(10):
        resp = await client_auditor.get(f"/api/audit-logs?national_id_search=111-22-{i:04d}")
        assert resp.status_code == 200, f"Request {i+1} should succeed under rate limit"

    # 11th request must be rejected with HTTP 429 Too Many Requests
    resp_blocked = await client_auditor.get("/api/audit-logs?national_id_search=111-22-9999")
    assert resp_blocked.status_code == 429
    assert "Rate limit exceeded" in resp_blocked.json()["detail"]
    assert "Retry-After" in resp_blocked.headers

    # Resetting the limiter immediately restores access
    rate_limiter.reset()
    resp_restored = await client_auditor.get("/api/audit-logs?national_id_search=111-22-9999")
    assert resp_restored.status_code == 200


async def test_audit_the_auditor_security_telemetry(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    """Assert SEARCH_BLIND_INDEX security audit events are captured without plaintext PII."""
    mock_exec = MagicMock()
    mock_exec.all.return_value = []
    mock_db_session.execute.return_value = mock_exec
    mock_db_session.scalar.return_value = 0

    search_id = "555-66-7777"
    response = await client_auditor.get(f"/api/audit-logs?national_id_search={search_id}")
    assert response.status_code == 200

    # Fetch security telemetry events endpoint
    events_res = await client_auditor.get("/api/audit-logs/security-events")
    assert events_res.status_code == 200
    payload = events_res.json()
    assert payload["total"] >= 1
    event = payload["events"][-1]

    assert event["event"] == "SEARCH_BLIND_INDEX"
    assert "actor_user_id" in event
    assert "blind_index" in event
    assert len(event["blind_index"]) == 64
    persisted_event = mock_db_session.add.call_args.args[0]
    assert persisted_event.event_type == "SEARCH_BLIND_INDEX"
    assert persisted_event.blind_index == event["blind_index"]
    assert search_id not in str(persisted_event.__dict__)

    # Critical Privacy Invariant: Raw plaintext national ID must NEVER leak into audit telemetry
    assert search_id not in str(payload)


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


async def test_blind_search_fails_closed_without_unique_audit_salt(
    client_auditor: AsyncClient,
):
    from types import SimpleNamespace
    from unittest.mock import patch

    with patch("api.routers.audits.get_settings", return_value=SimpleNamespace(AUDIT_SALT="short")):
        response = await client_auditor.get("/api/audit-logs?national_id_search=123-45-6789")

    assert response.status_code == 503


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


async def test_audit_log_cursor_pages_do_not_overlap(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    from types import SimpleNamespace

    def row(sequence_id: int):
        return SimpleNamespace(
            sequence_id=sequence_id,
            actor_user_id=2,
            actor_name="Auditor",
            employee_id=7,
            action="UPDATE",
            table_name="employees",
            row_id=7,
            old_value=None,
            new_value={},
            severity="INFO",
            entry_hash=f"{sequence_id:064x}",
            previous_hash=f"{sequence_id - 1:064x}",
            created_at=datetime.now(timezone.utc),
        )

    mock_db_session.scalar.return_value = 4
    result = MagicMock()
    result.all.return_value = [row(5), row(4), row(3)]
    mock_db_session.execute.return_value = result
    first = await client_auditor.get("/api/audit-logs?page=1&limit=2")
    assert first.status_code == 200
    first_page = first.json()
    assert [item["sequence_id"] for item in first_page["items"]] == [5, 4]
    assert all(item["actor_user_id"] == 2 for item in first_page["items"])
    assert first_page["next_cursor"] == 4
    assert first_page["has_more"] is True

    result.all.return_value = [row(3), row(2)]
    second = await client_auditor.get("/api/audit-logs?page=2&limit=2&before_sequence_id=4")
    assert second.status_code == 200
    second_page = second.json()
    assert [item["sequence_id"] for item in second_page["items"]] == [3, 2]
    assert set(item["sequence_id"] for item in first_page["items"]).isdisjoint(
        item["sequence_id"] for item in second_page["items"]
    )
    assert second_page["has_more"] is False


async def test_work_factor_calibration_benchmark():
    """Assert calibration helper generates valid SLA and GPU estimation metrics."""
    metrics = calibrate_work_factor(iterations_list=[1, 100, 1000], num_samples=2)
    assert len(metrics) == 3

    # Check 1 iteration (HMAC mode)
    assert metrics[0]["iterations"] == 1
    assert metrics[0]["sla_compliant"] is True
    assert metrics[0]["gpu_search_seconds"] < 1.0  # < 1 second on RTX 4090

    # Check 1,000 iterations (PBKDF2 default)
    assert metrics[2]["iterations"] == 1000
    assert metrics[2]["sla_compliant"] is True
    assert metrics[2]["gpu_search_seconds"] > 600.0  # > 10 minutes on RTX 4090
    assert metrics[2]["nist_approved"] is True


async def test_compute_blind_index_modes_and_validation():
    """Assert input validation and hashing modes for compute_blind_index."""
    salt = "test_salt_123"
    val = "123-45-6789"

    # PBKDF2 mode
    digest_pbkdf2 = compute_blind_index(val, salt=salt, iterations=1000, mode="pbkdf2")
    assert len(digest_pbkdf2) == 64
    expected_pbkdf2 = hashlib.pbkdf2_hmac("sha256", val.encode("utf-8"), salt.encode("utf-8"), 1000, 32).hex()
    assert digest_pbkdf2 == expected_pbkdf2

    # HMAC mode
    digest_hmac = compute_blind_index(val, salt=salt, mode="hmac")
    assert len(digest_hmac) == 64
    expected_hmac = hmac.new(salt.encode("utf-8"), val.encode("utf-8"), hashlib.sha256).hexdigest()
    assert digest_hmac == expected_hmac

    # Empty validation
    with pytest.raises(ValueError):
        compute_blind_index("")
    with pytest.raises(ValueError):
        compute_blind_index("   ")
