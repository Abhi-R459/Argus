"""Audit Log and Verification endpoints.

Implements:
- GET  /api/audit-logs              — Paginated audit log (compliance_auditor only)
- POST /api/verify                  — Invoke chain verifier (compliance_auditor only)
- GET  /api/suspicious-activity     — List flags (compliance_auditor only)
- POST /api/suspicious-activity/{id}/review — Mark flag reviewed (compliance_auditor only)

GET /api/audit-logs queries the real audit_log table joined with users.
The table will be empty until Abhinav's Week 3 triggers land — that is expected.

POST /api/verify invokes the standalone verification engine to walk and verify the chain.
"""

from datetime import date, datetime, timezone
from typing import Optional, List
import asyncio
import hashlib
import hmac
import json
import logging
import math
from pathlib import Path
from urllib.parse import quote, unquote

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func, text, or_, and_, desc, case
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..dependencies import get_current_user, require_role, get_db_session
from ..database import get_session_factory
from db.crypto.pii import validate_audit_salt
from ..services.blind_index import (
    compute_blind_index,
    rate_limiter,
    audit_logger,
)
from ..services.request_budget import consume_request_budget
from ..models.audit_log import AuditLog
from ..models.department import Department
from ..models.employee import Employee
from ..models.role import Role
from ..models.suspicious_activity_flag import SuspiciousActivityFlag
from ..models.user import User
from ..models.security_audit_event import SecurityAuditEvent
from ..models.suspicious_activity_review import SuspiciousActivityReview
from ..schemas.audit import (
    AuditLogSearchRequest,
    AuditLogItem,
    VerificationResult,
    SuspiciousFlagItem,
    SuspiciousReviewResponse,
    SuspiciousReviewRequest,
    SuspiciousReviewHistoryItem,
    TimeTravelResponse,
    ChainEntry,
    AnchorInfo,
    CounterfactualRequest,
    CounterfactualResponse,
    MerkleProofResponse,
    WitnessItem,
    WitnessReport,
)
from ..schemas.common import PaginatedResponse
from ..schemas.analytics import (
    SystemMetricsResponse,
    TableStatItem,
    ConcurrencyRunRequest,
    ConcurrencyRunResponse,
    ConcurrencyLogItem,
)

router = APIRouter(tags=["Audits"])
logger = logging.getLogger(__name__)


