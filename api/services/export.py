import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.audit_log import AuditLog
from ..models.user import User
from ..config import get_settings

try:
    from db.cli.signer import sign_checkpoint
    from db.cli.keygen import (
        load_private_key,
        generate_keypair,
        save_keypair,
        get_default_key_dir,
    )
except ImportError:
    from ...db.cli.signer import sign_checkpoint  # type: ignore[no-redef]
    from ...db.cli.keygen import (  # type: ignore[no-redef]
        load_private_key,
        generate_keypair,
        save_keypair,
        get_default_key_dir,
    )


def get_or_create_signing_key():
    """Resolve or generate an Ed25519 signing keypair for audit evidence export."""
    settings = get_settings()
    configured_path = Path(settings.SIGNING_PRIVATE_KEY_PATH)
    default_path = Path(get_default_key_dir()) / "signing_key.pem"

    for candidate in [configured_path, default_path]:
        if candidate.is_file():
            try:
                return load_private_key(str(candidate))
            except Exception:
                pass

    # If key doesn't exist, generate and save in default key directory
    priv_pem, pub_pem = generate_keypair()
    target_dir = configured_path.parent if configured_path.parent.exists() else get_default_key_dir()
    priv_path, _ = save_keypair(priv_pem, pub_pem, str(target_dir))
    return load_private_key(priv_path)


async def generate_signed_evidence_export(session: AsyncSession) -> dict:
    """
    Fetch all audit logs and generate an Ed25519 signed JSON export.
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
    
    # Compute canonical SHA-256 hash of payload
    payload_canonical = json.dumps(export_payload, sort_keys=True, separators=(",", ":"))
    payload_hash = hashlib.sha256(payload_canonical.encode("utf-8")).hexdigest()

    # Cryptographic Ed25519 signature
    private_key = get_or_create_signing_key()
    signature_bytes = sign_checkpoint(private_key, payload_hash)
    
    return {
        "metadata": {
            "version": "1.0",
            "signature_algorithm": "Ed25519",
            "signature": signature_bytes.hex(),
            "payload_hash": payload_hash,
        },
        "data": export_payload
    }

