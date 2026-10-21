"""Periodic application-level integrity checks and transition alerts.

This monitor reuses Argus' existing read-only verifier. Its last-result cache
is process-local; configured webhook delivery is the durable notification path.
Provider control-plane and PostgreSQL audit logs require separate integration.
"""

import asyncio
from datetime import datetime, timezone
import logging
import time
from typing import Any

import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _result_payload(result: Any, *, duration_ms: int) -> dict[str, Any]:
    """Convert a verifier result to the minimal monitor status contract."""
    if hasattr(result, "model_dump"):
        result = result.model_dump(mode="json")
    if not isinstance(result, dict):
        raise TypeError("Verifier returned an unsupported result.")

    status = result.get("status")
    if status not in {"intact", "tampered", "unknown", "error"}:
        status = "error"
    return {
        "status": status,
        "observed_at": _utc_now().isoformat(),
        "duration_ms": max(0, int(duration_ms)),
        "entries_scanned": max(0, int(result.get("entries_scanned") or 0)),
        "last_verified_sequence_id": max(
            0, int(result.get("last_verified_sequence_id") or 0)
        ),
        "tampered_sequence_id": result.get("tampered_sequence_id"),
        "details": str(result.get("details") or "No verification details available."),
        "verification_checks": {
            str(name): (
                value if isinstance(value, str) and value in {"pass", "fail", "unknown"}
                else "unknown"
            )
            for name, value in (result.get("verification_checks") or {}).items()
        },
    }


async def _send_transition_alert(
    webhook_url: str,
    *,
    current: dict[str, Any],
    previous_status: str | None,
) -> str:
    """Send a PII-free alert when verification leaves or returns to intact."""
    if not webhook_url:
        return "not_configured"
    if current["status"] == "intact" and previous_status in (None, "intact"):
        return "not_needed"
    if current["status"] != "intact" and current["status"] == previous_status:
        return "not_needed"

    event = "integrity_restored" if current["status"] == "intact" else "integrity_attention"
    payload = {
        "source": "argus",
        "event": event,
        "status": current["status"],
        "observed_at": current["observed_at"],
        "tampered_sequence_id": current["tampered_sequence_id"],
        "verification_checks": current["verification_checks"],
        "details": current["details"][:500],
    }
    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()
        return "sent"
    except (httpx.HTTPError, ValueError) as exc:
        # Avoid logging the HTTP exception: it may contain the webhook URL.
        logger.warning("Integrity monitor alert delivery failed (%s)", type(exc).__name__)
        return "failed"


async def run_integrity_monitor(app) -> None:
    """Run verification immediately, then repeat at the configured interval."""
    settings = get_settings()
    interval = settings.INTEGRITY_MONITOR_INTERVAL_SECONDS
    previous_status: str | None = None

    while True:
        started = time.monotonic()
        try:
            # The route owns the canonical verifier path. Its HTTP dependencies
            # are unused by the verification body, so pass explicit nulls here.
            from ..routers.audits import run_verification

            result = await run_verification(current_user=None, session=None)
            current = _result_payload(
                result,
                duration_ms=round((time.monotonic() - started) * 1000),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scheduled integrity verification failed")
            current = _result_payload(
                {
                    "status": "error",
                    "details": "Scheduled integrity verification could not complete.",
                    "verification_checks": {
                        "hash_chain": "unknown",
                        "checkpoint_binding": "unknown",
                        "external_anchor": "unknown",
                        "checkpoint_signatures": "unknown",
                    },
                },
                duration_ms=round((time.monotonic() - started) * 1000),
            )

        current.update({
            "enabled": True,
            "interval_seconds": interval,
            "alert_delivery": "not_configured",
        })
        current["alert_delivery"] = await _send_transition_alert(
            settings.SECURITY_ALERT_WEBHOOK_URL,
            current=current,
            previous_status=previous_status,
        )
        app.state.integrity_monitor_status = current
        previous_status = current["status"]
        await asyncio.sleep(interval)