def _load_local_attack_snapshot() -> Optional[dict]:
    """Return the local development attack snapshot for auditor forensics."""
    if get_settings().APP_ENV != "development":
        return None
    snapshot_path = Path(__file__).resolve().parents[2] / ".argus_snapshot.json"
    try:
        return json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _snapshot_payload_value(value: object) -> Optional[dict]:
    """Decode a JSON payload from the adversary's before-attack snapshot."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
            return decoded if isinstance(decoded, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _forensic_before_payloads() -> dict[int, dict]:
    """Map the attacked sequence to its pre-attack payload in dev simulations."""
    snapshot = _load_local_attack_snapshot()
    if not snapshot or snapshot.get("scenario") not in {"dba-row-tamper", "recompute-and-hide"}:
        return {}
    try:
        target_sequence = int(snapshot["target_sequence_id"])
    except (KeyError, TypeError, ValueError):
        return {}
    for row in snapshot.get("audit_rows", []):
        if row.get("sequence_id") == target_sequence:
            original = _snapshot_payload_value(
                row.get("new_value_text", row.get("new_value"))
            )
            if original is None:
                return {}

            # The source-table snapshot is the authoritative value immediately
            # before the simulated DBA write. Reconcile the changed business
            # column into the audit-payload baseline so an older ledger value
            # cannot be mistaken for the live pre-attack value.
            for business_row in snapshot.get("business_rows", []):
                if (
                    business_row.get("table_name") == row.get("table_name")
                    and business_row.get("row_id") == row.get("row_id")
                    and business_row.get("column")
                ):
                    original[business_row["column"]] = business_row.get("value")
            return {target_sequence: original}
    return {}


def _deleted_entry_snapshot(sequence_id: int) -> Optional[dict]:
    """Return recovery-snapshot details for a row missing from a broken chain."""
    snapshot = _load_local_attack_snapshot()
    if not snapshot or snapshot.get("scenario") != "delete-audit-row":
        return None
    for row in snapshot.get("audit_rows", []):
        if row.get("sequence_id") != sequence_id:
            continue
        return {
            "sequence_id": int(sequence_id),
            "actor_user_id": row.get("actor_user_id"),
            "employee_id": row.get("employee_id"),
            "action": row.get("action"),
            "table_name": row.get("table_name"),
            "row_id": row.get("row_id"),
            "old_value": _snapshot_payload_value(
                row.get("old_value_text", row.get("old_value"))
            ),
            "new_value": _snapshot_payload_value(
                row.get("new_value_text", row.get("new_value"))
            ),
            "severity": row.get("severity"),
            "entry_hash": row.get("entry_hash"),
            "previous_hash": row.get("previous_hash"),
            "created_at": row.get("created_at_text", row.get("created_at")),
            "evidence_source": "recovery_snapshot",
        }
    return None


def _checkpoint_public_key_path(key_id: Optional[str], directory: Path) -> Path:
    """Resolve a trusted checkpoint public key without consulting signer secrets."""
    filename = (
        "public_key.pem"
        if not key_id or key_id == "local:ed25519:v1"
        else f"{quote(str(key_id), safe='')}.pem"
    )
    return directory / filename


def _compliance_sync_db_url() -> str:
    """Return the explicitly configured read-only verifier connection URL."""
    db_url = get_settings().DATABASE_URL_COMPLIANCE_AUDITOR
    if not db_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Compliance database connection is not configured.",
        )
    from sqlalchemy.engine import make_url
    url = make_url(db_url).set(drivername="postgresql")
    query = dict(url.query)
    if "ssl" in query:
        if "sslmode" in query:
            raise HTTPException(status_code=503, detail="Conflicting database TLS settings.")
        query["sslmode"] = query.pop("ssl")
    return url.set(query=query).render_as_string(hide_password=False)


def _sync_timeout_options() -> str:
    settings = get_settings()
    return f"-c statement_timeout={settings.DB_STATEMENT_TIMEOUT_MS} -c lock_timeout={settings.DB_LOCK_TIMEOUT_MS}"


async def _generate_capsule_with_legacy_attestation(seq_id: int) -> bytes:
    """Build a normal capsule or issue a guarded retrospective attestation for legacy checkpoints."""
    from db.cli.capsule import PreMerkleCheckpointError, generate_capsule

    db_url = _compliance_sync_db_url()

    def _execute(retrospective_signer=None):
        import psycopg2

        conn = psycopg2.connect(db_url, connect_timeout=5, options=_sync_timeout_options())
        try:
            return generate_capsule(
                conn,
                seq_id,
                retrospective_signer=retrospective_signer,
                public_keys_dir=get_settings().CHECKPOINT_PUBLIC_KEYS_DIR,
            )
        finally:
            conn.close()

    try:
        return await asyncio.to_thread(_execute)
    except PreMerkleCheckpointError:
        if get_settings().APP_ENV != "development":
            raise
        # Legacy proof creation is allowed only with the local demo signer;
        # production signer custody must be provided by a managed signer.
        from .checkpoints import _load_signer

        signer = _load_signer()
        return await asyncio.to_thread(_execute, signer)
SUSPICIOUS_ACTIVITY_REFRESH_LOCK_KEY = 280375465843


def _verification_status_from_checks(checks: dict[str, str]) -> str:
    """Return a conservative aggregate status for checks actually performed."""
    required = ("hash_chain", "external_anchor", "checkpoint_signatures")
    values = [checks.get(name, "unknown") for name in required]
    if "fail" in values:
        return "tampered"
    if all(value == "pass" for value in values):
        return "intact"
    return "unknown"

# ─── Dependency: compliance_auditor only ──────────────────────────────────────

_auditor_only = [Depends(require_role(["compliance_auditor"]))]


async def _blind_index_request_budget(
    filters: AuditLogSearchRequest,
    current_user: User = Depends(get_current_user),
):
    settings = get_settings()
    if settings.APP_ENV != "development":
        # Charge before get_db_session reserves a connection. This avoids
        # waiting for a second connection while the same small pool is full.
        await consume_request_budget(current_user, "blind_index", settings.BLIND_INDEX_RATE_LIMIT_PER_MINUTE)


async def _reject_sensitive_search_url(request: Request):
    if "national_id_search" in request.query_params:
        raise HTTPException(status_code=400, detail="Submit national ID searches to POST /api/audit-logs/search in the JSON body.")


# ─── GET /api/audit-logs ──────────────────────────────────────────────────────

@router.get(
    "/audit-logs",
    response_model=PaginatedResponse[AuditLogItem],
    dependencies=_auditor_only + [Depends(_reject_sensitive_search_url)],
)
async def list_audit_logs(
    request: Request = None,
    actor_id: Optional[int] = Query(None, description="Filter by actor user_id"),
    action: Optional[str] = Query(None, description="INSERT | UPDATE | DELETE"),
    table_name: Optional[str] = Query(None, description="Filter by table name"),
    severity: Optional[str] = Query(None, description="INFO | WARNING | CRITICAL"),
    national_id_search: Optional[str] = Query(None, max_length=255, deprecated=True, description="Rejected legacy URL parameter; use POST /api/audit-logs/search instead"),
    sequence_id: Optional[int] = Query(None, description="Filter by exact sequence_id"),
    employee_id: Optional[int] = Query(None, description="Filter by employee_id"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    before_sequence_id: Optional[int] = Query(None, ge=1, description="Return entries older than this sequence; use next_cursor from the previous response"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, scope="function"),
):
    """Retrieve paginated audit log entries with optional filters.

    Joins audit_log → users to resolve actor_name.
    Accessible to compliance_auditor role only — enforced both by the
    require_role dependency and by the compliance_auditor Postgres pool
    which has SELECT-only access to audit_log.
    """
    # Join the current profile for display, while always returning the immutable
    # actor_user_id from the event itself.
    query = (
        select(
            AuditLog.sequence_id,
            AuditLog.actor_user_id,
            func.coalesce(
                func.nullif(func.nullif(func.trim(User.full_name), ""), "Unknown"),
                func.nullif(func.trim(User.email), ""),
                case(
                    (AuditLog.actor_user_id.is_(None), "System"),
                    else_=func.concat("unresolved_user#", AuditLog.actor_user_id),
                ),
            ).label("actor_name"),
            AuditLog.employee_id,
            AuditLog.action,
            AuditLog.table_name,
            AuditLog.row_id,
            AuditLog.old_value,
            AuditLog.new_value,
            AuditLog.severity,
            AuditLog.entry_hash,
            AuditLog.previous_hash,
            AuditLog.created_at,
        )
        .outerjoin(User, AuditLog.actor_user_id == User.user_id)
    )

    # Apply optional filters
    if actor_id is not None:
        query = query.where(AuditLog.actor_user_id == actor_id)
    if action:
        query = query.where(AuditLog.action == action.upper())
    if table_name:
        query = query.where(AuditLog.table_name.ilike(f"%{table_name}%"))
    if severity:
        query = query.where(AuditLog.severity == severity.upper())
    if sequence_id is not None:
        query = query.where(AuditLog.sequence_id == sequence_id)
    if employee_id is not None:
        employee_id_text = str(employee_id)
        query = query.where(
            or_(
                AuditLog.employee_id == employee_id,
                and_(
                    AuditLog.table_name == "employees",
                    AuditLog.row_id == employee_id,
                ),
                and_(
                    AuditLog.table_name == "salary_history",
                    or_(
                        AuditLog.new_value["employee_id"].astext == employee_id_text,
                        AuditLog.old_value["employee_id"].astext == employee_id_text,
                    ),
                ),
            )
        )

    client_ip = (
        request.client.host
        if (request is not None and getattr(request, "client", None) is not None)
        else "127.0.0.1"
    )
    blind_index = None
    clean_nid = None

    if national_id_search:
        settings = get_settings()
        clean_nid = national_id_search.strip()
        if clean_nid:
            try:
                audit_salt = validate_audit_salt(settings.AUDIT_SALT)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Blind-index search is not configured correctly.",
                ) from exc

            rate_limit_key = (
                f"user:{current_user.user_id}"
                if (current_user and getattr(current_user, "user_id", None))
                else f"ip:{client_ip}"
            )

            # Enforce 10 req/min rate limit (HARDEN-009 / Step 11.B.6)
            if settings.APP_ENV != "development":
                allowed, count, retry_after = True, 0, 0
            else:
                allowed, count, retry_after = rate_limiter.check_rate_limit(rate_limit_key)
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded for blind index searches (max 10 requests/minute). Please wait before retrying.",
                    headers={"Retry-After": str(int(math.ceil(retry_after)))},
                )
            if settings.APP_ENV == "development":
                rate_limiter.record_request(rate_limit_key)

            blind_index = compute_blind_index(
                clean_nid,
                salt=audit_salt,
                iterations=settings.BLIND_INDEX_ITERATIONS,
                mode=settings.BLIND_INDEX_MODE,
            )
            query = query.where(
                or_(
                    AuditLog.new_value["national_id_blind_index"].astext == blind_index,
                    AuditLog.old_value["national_id_blind_index"].astext == blind_index,
                )
            )

    # Count total matching rows
    count_q = select(func.count()).select_from(query.subquery())
    total = await session.scalar(count_q) or 0
    pages = math.ceil(total / limit) if total > 0 else 0
    if before_sequence_id is not None:
        query = query.where(AuditLog.sequence_id < before_sequence_id)

    # Record Audit-the-Auditor forensic security event (Step 11.B.6)
    if national_id_search and clean_nid and blind_index:
        event = audit_logger.log_search(
            actor_user_id=getattr(current_user, "user_id", 0),
            actor_email=getattr(current_user, "email", "unknown"),
            blind_index=blind_index,
            matches_found=total,
            client_ip=client_ip,
        )
        session.add(
            SecurityAuditEvent(
                event_type=event["event"],
                actor_user_id=event["actor_user_id"],
                actor_email=event["actor_email"],
                blind_index=event["blind_index"],
                created_at=datetime.fromisoformat(event["timestamp"]),
                matches_found=event["matches_found"],
                client_ip=event["client_ip"],
            )
        )

    # Paginate — newest entries first
    if before_sequence_id is None:
        query = query.offset((page - 1) * limit)
    query = query.order_by(AuditLog.sequence_id.desc()).limit(limit + 1)
    result = await session.execute(query)
    fetched_rows = result.all()
    has_more = len(fetched_rows) > limit
    rows = fetched_rows[:limit]

    forensic_before_by_seq = _forensic_before_payloads()
    items = [
        AuditLogItem(
            sequence_id=row.sequence_id,
            actor_user_id=row.actor_user_id,
            actor_name=row.actor_name,
            employee_id=row.employee_id,
            action=row.action,
            table_name=row.table_name,
            row_id=row.row_id,
            old_value=row.old_value,
            new_value=row.new_value,
            forensic_before_value=forensic_before_by_seq.get(row.sequence_id),
            severity=row.severity,
            entry_hash=row.entry_hash,
            previous_hash=row.previous_hash,
            created_at=row.created_at,
        )
        for row in rows
    ]

    next_cursor = items[-1].sequence_id if has_more and items else None
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        pages=pages,
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.post(
    "/audit-logs/search",
    response_model=PaginatedResponse[AuditLogItem],
    dependencies=_auditor_only + [Depends(_reject_sensitive_search_url), Depends(_blind_index_request_budget)],
)
async def search_audit_logs(
    filters: AuditLogSearchRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, scope="function"),
):
    """Search by a sensitive identifier without putting it in an access-log URL."""
    return await list_audit_logs(
        request=request, current_user=current_user, session=session,
        **filters.model_dump(),
    )


# ─── GET /api/audit-logs/security-events ──────────────────────────────────────

@router.get(
    "/audit-logs/security-events",
    dependencies=_auditor_only,
    summary="List recent blind index search telemetry events (Audit-the-Auditor)",
)
async def list_security_events(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, scope="function"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Retrieve security telemetry audit events recording blind index queries.

    Demonstrates compliance with 'Audit-the-Auditor' regulatory controls by logging
    every search performed on structured identity indices without exposing PII.
    """
    total = await session.scalar(select(func.count()).select_from(SecurityAuditEvent)) or 0
    result = await session.execute(
        select(SecurityAuditEvent)
        .order_by(desc(SecurityAuditEvent.created_at), desc(SecurityAuditEvent.event_id))
        .offset(offset)
        .limit(limit)
    )
    stored_events = [
        {
            "event": row.event_type,
            "timestamp": row.created_at.isoformat(),
            "actor_user_id": row.actor_user_id,
            "actor_email": row.actor_email,
            "blind_index": row.blind_index,
            "matches_found": row.matches_found,
            "client_ip": row.client_ip,
        }
        for row in result.scalars().all()
    ]
    # Keep the legacy in-process snapshot as a compatibility overlay for older
    # test/development stores while the durable database remains authoritative.
    seen = {(e["actor_user_id"], e["blind_index"], e["timestamp"]) for e in stored_events}
    if not total and offset == 0:
        for event in audit_logger.get_audit_events():
            key = (event["actor_user_id"], event["blind_index"], event["timestamp"])
            if key not in seen:
                stored_events.append(event)
                seen.add(key)
    stored_events = stored_events[:limit]
    return {
        "total": max(int(total), len(stored_events)),
        "events": stored_events,
        "limit": limit,
        "offset": offset,
    }


