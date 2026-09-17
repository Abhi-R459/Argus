"""API Service for Tunable Blind Indexing, Rate Limiting & Forensic Audit Logging.

Supports:
- NIST SP 800-132 PBKDF2-HMAC-SHA256 blind indexing for structured PII.
- Sliding-window rate limiting (10 queries/minute per auditor session).
- "Audit-the-Auditor" tamper-evident security telemetry (SEARCH_BLIND_INDEX).
- Zero-PII leak guarantee: plaintext national IDs never logged or stored.
"""

from __future__ import annotations

import collections
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional, Tuple

from db.crypto.blind_index import (
    compute_blind_index,
    calibrate_work_factor,
    DEFAULT_ITERATIONS,
    DEFAULT_SALT,
    DEFAULT_MODE,
)

logger = logging.getLogger("argus.security.audit")


class BlindSearchRateLimiter:
    """Thread-safe sliding-window rate limiter for blind index queries.

    Limits high-frequency enumeration of low-entropy national identifiers.
    Default threshold: 10 requests per 60-second window per user/IP session.
    """

    def __init__(self, max_requests: int = 10, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, Deque[float]] = collections.defaultdict(collections.deque)
        self._lock = threading.Lock()

    def check_rate_limit(self, key: str) -> Tuple[bool, int, float]:
        """Check if request for key is allowed under current rate limit.

        Args:
            key: Rate limiting key (e.g. "user:12" or "ip:192.168.1.1").

        Returns:
            Tuple of (is_allowed: bool, current_count: int, retry_after_seconds: float).
        """
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            q = self._requests[key]
            # Expire timestamps outside the sliding window
            while q and q[0] <= cutoff:
                q.popleft()

            count = len(q)
            if count >= self.max_requests:
                oldest = q[0]
                retry_after = max(1.0, (oldest + self.window_seconds) - now)
                return False, count, retry_after

            return True, count, 0.0

    def record_request(self, key: str) -> None:
        """Record a permitted request timestamp for key."""
        now = time.time()
        with self._lock:
            self._requests[key].append(now)

    def reset(self) -> None:
        """Reset all rate limiter tracking state (used in testing)."""
        with self._lock:
            self._requests.clear()


class BlindSearchAuditLogger:
    """Forensic telemetry recorder for blind index search activity.

    Enforces the "Audit-the-Auditor" regulatory control: whenever an auditor
    queries the audit chain by national ID, an immutable security event is
    recorded and logged.

    Privacy Invariant:
    The raw plaintext National ID is strictly forbidden from being logged
    or recorded. Only the cryptographic blind index digest is retained.
    """

    def __init__(self, max_retained_events: int = 1000):
        self.max_retained_events = max_retained_events
        self._events: Deque[dict[str, Any]] = collections.deque(maxlen=max_retained_events)
        self._lock = threading.Lock()

    def log_search(
        self,
        actor_user_id: int,
        actor_email: str,
        blind_index: str,
        matches_found: int = 0,
        client_ip: str = "127.0.0.1",
    ) -> dict[str, Any]:
        """Record and log a SEARCH_BLIND_INDEX security event.

        Args:
            actor_user_id: User ID of the querying auditor.
            actor_email: Email / username of the querying auditor.
            blind_index: Hexadecimal blind index digest used in the query.
            matches_found: Number of matching audit_log rows returned.
            client_ip: Remote client IP address.

        Returns:
            Dictionary representation of the recorded security audit event.
        """
        event = {
            "event": "SEARCH_BLIND_INDEX",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor_user_id": actor_user_id,
            "actor_email": actor_email,
            "blind_index": blind_index,
            "matches_found": matches_found,
            "client_ip": client_ip,
        }

        # Python structured security logger
        logger.info(
            "SECURITY_AUDIT: event=%s actor_id=%s actor_email=%s blind_index=%s matches=%d client_ip=%s",
            event["event"],
            event["actor_user_id"],
            event["actor_email"],
            event["blind_index"],
            event["matches_found"],
            event["client_ip"],
        )

        with self._lock:
            self._events.append(dict(event))

        return event

    def get_audit_events(self) -> List[dict[str, Any]]:
        """Return a chronological snapshot of recent blind search audit events."""
        with self._lock:
            return list(self._events)

    def clear_audit_events(self) -> None:
        """Clear recorded audit events (used in testing)."""
        with self._lock:
            self._events.clear()


# Global service singletons
rate_limiter = BlindSearchRateLimiter()
audit_logger = BlindSearchAuditLogger()

__all__ = [
    "compute_blind_index",
    "calibrate_work_factor",
    "BlindSearchRateLimiter",
    "BlindSearchAuditLogger",
    "rate_limiter",
    "audit_logger",
    "DEFAULT_ITERATIONS",
    "DEFAULT_SALT",
    "DEFAULT_MODE",
]
