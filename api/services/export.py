import json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.audit_log import AuditLog
from ..models.user import User

async def generate_signed_evidence_export(session: AsyncSession) -> dict:
    """
    Fetch all audit logs and generate a signed JSON export.
    
    TODO (PENDING_ABHINAV): The cryptographic signing logic relies on Abhinav's 
    checkpoint signing utility (Week 6). Currently mocked.
    """
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
        .outerjoin(User, AuditLog.actor_user_id == User.user_id)
        .order_by(AuditLog.sequence_id.asc())
    )
    
    result = await session.execute(query)
    rows = result.all()
    
    logs = []
    for row in rows:
        logs.append({
            "sequence_id": row.sequence_id,
            "actor_name": row.actor_name,
            "employee_id": row.employee_id,
            "action": row.action,
            "table_name": row.table_name,
            "row_id": row.row_id,
            "old_value": row.old_value,
            "new_value": row.new_value,
            "severity": row.severity,
            "entry_hash": row.entry_hash,
            "previous_hash": row.previous_hash,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        })
        
    export_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_entries": len(logs),
        "logs": logs
    }
    
    # MOCK SIGNATURE
    # Replace with subprocess call to Abhinav's signing utility or import it
    mock_signature = "mock_signature_until_abhinav_signing_utility_is_ready"
    
    return {
        "metadata": {
            "version": "1.0",
            "signature_algorithm": "RSA-SHA256 (MOCK)",
            "signature": mock_signature
        },
        "data": export_payload
    }