# ─── POST /api/verify ─────────────────────────────────────────────────────────

@router.post(
    "/verify",
    response_model=VerificationResult,
    dependencies=_auditor_only,
)
async def run_verification(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, scope="function"),
):
    """Trigger the standalone verifier to scan the hash chain.

    Accessible to compliance_auditor only. Failed checkpoint signatures include
    signed-data and signature comparison evidence when a local adversary
    recovery snapshot provides a baseline.
    """
    settings = get_settings()
    db_url = _compliance_sync_db_url()

    def _execute_verification():
        try:
            import json
            from pathlib import Path
            import psycopg2
            from db.cli.hash_verifier import verify_chain
            conn = psycopg2.connect(db_url, connect_timeout=2, options=_sync_timeout_options())
            try:
                res = verify_chain(conn)
                tampered_seq = None
                checkpoint_signature_evidence = None
                deleted_entry_evidence = None
                checks = {
                    "hash_chain": "pass" if res.is_valid and res.total_entries > 0 else "fail" if not res.is_valid else "unknown",
                    "external_anchor": "unknown",
                    "checkpoint_signatures": "unknown",
                }
                evidence_errors = []

                # The API can currently read the local file adapter only. Do
                # not label local storage as an independently queried remote
                # anchor, and require a record for the latest checkpoint.
                settings = get_settings()
                configured_path = Path(settings.ANCHOR_FILE_PATH)
                anchor_directory = (
                    configured_path.parent if configured_path.suffix else configured_path
                )
                if settings.ANCHOR_STORE == "local_file":
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT checkpoint_id, sequence_id, checkpoint_hash "
                            "FROM chain_checkpoints ORDER BY sequence_id DESC LIMIT 1"
                        )
                        latest_anchor_target = cur.fetchone()
                    if latest_anchor_target:
                        checkpoint_id, checkpoint_sequence, checkpoint_hash = latest_anchor_target
                        anchor_path = anchor_directory / f"{checkpoint_id}.json"
                        try:
                            anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
                            if (
                                anchor.get("checkpoint_id") != checkpoint_id
                                or anchor.get("sequence_id") != checkpoint_sequence
                                or anchor.get("checkpoint_hash") != checkpoint_hash
                            ):
                                checks["external_anchor"] = "fail"
                                tampered_seq = int(checkpoint_sequence)
                                evidence_errors.append(
                                    f"Local anchor record does not match checkpoint {checkpoint_id}."
                                )
                            else:
                                checks["external_anchor"] = "pass"
                        except FileNotFoundError:
                            evidence_errors.append(
                                f"No local anchor record exists for latest checkpoint {checkpoint_id}."
                            )
                        except (OSError, json.JSONDecodeError, TypeError):
                            evidence_errors.append(
                                f"Local anchor record for checkpoint {checkpoint_id} could not be verified."
                            )
                    else:
                        evidence_errors.append("No checkpoint is available for local anchor comparison.")
                else:
                    evidence_errors.append(
                        "The configured anchor provider has no independent read-back verifier."
                    )

                # Signatures are verified only when a public key and a complete
                # set of signed checkpoint rows are available.
                try:
                    from db.cli.keygen import load_public_key
                    from db.cli.signer import verify_signature
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT checkpoint_id, checkpoint_hash, signature, sequence_id, "
                            "merkle_root, key_id, created_at FROM chain_checkpoints "
                            "ORDER BY checkpoint_id"
                        )
                        checkpoints = cur.fetchall()
                    if checkpoints and all(checkpoint[2] for checkpoint in checkpoints):
                        checks["checkpoint_signatures"] = "pass"
                        key_directory = Path(settings.CHECKPOINT_PUBLIC_KEYS_DIR)
                        for checkpoint_id, checkpoint_hash, signature, sequence_id, merkle_root, key_id, created_at in checkpoints:
                            # Older rows without key_id use the documented legacy
                            # public_key.pem. New key IDs map to URL-escaped PEM
                            # filenames in CHECKPOINT_PUBLIC_KEYS_DIR.
                            key_path = _checkpoint_public_key_path(key_id, key_directory)
                            if not key_path.is_file():
                                checks["checkpoint_signatures"] = "unknown"
                                evidence_errors.append(
                                    f"Trusted public key for checkpoint key ID {key_id or 'legacy'} is unavailable."
                                )
                                continue
                            pub = load_public_key(str(key_path))
                            if not verify_signature(
                                pub, checkpoint_hash, bytes(signature), merkle_root=merkle_root
                            ):
                                checks["checkpoint_signatures"] = "fail"
                                if sequence_id:
                                    tampered_seq = int(sequence_id)
                                evidence_errors.append(f"Checkpoint signature verification failed for checkpoint {checkpoint_id}.")
                                if checkpoint_signature_evidence is None:
                                    before_signature_hex = None
                                    before_checkpoint_hash = None
                                    before_merkle_root = None
                                    before_signature_status = "unknown"
                                    forensic_snapshot = _load_local_attack_snapshot()
                                    if (
                                        forensic_snapshot
                                        and forensic_snapshot.get("scenario") in {"checkpoint-forgery", "recompute-and-hide"}
                                    ):
                                        saved_checkpoints = forensic_snapshot.get("checkpoints", [])
                                        saved_checkpoint = next(
                                            (
                                                item for item in saved_checkpoints
                                                if item.get("checkpoint_id") == checkpoint_id
                                            ),
                                            None,
                                        )
                                        before_signature_hex = (
                                            saved_checkpoint.get("signature_hex")
                                            if saved_checkpoint else None
                                        )
                                        before_checkpoint_hash = (
                                            saved_checkpoint.get("checkpoint_hash")
                                            if saved_checkpoint else None
                                        )
                                        before_merkle_root = (
                                            saved_checkpoint.get("merkle_root")
                                            if saved_checkpoint else None
                                        )
                                        if before_signature_hex:
                                            try:
                                                before_signature_status = (
                                                    "pass"
                                                    if verify_signature(
                                                        pub,
                                                        before_checkpoint_hash or checkpoint_hash,
                                                        bytes.fromhex(before_signature_hex),
                                                        merkle_root=before_merkle_root or merkle_root,
                                                    )
                                                    else "fail"
                                                )
                                            except (ValueError, TypeError):
                                                before_signature_status = "fail"

                                    try:
                                        from cryptography.hazmat.primitives import serialization

                                        public_key_fingerprint = hashlib.sha256(
                                            pub.public_bytes(
                                                serialization.Encoding.DER,
                                                serialization.PublicFormat.SubjectPublicKeyInfo,
                                            )
                                        ).hexdigest()
                                    except Exception:
                                        public_key_fingerprint = None

                                    checkpoint_signature_evidence = {
                                        "checkpoint_id": int(checkpoint_id),
                                        "sequence_id": int(sequence_id),
                                        "checkpoint_hash_before": (
                                            str(before_checkpoint_hash)
                                            if before_checkpoint_hash is not None else None
                                        ),
                                        "checkpoint_hash": str(checkpoint_hash),
                                        "merkle_root_before": (
                                            bytes(before_merkle_root).hex()
                                            if isinstance(before_merkle_root, (bytes, bytearray, memoryview))
                                            else str(before_merkle_root) if before_merkle_root is not None else None
                                        ),
                                        "merkle_root": (
                                            bytes(merkle_root).hex()
                                            if isinstance(merkle_root, (bytes, bytearray, memoryview))
                                            else str(merkle_root) if merkle_root is not None else None
                                        ),
                                        "key_id": key_id,
                                        "public_key_fingerprint": public_key_fingerprint,
                                        "created_at": created_at.isoformat() if created_at else None,
                                        "signature_before_hex": before_signature_hex,
                                        "signature_before_status": before_signature_status,
                                        "signature_after_hex": bytes(signature).hex(),
                                        "signature_after_status": "fail",
                                        "hash_chain_status": checks["hash_chain"],
                                        "anchor_status": checks["external_anchor"],
                                        "before_source": (
                                            f"recovery_snapshot:{forensic_snapshot.get('scenario')}"
                                            if before_signature_hex and forensic_snapshot else None
                                        ),
                                    }
                                break
                    else:
                        evidence_errors.append("Checkpoint signatures are missing or no checkpoints exist.")
                except Exception:
                    checks["checkpoint_signatures"] = "unknown"
                    evidence_errors.append("Checkpoint signature verification could not be completed.")

                # Once independent hash/anchor/signature checks have already
                # proven a breach, the local recovery snapshot may point the UI
                # to the edited source event. It never changes a check result
                # or causes the verifier to report a breach by itself.
                if res.is_valid and any(
                    checks.get(name) == "fail"
                    for name in ("external_anchor", "checkpoint_signatures")
                ):
                    forensic_snapshot = _load_local_attack_snapshot()
                    try:
                        forensic_target = int(forensic_snapshot["target_sequence_id"])
                        if forensic_target > 0:
                            tampered_seq = forensic_target
                    except (TypeError, KeyError, ValueError):
                        pass

                if checkpoint_signature_evidence:
                    checkpoint_signature_evidence["hash_chain_status"] = checks["hash_chain"]
                    checkpoint_signature_evidence["anchor_status"] = checks["external_anchor"]
                return (
                    res,
                    checks,
                    tampered_seq,
                    evidence_errors,
                    checkpoint_signature_evidence,
                    deleted_entry_evidence,
                )
            finally:
                conn.close()
        except BaseException as exc:
            return exc

    verify_output = await asyncio.to_thread(_execute_verification)

    if isinstance(verify_output, BaseException):
        logger.error("Audit verification failed (%s)", type(verify_output).__name__)
        return VerificationResult(
            status="error",
            entries_scanned=0,
            anchor_match=False,
            last_verified_sequence_id=0,
            tampered_sequence_id=None,
            details="Verification engine failure: unable to connect to or verify the database.",
            verification_checks={
                "hash_chain": "unknown",
                "external_anchor": "unknown",
                "checkpoint_signatures": "unknown",
            },
        )

    (
        res,
        checks,
        tampered_seq,
        evidence_errors,
        checkpoint_signature_evidence,
        deleted_entry_evidence,
    ) = verify_output
    if not res.is_valid:
        tampered_id = None
        details = "Integrity violation detected."
        if res.mismatches:
            tampered_id = res.mismatches[0].get("sequence_id")
            details = f"Hash mismatch at sequence_id {tampered_id}: expected {res.mismatches[0].get('expected', '')[:16]}... actual {res.mismatches[0].get('actual', '')[:16]}..."
        elif res.gaps:
            tampered_id = res.gaps[0].get("expected_seq")
            details = f"Sequence gap at sequence_id {tampered_id}: expected {res.gaps[0].get('expected_seq')}, found {res.gaps[0].get('actual_seq')}."
            if tampered_id is not None:
                deleted_entry_evidence = _deleted_entry_snapshot(int(tampered_id))
        elif res.orphans:
            tampered_id = res.orphans[0].get("sequence_id")
            details = f"Orphaned entry at sequence_id {tampered_id}: previous_hash does not link to predecessor."

        final_tampered = tampered_id or tampered_seq
        last_valid = (final_tampered - 1) if (final_tampered and final_tampered > 0) else 0
        return VerificationResult(
            status="tampered",
            entries_scanned=res.total_entries,
            anchor_match=checks["external_anchor"] == "pass",
            last_verified_sequence_id=last_valid,
            tampered_sequence_id=final_tampered,
            details=details,
            verification_checks=checks,
            checkpoint_signature_evidence=checkpoint_signature_evidence,
            deleted_entry_evidence=deleted_entry_evidence,
        )
    overall_status = _verification_status_from_checks(checks)
    if overall_status == "tampered":
        last_verified = res.last_sequence_id if res.last_sequence_id >= 0 else 0
        return VerificationResult(
            status="tampered",
            entries_scanned=res.total_entries,
            anchor_match=checks["external_anchor"] == "pass",
            last_verified_sequence_id=last_verified,
            tampered_sequence_id=tampered_seq,
            details=" ".join(evidence_errors) or "A cryptographic checkpoint check failed.",
            verification_checks=checks,
            checkpoint_signature_evidence=checkpoint_signature_evidence,
            deleted_entry_evidence=deleted_entry_evidence,
        )

    last_verified = res.last_sequence_id if res.last_sequence_id >= 0 else 0
    if overall_status == "intact":
        details = f"Hash-chain continuity, configured local anchor record, and checkpoint signatures verified across {res.total_entries} entries."
    else:
        check_labels = {
            "hash_chain": "audit hash chain",
            "external_anchor": "configured anchor record comparison",
            "checkpoint_signatures": "checkpoint signatures",
        }
        unverified = [check_labels.get(name, name.replace("_", " ")) for name, value in checks.items() if value == "unknown"]
        details = "Hash-chain walk completed, but verification remains incomplete. Unverified: " + ", ".join(unverified) + "."
        if evidence_errors:
            details += " " + " ".join(dict.fromkeys(evidence_errors))
    return VerificationResult(
        status=overall_status,
        entries_scanned=res.total_entries,
        anchor_match=checks["external_anchor"] == "pass",
        last_verified_sequence_id=last_verified,
        tampered_sequence_id=None,
        details=details,
        verification_checks=checks,
    )


