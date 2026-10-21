"""Read-only incident monitoring status for Compliance Auditor users."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from ..config import get_settings
from ..dependencies import require_role

router = APIRouter(tags=["Monitoring"])
_auditor_only = [Depends(require_role(["compliance_auditor"]))]


@router.get("/monitor/status", dependencies=_auditor_only)
async def get_integrity_monitor_status(request: Request) -> dict:
    """Return the latest scheduled integrity check without implying freshness."""
    settings = get_settings()
    interval = settings.INTEGRITY_MONITOR_INTERVAL_SECONDS
    if not settings.INTEGRITY_MONITOR_ENABLED:
        return {
            "enabled": False,
            "status": "unknown",
            "last_result_status": None,
            "observed_at": None,
            "age_seconds": None,
            "stale": True,
            "interval_seconds": interval,
            "alert_delivery": "not_configured",
            "entries_scanned": 0,
            "last_verified_sequence_id": 0,
            "tampered_sequence_id": None,
            "details": "Continuous integrity monitoring is not enabled.",
            "verification_checks": {},
        }

    stored = getattr(request.app.state, "integrity_monitor_status", None)
    if not isinstance(stored, dict):
        return {
            "enabled": True,
            "status": "unknown",
            "last_result_status": None,
            "observed_at": None,
            "age_seconds": None,
            "stale": True,
            "interval_seconds": interval,
            "alert_delivery": "unknown",
            "entries_scanned": 0,
            "last_verified_sequence_id": 0,
            "tampered_sequence_id": None,
            "details": "The monitor has not completed a check in this API process.",
            "verification_checks": {},
        }

    observed_at = None
    age_seconds = None
    try:
        observed_at = datetime.fromisoformat(stored["observed_at"])
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        age_seconds = max(0, int((datetime.now(timezone.utc) - observed_at).total_seconds()))
    except (KeyError, TypeError, ValueError):
        pass

    stale = age_seconds is None or age_seconds > interval * 2
    result_status = stored.get("status", "unknown")
    status = "unknown" if stale else result_status
    details = stored.get("details", "No verification details available.")
    if stale:
        details = "The last monitor result is stale or has no valid timestamp. " + str(details)

    return {
        "enabled": True,
        "status": status,
        "last_result_status": result_status,
        "observed_at": observed_at.isoformat() if observed_at else None,
        "age_seconds": age_seconds,
        "stale": stale,
        "interval_seconds": interval,
        "alert_delivery": stored.get("alert_delivery", "unknown"),
        "duration_ms": stored.get("duration_ms", 0),
        "entries_scanned": stored.get("entries_scanned", 0),
        "last_verified_sequence_id": stored.get("last_verified_sequence_id", 0),
        "tampered_sequence_id": stored.get("tampered_sequence_id"),
        "details": details,
        "verification_checks": stored.get("verification_checks", {}),
    }
