from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest


def _settings(monkeypatch, *, enabled=True, interval=300):
    from api.routers import monitoring

    monkeypatch.setattr(
        monitoring,
        "get_settings",
        lambda: SimpleNamespace(
            INTEGRITY_MONITOR_ENABLED=enabled,
            INTEGRITY_MONITOR_INTERVAL_SECONDS=interval,
        ),
    )


@pytest.mark.asyncio
async def test_monitor_status_is_unknown_before_first_completed_check(monkeypatch):
    from api.routers.monitoring import get_integrity_monitor_status

    _settings(monkeypatch)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))

    status = await get_integrity_monitor_status(request)

    assert status["enabled"] is True
    assert status["status"] == "unknown"
    assert status["stale"] is True
    assert status["observed_at"] is None


@pytest.mark.asyncio
async def test_stale_passing_result_is_reported_as_unknown(monkeypatch):
    from api.routers.monitoring import get_integrity_monitor_status

    _settings(monkeypatch, interval=60)
    observed_at = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        integrity_monitor_status={
            "status": "intact",
            "observed_at": observed_at,
            "entries_scanned": 12,
            "last_verified_sequence_id": 12,
            "verification_checks": {"hash_chain": "pass"},
        }
    )))

    status = await get_integrity_monitor_status(request)

    assert status["status"] == "unknown"
    assert status["last_result_status"] == "intact"
    assert status["stale"] is True
    assert "stale" in status["details"].lower()


@pytest.mark.asyncio
async def test_fresh_detection_exposes_sequence_and_check_results(monkeypatch):
    from api.routers.monitoring import get_integrity_monitor_status

    _settings(monkeypatch)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        integrity_monitor_status={
            "status": "tampered",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "entries_scanned": 40,
            "last_verified_sequence_id": 17,
            "tampered_sequence_id": 18,
            "details": "Hash mismatch at sequence 18.",
            "verification_checks": {"hash_chain": "fail", "external_anchor": "pass"},
            "alert_delivery": "sent",
        }
    )))

    status = await get_integrity_monitor_status(request)

    assert status["status"] == "tampered"
    assert status["stale"] is False
    assert status["tampered_sequence_id"] == 18
    assert status["verification_checks"]["hash_chain"] == "fail"
    assert status["alert_delivery"] == "sent"


@pytest.mark.asyncio
async def test_disabled_monitor_does_not_claim_integrity(monkeypatch):
    from api.routers.monitoring import get_integrity_monitor_status

    _settings(monkeypatch, enabled=False)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))

    status = await get_integrity_monitor_status(request)

    assert status["enabled"] is False
    assert status["status"] == "unknown"
    assert status["stale"] is True


@pytest.mark.asyncio
async def test_monitor_status_allows_auditor(client_auditor):
    auditor_response = await client_auditor.get("/api/monitor/status")

    assert auditor_response.status_code == 200


@pytest.mark.asyncio
async def test_monitor_status_denies_hr(client_hr):
    hr_response = await client_hr.get("/api/monitor/status")

    assert hr_response.status_code == 403


def test_monitor_result_normalizes_unexpected_checks():
    from api.services.integrity_monitor import _result_payload

    result = _result_payload(
        {
            "status": "intact",
            "verification_checks": {"hash_chain": "pass", "unexpected": {"secret": "value"}},
        },
        duration_ms=10,
    )

    assert result["verification_checks"] == {
        "hash_chain": "pass",
        "unexpected": "unknown",
    }


@pytest.mark.asyncio
async def test_alert_without_configuration_is_reported_clearly():
    from api.services.integrity_monitor import _send_transition_alert

    result = await _send_transition_alert(
        "",
        current={"status": "tampered", "observed_at": "now"},
        previous_status=None,
    )

    assert result == "not_configured"


@pytest.mark.asyncio
async def test_monitor_runs_verifier_and_publishes_latest_status(monkeypatch):
    import asyncio
    from api.services import integrity_monitor

    class StopAfterOneRun(Exception):
        pass

    monkeypatch.setattr(
        integrity_monitor,
        "get_settings",
        lambda: SimpleNamespace(
            INTEGRITY_MONITOR_INTERVAL_SECONDS=300,
            SECURITY_ALERT_WEBHOOK_URL="",
        ),
    )

    async def verify_once(*, current_user, session):
        assert current_user is None
        assert session is None
        return {
            "status": "tampered",
            "entries_scanned": 9,
            "last_verified_sequence_id": 4,
            "tampered_sequence_id": 5,
            "details": "Hash mismatch at sequence 5.",
            "verification_checks": {"hash_chain": "fail"},
        }

    async def fake_sleep(_interval):
        raise StopAfterOneRun

    monkeypatch.setattr("api.routers.audits.run_verification", verify_once)
    monkeypatch.setattr(integrity_monitor.asyncio, "sleep", fake_sleep)
    app = SimpleNamespace(state=SimpleNamespace())

    with pytest.raises(StopAfterOneRun):
        await integrity_monitor.run_integrity_monitor(app)

    assert app.state.integrity_monitor_status["status"] == "tampered"
    assert app.state.integrity_monitor_status["tampered_sequence_id"] == 5
    assert app.state.integrity_monitor_status["alert_delivery"] == "not_configured"