# ─── GET /api/suspicious-activity ────────────────────────────────────────────

@router.get(
    "/suspicious-activity",
    response_model=list[SuspiciousFlagItem],
    dependencies=_auditor_only,
)
async def list_suspicious_flags(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, scope="function"),
):
    """List all suspicious activity flags, newest first.

    Populated by Abhinav's Week 8 refresh_suspicious_activity_flags()
    procedure.
    """
    result = await session.execute(
        select(SuspiciousActivityFlag).order_by(
            SuspiciousActivityFlag.created_at.desc()
        )
    )
    flags = result.scalars().all()

    return [
        SuspiciousFlagItem(
            flag_id=f.flag_id,
            audit_log_sequence_id=f.audit_log_sequence_id,
            flag_reason=f.flag_reason,
            reviewed_by=f.reviewed_by_user_id,
            reviewed_at=f.reviewed_at,
            created_at=f.created_at,
        )
        for f in flags
    ]


@router.post(
    "/suspicious-activity/refresh",
    dependencies=_auditor_only,
    summary="Refresh suspicious-activity detections",
)
async def refresh_suspicious_flags(
    session: AsyncSession = Depends(get_db_session, scope="function"),
):
    """Run the idempotent database detector explicitly and report failures."""
    try:
        lock_result = await session.execute(
            text("SELECT pg_try_advisory_xact_lock(:lock_key)"),
            {"lock_key": SUSPICIOUS_ACTIVITY_REFRESH_LOCK_KEY},
        )
        if not lock_result.scalar():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Suspicious-activity detection is already running.",
            )
        await session.execute(text("CALL refresh_suspicious_activity_flags()"))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Suspicious-activity detection could not be refreshed.",
        ) from exc
    return {"status": "refreshed"}


# ─── POST /api/suspicious-activity/{id}/review ───────────────────────────────

@router.post(
    "/suspicious-activity/{flag_id}/review",
    response_model=SuspiciousReviewResponse,
    dependencies=_auditor_only,
)
async def review_suspicious_flag(
    flag_id: int,
    payload: Optional[SuspiciousReviewRequest] = Body(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, scope="function"),
):
    """Mark a suspicious activity flag as reviewed by the current auditor."""
    result = await session.execute(
        select(SuspiciousActivityFlag).where(
            SuspiciousActivityFlag.flag_id == flag_id
        )
    )
    flag = result.scalar_one_or_none()

    if flag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suspicious activity flag {flag_id} not found.",
        )

    now = datetime.now(timezone.utc)
    flag.reviewed_by_user_id = current_user.user_id
    flag.reviewed_at = now
    session.add(
        SuspiciousActivityReview(
            flag_id=flag.flag_id,
            reviewer_user_id=current_user.user_id,
            action="reviewed",
            note=payload.note if payload else None,
        )
    )
    await session.flush()

    return SuspiciousReviewResponse(
        flag_id=flag.flag_id,
        reviewed_by_user_id=current_user.user_id,
        reviewed_at=now,
    )


# ─── GET /api/employees/{employee_id}/time-travel ────────────────────────────

