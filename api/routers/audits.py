"""Audit Log and Verification endpoints.

Implements:
- GET  /api/audit-logs              — Paginated audit log (compliance_auditor only)
- POST /api/verify                  — Invoke chain verifier (compliance_auditor only)
- GET  /api/suspicious-activity     — List flags (compliance_auditor only)
- POST /api/suspicious-activity/{id}/review — Mark flag reviewed (compliance_auditor only)

GET /api/audit-logs queries the real audit_log table joined with users.
The table will be empty until Abhinav's Week 3 triggers land — that is expected.

POST /api/verify returns a structured mock matching the contract shape.
TODO Week 6-7: Replace the mock body with a subprocess call to Abhinav's
               verifier CLI once it is committed to db/verifier/.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_current_user, require_role, get_db_session
from ..models.audit_log import AuditLog
from ..models.suspicious_activity_flag import SuspiciousActivityFlag
from ..models.user import User
from ..schemas.audit import (
    AuditLogItem,
    VerificationResult,
    SuspiciousFlagItem,
    SuspiciousReviewResponse,
)
from ..schemas.common import PaginatedResponse
import math

router = APIRouter(tags=["Audits"])

# ─── Dependency: compliance_auditor only ──────────────────────────────────────

_auditor_only = [Depends(require_role(["compliance_auditor"]))]


# ─── GET /api/audit-logs ──────────────────────────────────────────────────────

@router.get(
    "/audit-logs",
    response_model=PaginatedResponse[AuditLogItem],
    dependencies=_auditor_only,
)
async def list_audit_logs(
    actor_id: Optional[int] = Query(None, description="Filter by actor user_id"),
    action: Optional[str] = Query(None, description="INSERT | UPDATE | DELETE"),
    table_name: Optional[str] = Query(None, description="Filter by table name"),
    severity: Optional[str] = Query(None, description="INFO | WARNING | CRITICAL"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Retrieve paginated audit log entries with optional filters.

    Joins audit_log → users to resolve actor_name.
    Accessible to compliance_auditor role only — enforced both by the
    require_role dependency and by the compliance_auditor Postgres pool
    which has SELECT-only access to audit_log.
    """
    # Build base query joining to users for actor_name
    actor_alias = User
    query = (
        select(
            AuditLog.sequence_id,
            User.full_name.label("actor_name"),
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
        .join(User, AuditLog.actor_user_id == User.user_id)
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

    # Count total matching rows
    count_q = select(func.count()).select_from(query.subquery())
    total = await session.scalar(count_q) or 0
    pages = math.ceil(total / limit) if total > 0 else 0

    # Paginate — newest entries first
    query = (
        query
        .order_by(AuditLog.sequence_id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    result = await session.execute(query)
    rows = result.all()

    items = [
        AuditLogItem(
            sequence_id=row.sequence_id,
            actor_name=row.actor_name,
            employee_id=row.employee_id,
            action=row.action,
            table_name=row.table_name,
            row_id=row.row_id,
            old_value=row.old_value,
            new_value=row.new_value,
            severity=row.severity,
            entry_hash=row.entry_hash,
            previous_hash=row.previous_hash,
            created_at=row.created_at,
        )
        for row in rows
    ]

    return PaginatedResponse(items=items, total=total, page=page, pages=pages)


# ─── POST /api/verify ─────────────────────────────────────────────────────────

@router.post(
    "/verify",
    response_model=VerificationResult,
    dependencies=_auditor_only,
)
async def run_verification(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Trigger the standalone verifier to scan the hash chain.

    Accessible to compliance_auditor only.

    TODO Week 6-7: Replace this mock body with a real subprocess call:

        import asyncio, json
        proc = await asyncio.create_subprocess_exec(
            "python", "-m", "db.verifier.cli", "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        raw = json.loads(stdout)
        return VerificationResult(**raw)

    The verifier CLI lives in db/verifier/ (Abhinav's track, Week 5-6).
    Until then, return the structured mock below so the frontend contract
    is exercised end-to-end.
    """
    # Count current audit log entries for the mock response
    total_entries = await session.scalar(select(func.count(AuditLog.sequence_id))) or 0
    last_id_row = await session.scalar(
        select(AuditLog.sequence_id).order_by(AuditLog.sequence_id.desc()).limit(1)
    )
    last_id = last_id_row or 0

    # --- MOCK RESPONSE (replace with subprocess call above in Week 6-7) ---
    return VerificationResult(
        status="intact",
        entries_scanned=total_entries,
        anchor_match=True,
        last_verified_sequence_id=last_id,
        tampered_sequence_id=None,
        details=(
            f"Chain walks successfully across {total_entries} entries. "
            "Tail hash matches external anchor store. "
            "[MOCK — real verifier CLI pending Abhinav's Week 6 commit]"
        ),
    )


# ─── GET /api/suspicious-activity ────────────────────────────────────────────

@router.get(
    "/suspicious-activity",
    response_model=list[SuspiciousFlagItem],
    dependencies=_auditor_only,
)
async def list_suspicious_flags(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """List all suspicious activity flags, newest first.

    Populated by Abhinav's Week 8 refresh_suspicious_activity_flags()
    procedure. Returns empty list until then.
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


# ─── POST /api/suspicious-activity/{id}/review ───────────────────────────────

@router.post(
    "/suspicious-activity/{flag_id}/review",
    response_model=SuspiciousReviewResponse,
    dependencies=_auditor_only,
)
async def review_suspicious_flag(
    flag_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
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
    await session.flush()

    return SuspiciousReviewResponse(
        flag_id=flag.flag_id,
        reviewed_by_user_id=current_user.user_id,
        reviewed_at=now,
    )


# ─── GET /api/employees/{employee_id}/time-travel ────────────────────────────

from ..schemas.audit import TimeTravelResponse

@router.get(
    "/employees/{employee_id}/time-travel",
    response_model=TimeTravelResponse,
    dependencies=_auditor_only,
)
async def reconstruct_employee_state(
    employee_id: int,
    timestamp: datetime = Query(..., description="Target ISO timestamp"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Reconstruct an employee's record state at a specific past timestamp.
    
    Accessible to compliance_auditor only.
    
    TODO (PENDING_ABHINAV): Once Abhinav pushes the DB function (Week 8),
    replace this mock with a real query:
    SELECT * FROM reconstruct_employee_state(:emp_id, :ts);
    """
    
    # Check if the employee actually exists today just to validate the ID
    from ..models.employee import Employee
    result = await session.execute(select(Employee).where(Employee.employee_id == employee_id))
    emp = result.scalar_one_or_none()
    
    if emp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee {employee_id} not found."
        )
    
    # MOCK RESPONSE
    return TimeTravelResponse(
        employee_id=employee_id,
        full_name=emp.full_name,
        email=emp.email,
        role_title="Software Engineer",  # Mocked
        department_name="Engineering",  # Mocked
        salary=95000.00,  # Mocked
        date_hired=emp.date_hired,
        is_active=emp.is_active,
        as_of=timestamp
    )


# ─── GET /api/audit-logs/export ───────────────────────────────────────────────

from fastapi.responses import StreamingResponse
import io
import json
from ..services.export import generate_signed_evidence_export

@router.get(
    "/audit-logs/export",
    dependencies=_auditor_only,
)
async def export_signed_evidence(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
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
