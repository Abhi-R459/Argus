"""API integration tests for Counterfactual 'What-If' Provenance Replay (NOVEL-011-B & NOVEL-011-D).

Tests:
1. Role-based access control: compliance_auditor authorized, hr_admin gets 403.
2. Request validation: empty skip list returns 422, malformed timestamp returns 422.
3. Successful replay execution with mock engine response.
"""

from unittest.mock import MagicMock, patch
import pytest
from httpx import AsyncClient

from db.cli.counterfactual import BlastRadius, CounterfactualResult, SkippedEventInfo

pytestmark = pytest.mark.asyncio


def _dummy_result(employee_id=42, skip_ids=None):
    if skip_ids is None:
        skip_ids = [71]
    return CounterfactualResult(
        employee_id=employee_id,
        as_of="2026-09-25T12:00:00+00:00",
        skip_sequence_ids=skip_ids,
        actual_state={"full_name": "Alice Chen", "salary": 250000.0, "role_title": "Senior Manager"},
        counterfactual_state={"full_name": "Alice Chen", "salary": 80000.0, "role_title": "Analyst"},
        blast_radius=BlastRadius(
            salary_actual=250000.0,
            salary_counterfactual=80000.0,
            salary_overpaid_annual=170000.0,
            salary_overpaid_cumulative=680000.0,
            tenure_months=48.0,
            skipped_events_count=len(skip_ids),
            skipped_sequence_ids=skip_ids,
            first_fraud_event_timestamp="2022-09-25T12:00:00+00:00",
            as_of_timestamp="2026-09-25T12:00:00+00:00",
        ),
        skipped_events=[
            SkippedEventInfo(
                sequence_id=71,
                actor_user_id=1,
                action="INSERT",
                table_name="salary_history",
                created_at="2022-09-25T12:00:00+00:00",
                severity="CRITICAL",
                delta_summary="Salary inserted: 250000.0",
            )
        ],
        applied_events_count=12,
        simulation_duration_ms=8.5,
    )


async def test_counterfactual_hr_forbidden(client_hr: AsyncClient):
    """POST /api/audit-logs/counterfactual must be 403 Forbidden for HR admin."""
    response = await client_hr.post(
        "/api/audit-logs/counterfactual",
        json={"employee_id": 42, "skip_sequence_ids": [71]},
    )
    assert response.status_code == 403


async def test_counterfactual_empty_skip_returns_422(client_auditor: AsyncClient):
    """Passing an empty skip_sequence_ids list must return 422 Unprocessable Entity."""
    response = await client_auditor.post(
        "/api/audit-logs/counterfactual",
        json={"employee_id": 42, "skip_sequence_ids": []},
    )
    assert response.status_code == 422
    assert "skip_sequence_ids" in response.json()["detail"]


async def test_counterfactual_invalid_timestamp_returns_422(client_auditor: AsyncClient):
    """Passing an invalid ISO timestamp in as_of must return 422."""
    response = await client_auditor.post(
        "/api/audit-logs/counterfactual",
        json={"employee_id": 42, "skip_sequence_ids": [71], "as_of": "not-a-valid-date"},
    )
    assert response.status_code == 422
    assert "Invalid ISO timestamp format" in response.json()["detail"]


async def test_counterfactual_auditor_success(client_auditor: AsyncClient):
    """Compliance auditor can trigger simulation; returns typed counterfactual payload."""
    with patch("db.cli.counterfactual.counterfactual_replay", return_value=_dummy_result(42, [71])):
        with patch("psycopg2.connect"):
            response = await client_auditor.post(
                "/api/audit-logs/counterfactual",
                json={"employee_id": 42, "skip_sequence_ids": [71], "as_of": "2026-09-25T12:00:00Z"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["employee_id"] == 42
            assert data["actual_state"]["salary"] == 250000.0
            assert data["counterfactual_state"]["salary"] == 80000.0
            assert data["blast_radius"]["salary_overpaid_annual"] == 170000.0
            assert data["blast_radius"]["salary_overpaid_cumulative"] == 680000.0
            assert len(data["skipped_events"]) == 1
            assert data["skipped_events"][0]["sequence_id"] == 71


async def test_counterfactual_missing_sequence_ids_422(client_auditor: AsyncClient):
    """If engine reports missing sequence IDs, returns 422."""
    with patch(
        "db.cli.counterfactual.counterfactual_replay",
        side_effect=ValueError("Sequence IDs not found in audit log: [999]"),
    ):
        with patch("psycopg2.connect"):
            response = await client_auditor.post(
                "/api/audit-logs/counterfactual",
                json={"employee_id": 42, "skip_sequence_ids": [999]},
            )
            assert response.status_code == 422
            assert "999" in response.json()["detail"]