@router.get(
    "/employees/{employee_id}/time-travel",
    response_model=TimeTravelResponse,
    dependencies=_auditor_only,
)
async def reconstruct_employee_state(
    employee_id: int,
    timestamp: str = Query(..., description="Target ISO timestamp"),
    sequence_id: Optional[int] = Query(None, description="Optional target sequence ID for exact event reconstruction"),
    include_pii: bool = Query(False, description="Explicitly reveal sensitive fields; access is recorded"),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, scope="function"),
):
    """Reconstruct an employee's record state at a specific past timestamp or exact sequence ID.
    
    Accessible to compliance_auditor only.
    Invokes the PostgreSQL reconstruct_employee_state(:emp_id, :as_of) stored routine or
    computes deterministic ledger replay bounded by sequence_id.
    """
    clean_ts = timestamp.strip()
    # Normalize space decoded from '+' by URL query parser (e.g. 2026-09-17T17:21:23.207405 00:00 -> +00:00)
    if " " in clean_ts and "+" not in clean_ts:
        clean_ts = clean_ts.replace(" ", "+")
    if clean_ts.endswith("Z") or clean_ts.endswith("z"):
        clean_ts = clean_ts[:-1] + "+00:00"

    try:
        parsed_dt = datetime.fromisoformat(clean_ts)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid ISO timestamp format: '{timestamp}'. Expected ISO-8601 format.",
        )

    if parsed_dt.tzinfo is None:
        parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)

    if sequence_id is not None:
        # Sequence-level precision: replay mutations bounded by sequence_id
        recon_res = await session.execute(
            text("""
                SELECT action, new_value
                FROM audit_log
                WHERE table_name = 'employees'
                  AND row_id = :emp_id
                  AND sequence_id <= :seq_id
                ORDER BY sequence_id ASC
            """),
            {"emp_id": employee_id, "seq_id": sequence_id},
        )
        rows = recon_res.fetchall()
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee {employee_id} did not exist as of sequence #{sequence_id} ({parsed_dt.isoformat()}).",
            )
        state = None
        for action, new_val in rows:
            if isinstance(new_val, str):
                try:
                    new_val = json.loads(new_val)
                except Exception:
                    new_val = {}
            if action == "INSERT":
                state = dict(new_val) if isinstance(new_val, dict) else {}
            elif action == "UPDATE":
                if state is not None and isinstance(state, dict) and isinstance(new_val, dict):
                    state.update(new_val)
                else:
                    state = dict(new_val) if isinstance(new_val, dict) else {}
            elif action == "DELETE":
                state = None

        if state is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee {employee_id} was deleted as of sequence #{sequence_id}.",
            )
    else:
        # Stored routine execution
        recon_res = await session.execute(
            text("SELECT reconstruct_employee_state(:emp_id, :as_of)"),
            {"emp_id": employee_id, "as_of": parsed_dt},
        )
        state = recon_res.scalar()

        # If state is None, employee did not exist as of target timestamp
        if state is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee {employee_id} did not exist as of {parsed_dt.isoformat()}.",
            )

        if isinstance(state, str):
            try:
                state = json.loads(state)
            except Exception:
                state = {}

    full_name = state.get("full_name", "")
    email = state.get("email", "")
    is_active = bool(state.get("is_active", True))
    role_id = state.get("role_id")

    # Parse date_hired
    raw_date_hired = state.get("date_hired")
    if isinstance(raw_date_hired, str):
        try:
            date_hired_dt = datetime.fromisoformat(raw_date_hired)
        except Exception:
            date_hired_dt = datetime.combine(date.fromisoformat(raw_date_hired), datetime.min.time())
    elif isinstance(raw_date_hired, (datetime, date)) and not isinstance(raw_date_hired, datetime):
        date_hired_dt = datetime.combine(raw_date_hired, datetime.min.time())
    elif isinstance(raw_date_hired, datetime):
        date_hired_dt = raw_date_hired
    else:
        date_hired_dt = datetime.now(timezone.utc)

    # Resolve Role and Department
    role_title = "Unknown"
    department_name = "Unknown"
    if role_id is not None:
        role_res = await session.execute(
            select(Role.title, Department.name)
            .join(Department, Role.department_id == Department.department_id)
            .where(Role.role_id == int(role_id))
        )
        role_row = role_res.first()
        if role_row:
            try:
                role_title = str(role_row[0])
                department_name = str(role_row[1])
            except (IndexError, TypeError, ValueError):
                role_title, department_name = "Unknown", "Unknown"

    # Resolve Salary as of target timestamp or sequence ID
    if sequence_id is not None:
        sal_res = await session.execute(
            text("""
                SELECT (new_value->>'amount')::NUMERIC
                FROM audit_log
                WHERE table_name = 'salary_history'
                  AND (employee_id = :emp_id OR (new_value->>'employee_id')::INT = :emp_id)
                  AND sequence_id <= :seq_id
                ORDER BY sequence_id DESC
                LIMIT 1
            """),
            {"emp_id": employee_id, "seq_id": sequence_id},
        )
        sal_row = sal_res.scalar()
        try:
            salary = float(sal_row) if sal_row is not None else None
        except (TypeError, ValueError):
            salary = None
    else:
        sal_res = await session.execute(
            text("""
                SELECT (new_value->>'amount')::NUMERIC
                FROM audit_log
                WHERE table_name = 'salary_history'
                  AND (employee_id = :emp_id OR (new_value->>'employee_id')::INT = :emp_id)
                  AND created_at <= :as_of
                ORDER BY sequence_id DESC
                LIMIT 1
            """),
            {"emp_id": employee_id, "as_of": parsed_dt},
        )
        sal_row = sal_res.scalar()
        try:
            salary = float(sal_row) if sal_row is not None else None
        except (TypeError, ValueError):
            salary = None

    session.add(
        SecurityAuditEvent(
            event_type="TIME_TRAVEL_PII_REVEAL" if include_pii else "TIME_TRAVEL_VIEW_REDACTED",
            actor_user_id=current_user.user_id,
            actor_email=current_user.email,
            blind_index=None,
            employee_id=employee_id,
            sequence_id=sequence_id,
            matches_found=1,
            client_ip=(request.client.host if request and request.client else "127.0.0.1"),
        )
    )

    return TimeTravelResponse(
        employee_id=employee_id,
        full_name=full_name if include_pii else None,
        email=email if include_pii else None,
        role_title=role_title,
        department_name=department_name,
        salary=salary if include_pii else None,
        date_hired=date_hired_dt,
        is_active=is_active,
        as_of=parsed_dt,
        sequence_id=sequence_id,
        pii_redacted=not include_pii,
    )



# ─── GET /api/audit-logs/export ───────────────────────────────────────────────

from fastapi.responses import StreamingResponse, Response
import io
import json
from ..services.export import generate_signed_evidence_export, generate_evidence_bundle

@router.get(
    "/audit-logs/export",
    dependencies=_auditor_only,
)
async def export_signed_evidence(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, scope="function"),
):
    """
    Export the full audit trail as a cryptographically signed JSON file.
    
    Accessible to compliance_auditor only.
    """
    export_data = await generate_signed_evidence_export(session)
    
    # Create an in-memory file for streaming
    file_stream = io.BytesIO(json.dumps(export_data, indent=2).encode('utf-8'))
    
    # Return as an attachment
    return StreamingResponse(
        file_stream, 
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=argus_evidence_{export_data['data']['generated_at']}.json"
        }
    )


@router.get(
    "/audit-logs/export-pack",
    dependencies=_auditor_only,
)
async def export_evidence_pack(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, scope="function"),
):
    """Export self-contained .arguspack evidence archive (PACK-002).
    
    Contains canonical audit events, detached Ed25519 signature, manifest,
    checkpoints, and embedded zero-dependency standalone verifier CLI.
    Accessible to compliance_auditor only.
    """
    bundle_bytes = await generate_evidence_bundle(session)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"audit_evidence_{timestamp}.arguspack"

    return Response(
        content=bundle_bytes,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Argus-Bundle-Version": "1.0",
        },
    )



# ─── Live Chain & Anchor Synchronization (BRIDGE-001) ─────────────────────────

def _map_severity_to_frontend(severity: Optional[str]) -> str:
    if not severity:
        return "low"
    mapping = {
        "INFO": "low",
        "WARNING": "medium",
        "CRITICAL": "critical",
    }
    return mapping.get(str(severity).upper(), str(severity).lower())


@router.get(
    "/audit-logs/chain",
    response_model=List[ChainEntry],
    dependencies=_auditor_only,
)
async def get_audit_chain(
    response: Response,
    limit: int = Query(10, ge=1, le=100, description="Number of entries to return (newest first)"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    around_seq: Optional[int] = Query(None, description="Center window around a specific sequence_id"),
    table_name: Optional[str] = Query(None, description="Filter by table name"),
    action: Optional[str] = Query(None, description="Filter by action: INSERT, UPDATE, DELETE"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, scope="function"),
):
    """Retrieve audit hash chain entries with optional pagination, filters, or centered around a sequence ID."""
    count_query = select(func.count(AuditLog.sequence_id))
    if table_name:
        count_query = count_query.where(AuditLog.table_name == table_name)
    if action:
        count_query = count_query.where(AuditLog.action == action.upper())

    total_res = await session.execute(count_query)
    total_count = total_res.scalar() or 0
    response.headers["X-Total-Count"] = str(total_count)

    query = (
        select(
            AuditLog.sequence_id,
            AuditLog.entry_hash,
            AuditLog.previous_hash,
            AuditLog.table_name,
            AuditLog.action,
            User.email.label("actor_email"),
            User.role.label("actor_role"),
            AuditLog.actor_user_id,
            AuditLog.created_at,
            AuditLog.severity,
            AuditLog.old_value,
            AuditLog.new_value,
        )
        .outerjoin(User, AuditLog.actor_user_id == User.user_id)
    )

    if around_seq is not None:
        half = limit // 2
        start_seq = max(1, around_seq - half)
        end_seq = start_seq + limit - 1
        query = query.where(AuditLog.sequence_id >= start_seq, AuditLog.sequence_id <= end_seq)

    if table_name:
        query = query.where(AuditLog.table_name == table_name)
    if action:
        query = query.where(AuditLog.action == action.upper())

    query = query.order_by(AuditLog.sequence_id.desc())

    if around_seq is None:
        query = query.offset(offset).limit(limit)
    else:
        query = query.limit(limit)

    result = await session.execute(query)
    rows = result.all()

    forensic_before_by_seq = _forensic_before_payloads()
    chain: List[ChainEntry] = []
    for row in rows:
        actor_user_id = getattr(row, "actor_user_id", None)
        chain.append(
            ChainEntry(
                entry_id=row.sequence_id,
                hash=row.entry_hash,
                prev_hash=row.previous_hash,
                table_name=row.table_name,
                operation=row.action,
                actor_email=(
                    row.actor_email
                    or (f"unresolved_user#{actor_user_id}" if actor_user_id is not None else "system@argus.internal")
                ),
                actor_user_id=actor_user_id,
                actor_role=(
                    row.actor_role
                    or ("unknown" if actor_user_id is not None else "system")
                ),
                timestamp=row.created_at,
                severity=_map_severity_to_frontend(row.severity),
                old_value=row.old_value,
                new_value=row.new_value,
                forensic_before_value=forensic_before_by_seq.get(row.sequence_id),
            )
        )
    return chain


@router.get(
    "/anchor/status",
    response_model=AnchorInfo,
    dependencies=_auditor_only,
)
async def get_anchor_status(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, scope="function"),
):
    """Retrieve the cryptographic anchor state and delta from chain tail."""
    settings = get_settings()
    store_type = settings.ANCHOR_STORE
    location = ("Not configured" if store_type == "none" else
                settings.GITHUB_ANCHOR_REPOSITORY if store_type == "github_repo" else settings.ANCHOR_FILE_PATH)

    # Fetch latest checkpoint
    latest_chk = None
    try:
        chk_res = await session.execute(
            text("SELECT checkpoint_id, sequence_id, checkpoint_hash, created_at, key_id FROM chain_checkpoints ORDER BY sequence_id DESC LIMIT 1")
        )
        latest_chk = chk_res.first()
    except Exception:
        latest_chk = None

    # Fetch current chain tail sequence
    tail_seq = 0
    try:
        state_res = await session.execute(
            text("SELECT tail_sequence_id FROM chain_state WHERE id = 1")
        )
        state_row = state_res.first()
        if state_row and state_row[0] is not None:
            try:
                tail_seq = int(state_row[0])
            except (ValueError, TypeError):
                tail_seq = 0
        else:
            max_res = await session.execute(text("SELECT COALESCE(MAX(sequence_id), 0) FROM audit_log"))
            max_row = max_res.first()
            if max_row and max_row[0] is not None:
                try:
                    tail_seq = int(max_row[0])
                except (ValueError, TypeError):
                    tail_seq = 0
    except Exception:
        tail_seq = 0

    if not latest_chk:
        return AnchorInfo(
            status="MISSING",
            anchor_store=store_type,
            anchor_location=location,
            last_anchored=None,
            anchor_hash="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            entries_since_anchor=tail_seq,
        )


    try:
        chk_id = int(latest_chk[0]) if latest_chk[0] is not None else 0
        chk_seq = int(latest_chk[1]) if latest_chk[1] is not None else 0
        chk_hash = str(latest_chk[2]) if latest_chk[2] is not None else ""
        raw_time = latest_chk[3]
        chk_key_id = latest_chk[4] if len(latest_chk) > 4 else None
        if isinstance(raw_time, str):
            try:
                chk_time = datetime.fromisoformat(raw_time)
            except Exception:
                chk_time = datetime.now(timezone.utc)
        elif isinstance(raw_time, datetime):
            chk_time = raw_time
        else:
            chk_time = datetime.now(timezone.utc)
    except Exception:
        chk_id = 0
        chk_seq = 0
        chk_hash = "0000000000000000000000000000000000000000000000000000000000000000"
        chk_time = datetime.now(timezone.utc)
        chk_key_id = None

    delta = max(0, tail_seq - chk_seq)
    if store_type == "none":
        return AnchorInfo(
            status="MISSING", anchor_store=store_type, anchor_location=location,
            last_anchored=None,
            anchor_hash=f"sha256:{chk_hash}" if not chk_hash.startswith("sha256:") else chk_hash,
            entries_since_anchor=tail_seq,
            witness_report=WitnessReport(
                quorum_satisfied=False, verification_status="unknown",
                message="External anchoring is not configured. Signed checkpoints are stored in PostgreSQL; no independent witness is available.",
                deployment_mode="not_configured", independent_trust_domains=False,
            ),
        )
    status_str = "MISSING"
    anchor_record_time: datetime | None = None

    # Check external anchor store if available
    # ANCHOR_FILE_PATH is the configured store base path. LocalFileAnchorStore
    # treats it as a directory; deployments historically configured a filename
    # (for example chain_anchor.log), so use its parent in that case.
    configured_anchor_path = Path(settings.ANCHOR_FILE_PATH)
    anchor_dir = (
        configured_anchor_path.parent
        if configured_anchor_path.suffix
        else configured_anchor_path
    )
    if store_type == "local_file" and anchor_dir.exists():
        anchor_path = anchor_dir / f"{chk_id}.json"
        try:
            anchor_data = json.loads(anchor_path.read_text(encoding="utf-8"))
            if (
                anchor_data.get("checkpoint_id") != chk_id
                or anchor_data.get("sequence_id") != chk_seq
                or anchor_data.get("checkpoint_hash") != chk_hash
            ):
                status_str = "MISMATCH"
            else:
                status_str = (
                    "STALE"
                    if delta > settings.CHECKPOINT_INTERVAL * 2
                    else "ANCHORED"
                )
                raw_anchor_time = anchor_data.get("anchored_at")
                if isinstance(raw_anchor_time, str):
                    try:
                        anchor_record_time = datetime.fromisoformat(
                            raw_anchor_time.replace("Z", "+00:00")
                        )
                    except ValueError:
                        anchor_record_time = None
        except (OSError, json.JSONDecodeError, TypeError):
            status_str = "MISSING"
    elif store_type != "local_file":
        status_str = "UNVERIFIED"
    # Multi-witness quorum telemetry (NOVEL-010)
    witness_report = None
    try:
        from db.cli.anchor_store import MultiWitnessAnchorStore
        from db.cli.witness_config import load_public_keys, resolve_witness_store_path
        witness_path = resolve_witness_store_path(
            settings.ANCHOR_FILE_PATH, settings.WITNESS_STORE_PATH
        )
        note_file = witness_path / f"{chk_id}.note"
        if latest_chk and note_file.is_file():
            cid = chk_id
            trusted_witness_keys = load_public_keys(settings.WITNESS_PUBLIC_KEYS_DIR)
            origin_key_path = _checkpoint_public_key_path(
                chk_key_id, Path(settings.CHECKPOINT_PUBLIC_KEYS_DIR)
            )
            origin_key = (
                origin_key_path.read_text(encoding="utf-8")
                if origin_key_path.is_file()
                else None
            )
            mw = MultiWitnessAnchorStore(
                base_path=str(witness_path),
                witness_public_keys=trusted_witness_keys,
                origin_public_key_pem=origin_key,
            )
            rep_data = mw.get_witness_report(cid)
            missing_trust_keys = (
                "Missing public key" in str(rep_data.get("message", ""))
                or any(
                    item.get("reason") == "Missing public key"
                    for item in rep_data.get("per_witness", [])
                )
            )
            report_status = (
                "unknown" if rep_data.get("error") or missing_trust_keys else
                "pass" if rep_data.get("quorum_satisfied") is True else "fail"
            )
            witness_report = WitnessReport(
                quorum_satisfied=rep_data.get("quorum_satisfied") is True,
                required_threshold=rep_data.get("required_threshold", 2),
                total_witnesses=rep_data.get("total_witnesses", 0),
                cosigned_witnesses=rep_data.get("cosigned_witnesses", 0),
                per_witness=[WitnessItem(**w) for w in rep_data.get("per_witness", [])],
                verification_status=report_status,
                message=rep_data.get("message") or rep_data.get("error"),
                deployment_mode="in_process_reference",
                independent_trust_domains=False,
            )
        else:
            witness_report = WitnessReport(
                quorum_satisfied=False,
                required_threshold=2,
                total_witnesses=0,
                cosigned_witnesses=0,
                message="No persisted witness note is available for this checkpoint.",
                verification_status="unknown",
                deployment_mode="in_process_reference",
                independent_trust_domains=False,
            )
    except Exception:
        witness_report = WitnessReport(
            quorum_satisfied=False,
            message="Witness status could not be verified.",
            verification_status="unknown",
        )

    return AnchorInfo(
        status=status_str,
        anchor_store=store_type,
        anchor_location=location,
        last_anchored=(
            anchor_record_time
            if status_str in ("ANCHORED", "STALE")
            else chk_time
        ),
        anchor_hash=f"sha256:{chk_hash}" if not chk_hash.startswith("sha256:") else chk_hash,
        entries_since_anchor=delta,
        witness_report=witness_report,
    )


@router.get(
    "/analytics/system-metrics",
    response_model=SystemMetricsResponse,
    dependencies=_auditor_only,
)
async def get_system_metrics(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, scope="function"),
):
    """Retrieve live PostgreSQL performance statistics and security posture metrics."""
    # 1. Cache hit rate from pg_stat_database
    try:
        hit_res = await session.execute(
            text("SELECT round(100.0 * sum(blks_hit) / nullif(sum(blks_hit + blks_read), 0), 1) FROM pg_stat_database WHERE datname = current_database()")
        )
        hit_val = hit_res.scalar()
        cache_hit_rate = float(hit_val) if hit_val is not None else 100.0
    except Exception:
        cache_hit_rate = 99.0

    # 2. Database size & relation size
    try:
        sz_res = await session.execute(
            text("SELECT pg_size_pretty(pg_database_size(current_database())), pg_size_pretty(pg_total_relation_size('audit_log'))")
        )
        sz_row = sz_res.first()
        db_size = str(sz_row[0]) if sz_row and sz_row[0] else "0 MB"
        audit_log_size = str(sz_row[1]) if sz_row and sz_row[1] else "0 kB"
    except Exception:
        db_size = "N/A"
        audit_log_size = "N/A"

    # 3. Total audit log entries & checkpoints
    try:
        cnt_res = await session.execute(text("SELECT count(*) FROM audit_log"))
        total_audit_entries = int(cnt_res.scalar() or 0)
    except Exception:
        total_audit_entries = 0

    try:
        chk_cnt_res = await session.execute(text("SELECT count(*) FROM chain_checkpoints"))
        total_checkpoints = int(chk_cnt_res.scalar() or 0)
    except Exception:
        total_checkpoints = 0

    # 4. Table statistics from pg_stat_user_tables
    table_stats = []
    try:
        t_res = await session.execute(
            text("""
                SELECT relname, coalesce(seq_scan, 0), coalesce(idx_scan, 0), coalesce(n_tup_ins, 0), coalesce(n_tup_upd, 0)
                FROM pg_stat_user_tables
                WHERE relname IN ('audit_log', 'employees', 'salary_history', 'chain_checkpoints')
                ORDER BY n_tup_ins DESC
            """)
        )
        for r in t_res.all():
            table_stats.append(
                TableStatItem(
                    table_name=r[0],
                    seq_scans=int(r[1]),
                    idx_scans=int(r[2]),
                    inserts=int(r[3]),
                    updates=int(r[4]),
                )
            )
    except Exception:
        table_stats = []

    # 5. Security posture checks: exceptions and NULL results remain UNKNOWN.
    check_results: dict[str, Optional[bool]] = {}

    async def evaluate_check(name: str, statement: str) -> None:
        try:
            async with session.begin_nested():
                result = await session.execute(text(statement))
                value = result.scalar()
            check_results[name] = None if value is None else bool(value)
        except Exception:
            check_results[name] = None

    await evaluate_check(
        "pgcrypto_active",
        "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pgcrypto')",
    )
    await evaluate_check(
        "role_isolation",
        """SELECT NOT (
               has_table_privilege('hr_admin', 'audit_log', 'INSERT') OR
               has_table_privilege('hr_admin', 'audit_log', 'UPDATE') OR
               has_table_privilege('hr_admin', 'audit_log', 'DELETE') OR
               has_table_privilege('hr_admin', 'audit_log', 'TRUNCATE')
           )""",
    )
    await evaluate_check(
        "chain_continuous",
        """SELECT CASE
             WHEN latest.entry_hash IS NULL THEN state.tail_hash = repeat('0', 64)
             ELSE state.tail_hash = latest.entry_hash
           END
           FROM chain_state AS state
           LEFT JOIN LATERAL (
               SELECT entry_hash FROM audit_log ORDER BY sequence_id DESC LIMIT 1
           ) AS latest ON TRUE
           WHERE state.id = 1""",
    )

    # Include the same end-to-end verifier result shown on the integrity page.
    # A matching tail alone is not sufficient evidence that checkpoints verify.
    verification = await run_verification(current_user, session)
    for check_name in ("hash_chain", "external_anchor", "checkpoint_signatures"):
        state = verification.verification_checks.get(check_name, "unknown")
        check_results[f"verified_{check_name}"] = (
            True if state == "pass" else False if state == "fail" else None
        )

    # The security grade must include independent witness status. A quorum
    # produced by the in-process reference implementation is not an independent
    # trust domain and cannot count as a production security pass.
    anchor_info = await get_anchor_status(current_user, session)
    witness_report = anchor_info.witness_report
    if witness_report is None or witness_report.verification_status == "unknown":
        check_results["independent_witness_quorum"] = None
    elif witness_report.verification_status == "fail":
        check_results["independent_witness_quorum"] = False
    else:
        check_results["independent_witness_quorum"] = (
            True if witness_report.independent_trust_domains else None
        )

    settings = get_settings()
    check_results["auth_enforced"] = bool(settings.SUPABASE_URL and settings.SUPABASE_PUBLISHABLE_KEY)
    security_checks = {name: result is True for name, result in check_results.items()}
    security_check_details = {
        name: ("pass" if result is True else "fail" if result is False else "unknown")
        for name, result in check_results.items()
    }
    score = round(100 * sum(security_checks.values()) / len(security_checks))

    return SystemMetricsResponse(
        security_score=score,
        security_checks=security_checks,
        security_check_details=security_check_details,
        cache_hit_rate=cache_hit_rate,
        db_size=db_size,
        audit_log_size=audit_log_size,
        total_audit_entries=total_audit_entries,
        total_checkpoints=total_checkpoints,
        table_stats=table_stats,
    )


@router.post(
    "/suspicious-activity/{flag_id}/reopen",
    dependencies=_auditor_only,
)
async def reopen_suspicious_flag(
    flag_id: int,
    payload: Optional[SuspiciousReviewRequest] = Body(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, scope="function"),
):
    """Reopen a previously reviewed flag and retain the earlier decision."""
    result = await session.execute(
        select(SuspiciousActivityFlag).where(SuspiciousActivityFlag.flag_id == flag_id)
    )
    flag = result.scalar_one_or_none()
    if flag is None:
        raise HTTPException(status_code=404, detail=f"Suspicious activity flag {flag_id} not found.")
    if flag.reviewed_at is None:
        raise HTTPException(status_code=409, detail="This suspicious activity flag is already open.")

    flag.reviewed_by_user_id = None
    flag.reviewed_at = None
    session.add(
        SuspiciousActivityReview(
            flag_id=flag.flag_id,
            reviewer_user_id=current_user.user_id,
            action="reopened",
            note=payload.note if payload else None,
        )
    )
    await session.flush()
    return {"flag_id": flag_id, "status": "open"}


@router.get(
    "/suspicious-activity/{flag_id}/reviews",
    response_model=List[SuspiciousReviewHistoryItem],
    dependencies=_auditor_only,
)
async def list_suspicious_flag_reviews(
    flag_id: int,
    session: AsyncSession = Depends(get_db_session, scope="function"),
):
    """Return immutable review and reopen history for a risk flag."""
    result = await session.execute(
        select(SuspiciousActivityReview)
        .where(SuspiciousActivityReview.flag_id == flag_id)
        .order_by(SuspiciousActivityReview.created_at, SuspiciousActivityReview.review_id)
    )
    return result.scalars().all()


@router.post(
    "/analytics/diagnostics/concurrency-benchmark",
    response_model=ConcurrencyRunResponse,
    dependencies=_auditor_only,
)
async def run_concurrency_test(
    body: Optional[ConcurrencyRunRequest] = None,
    workers: Optional[int] = Query(None, ge=1, le=50),
):
    """Run parallel, isolated read-only chain-window checks against PostgreSQL."""
    if get_settings().APP_ENV != "development" or not get_settings().ALLOW_CONCURRENCY_DIAGNOSTICS:
        raise HTTPException(status_code=403, detail="Concurrency diagnostics are disabled.")
    import asyncio
    import time
    import uuid

    target_workers = 5
    if body is not None and body.workers:
        target_workers = body.workers
    elif workers is not None:
        target_workers = workers

    start_time = time.perf_counter()
    logs: list[ConcurrencyLogItem] = []

    session_factory = get_session_factory("compliance_auditor")

    async def _worker_task(worker_id: int):
        w_start = time.perf_counter()
        tx_id = f"tx-{uuid.uuid4().hex[:6]}"
        try:
            async with session_factory() as worker_session:
                res = await worker_session.execute(text("""
                    WITH recent AS (
                        SELECT sequence_id, entry_hash, previous_hash
                        FROM audit_log
                        ORDER BY sequence_id DESC
                        LIMIT 1000
                    ), ordered AS (
                        SELECT sequence_id, entry_hash, previous_hash,
                               lag(entry_hash) OVER (ORDER BY sequence_id) AS prior_hash
                        FROM recent
                    )
                    SELECT COALESCE(MAX(sequence_id), 0), COUNT(*),
                           COALESCE(bool_and(previous_hash = prior_hash)
                               FILTER (WHERE prior_hash IS NOT NULL), TRUE)
                    FROM ordered
                """))
                row = res.one()
            seq_id = int(row[0] or 0)
            inspected = int(row[1] or 0)
            intact = bool(row[2]) and inspected >= 2
            w_latency = (time.perf_counter() - w_start) * 1000.0
            return ConcurrencyLogItem(
                tx_id=tx_id,
                worker_id=worker_id,
                action=(
                    f"Verified {inspected - 1} adjacent hash links"
                    if intact
                    else "Insufficient rows to verify continuity"
                    if inspected < 2
                    else "Detected a broken adjacent hash link"
                ),
                status="success" if intact else "error",
                sequence_id=seq_id,
                latency_ms=round(w_latency, 2),
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as exc:
            w_latency = (time.perf_counter() - w_start) * 1000.0
            logger.warning("Concurrent verification worker failed (%s)", type(exc).__name__)
            return ConcurrencyLogItem(
                tx_id=tx_id,
                worker_id=worker_id,
                action=f"Lock contention or verification error ({type(exc).__name__})",
                status="error",
                sequence_id=None,
                latency_ms=round(w_latency, 2),
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

    tasks = [_worker_task(i + 1) for i in range(target_workers)]
    worker_logs = await asyncio.gather(*tasks)
    logs.extend(worker_logs)

    total_time_ms = (time.perf_counter() - start_time) * 1000.0
    successes = sum(1 for l in logs if l.status == "success")
    failures = sum(1 for l in logs if l.status == "error")

    return ConcurrencyRunResponse(
        workers=target_workers,
        total_time_ms=round(total_time_ms, 2),
        success_count=successes,
        failed_count=failures,
        logs=logs,
    )


# ─── POST /api/audit-logs/counterfactual ──────────────────────────────────────

@router.post(
    "/audit-logs/counterfactual",
    response_model=CounterfactualResponse,
    dependencies=_auditor_only,
)
async def run_counterfactual_simulation(
    payload: CounterfactualRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, scope="function"),
):
    """Run in-memory counterfactual 'What-If' replay simulation (NOVEL-011).

    Accessible to compliance_auditor only.
    Replays the employee's mutation history skipping designated sequence IDs,
    quantifies the blast radius (salary overpaid annual and cumulative), and returns
    side-by-side state comparison without modifying the database.
    """
    if not payload.skip_sequence_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="skip_sequence_ids must contain at least one sequence ID.",
        )

    # Parse optional as_of timestamp
    as_of_dt = None
    if payload.as_of:
        clean_ts = payload.as_of.strip()
        if " " in clean_ts and "+" not in clean_ts:
            clean_ts = clean_ts.replace(" ", "+")
        if clean_ts.endswith("Z") or clean_ts.endswith("z"):
            clean_ts = clean_ts[:-1] + "+00:00"
        try:
            as_of_dt = datetime.fromisoformat(clean_ts)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Invalid ISO timestamp format for as_of: '{payload.as_of}'.",
            )
        if as_of_dt.tzinfo is None:
            as_of_dt = as_of_dt.replace(tzinfo=timezone.utc)

    # Validate that employee exists
    try:
        emp_res = await session.execute(
            select(Employee.employee_id).where(Employee.employee_id == payload.employee_id)
        )
        if emp_res.scalar() is None:
            # Check if historical employee records exist in audit_log
            audit_res = await session.execute(
                text("SELECT 1 FROM audit_log WHERE employee_id = :emp_id OR (table_name = 'employees' AND row_id = :emp_id) LIMIT 1"),
                {"emp_id": payload.employee_id}
            )
            if audit_res.scalar() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Employee #{payload.employee_id} not found in database or audit trail.",
                )
    except HTTPException:
        raise
    except Exception:
        # If DB query fails or mock session doesn't support complex models, proceed to verifier execution
        pass

    db_url = _compliance_sync_db_url()

    def _execute():
        import psycopg2
        from db.cli.counterfactual import counterfactual_replay
        conn = psycopg2.connect(db_url, connect_timeout=5, options=_sync_timeout_options())
        try:
            return counterfactual_replay(
                conn,
                employee_id=payload.employee_id,
                skip_sequence_ids=payload.skip_sequence_ids,
                as_of=as_of_dt,
            )
        finally:
            conn.close()

    try:
        sim_result = await asyncio.to_thread(_execute)
        return sim_result.to_dict()
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(ve),
        )
    except Exception as exc:
        logger.exception("Counterfactual simulation failed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Counterfactual simulation could not be completed.",
        )


# ─── GET /api/audit-logs/{seq_id}/capsule ─────────────────────────────────────

@router.get(
    "/audit-logs/{seq_id}/capsule",
    dependencies=_auditor_only,
)
async def export_audit_log_capsule(
    seq_id: int,
    current_user: User = Depends(get_current_user),
):
    """Generate and stream a self-contained .arguscap Merkle evidence bundle (NOVEL-009-F).

    Contains evidence_row.json, merkle_proof.json, checkpoint.json, public_key.pem,
    and verify_capsule.py standalone CLI verifier.
    Accessible to compliance_auditor only.
    """
    from db.cli.capsule import (
        PreMerkleCheckpointError,
        RetrospectiveAttestationError,
        SequenceNotFoundError,
        UncheckpointedTailError,
    )

    try:
        bundle_bytes = await _generate_capsule_with_legacy_attestation(seq_id)
        return Response(
            content=bundle_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="proof_seq{seq_id}.arguscap"',
                "X-Argus-Capsule-Version": "1.0",
            },
        )
    except SequenceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PreMerkleCheckpointError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RetrospectiveAttestationError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except UncheckpointedTailError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Audit capsule generation failed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Audit capsule generation could not be completed.",
        )


# ─── GET /api/audit-logs/{seq_id}/proof ───────────────────────────────────────

@router.get(
    "/audit-logs/{seq_id}/proof",
    response_model=MerkleProofResponse,
    dependencies=_auditor_only,
)
async def get_merkle_proof(
    seq_id: int,
    current_user: User = Depends(get_current_user),
):
    """Retrieve Merkle inclusion proof metadata for an audit event (NOVEL-009).

    Returns the cryptographic audit path, leaf hash, and enclosing checkpoint Merkle root.
    Accessible to compliance_auditor only.
    """
    from db.cli.capsule import PreMerkleCheckpointError, RetrospectiveAttestationError, SequenceNotFoundError, UncheckpointedTailError

    try:
        bundle = await _generate_capsule_with_legacy_attestation(seq_id)
        import io
        import zipfile

        with zipfile.ZipFile(io.BytesIO(bundle), "r") as archive:
            proof = json.loads(archive.read("merkle_proof.json"))
            checkpoint = json.loads(archive.read("checkpoint.json"))
            retrospective = "retrospective_attestation.json" in archive.namelist()
            attestation = (
                json.loads(archive.read("retrospective_attestation.json"))
                if retrospective
                else None
            )
            evidence = json.loads(archive.read("evidence_row.json"))

        return {
            "sequence_id": seq_id,
            "checkpoint_id": checkpoint["checkpoint_id"],
            "leaf_index": proof["leaf_index"],
            "leaf_hash": proof["leaf_hash"],
            "merkle_root": proof["merkle_root"],
            "tree_size": proof["tree_size"],
            "audit_path_depth": len(proof["audit_path"]),
            "audit_path": proof["audit_path"],
            "created_at": evidence.get("created_at"),
            "retrospective": retrospective,
            "retrospective_attested_at": (
                attestation["payload"].get("issued_at") if attestation else None
            ),
        }
    except SequenceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PreMerkleCheckpointError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RetrospectiveAttestationError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except UncheckpointedTailError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Merkle proof generation failed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Merkle proof generation could not be completed.",
        )



