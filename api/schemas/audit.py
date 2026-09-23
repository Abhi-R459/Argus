"""Pydantic v2 schemas for Audit Log, Verification, and Suspicious Activity endpoints.

Shapes mirror contracts/api_contract.md §4 and §6 exactly.
"""

from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from datetime import datetime


# ─── Audit Log ────────────────────────────────────────────────────────────────

class AuditLogItem(BaseModel):
    """One row from GET /api/audit-logs.

    actor_name is resolved by joining audit_log → users.
    old_value / new_value are nullable JSONB payloads.
    """

    sequence_id: int
    actor_name: str
    employee_id: Optional[int]
    action: str          # INSERT | UPDATE | DELETE
    table_name: str
    row_id: int
    old_value: Optional[Dict[str, Any]]
    new_value: Optional[Dict[str, Any]]
    severity: str        # INFO | WARNING | CRITICAL
    entry_hash: str
    previous_hash: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Verification ──────────────────────────────────────────────────────────────

class VerificationResult(BaseModel):
    """Response from POST /api/verify.

    Mirrors both the 'intact' and 'tampered' shapes from the contract.
    """

    status: str                         # "intact" | "tampered"
    entries_scanned: int
    anchor_match: bool
    last_verified_sequence_id: int
    tampered_sequence_id: Optional[int]
    details: str


# ─── Suspicious Activity ───────────────────────────────────────────────────────

class SuspiciousFlagItem(BaseModel):
    """One row from GET /api/suspicious-activity."""

    flag_id: int
    audit_log_sequence_id: int
    flag_reason: str
    reviewed_by: Optional[int]          # reviewed_by_user_id
    reviewed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class SuspiciousReviewResponse(BaseModel):
    """Response from POST /api/suspicious-activity/{id}/review."""

    flag_id: int
    reviewed_by_user_id: int
    reviewed_at: datetime


# ─── Time-Travel ───────────────────────────────────────────────────────────────

class TimeTravelResponse(BaseModel):
    """Response from GET /api/employees/{id}/time-travel."""

    employee_id: int
    full_name: str
    email: str
    role_title: str
    department_name: str
    salary: float
    date_hired: datetime
    is_active: bool
    as_of: datetime
    sequence_id: Optional[int] = None


# ─── Live Chain & Anchor Status ───────────────────────────────────────────────

class ChainEntry(BaseModel):
    """One block/node from GET /api/audit-logs/chain."""

    entry_id: int
    hash: str
    prev_hash: Optional[str] = None
    table_name: str
    operation: str                      # INSERT | UPDATE | DELETE
    actor_email: str
    actor_role: str
    timestamp: datetime
    severity: str                       # low | medium | high | critical
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class AnchorInfo(BaseModel):
    """Response from GET /api/anchor/status."""

    status: str                         # ANCHORED | STALE | MISSING
    anchor_store: str                   # local_file | github_repo
    anchor_location: str
    last_anchored: datetime
    anchor_hash: str
    entries_since_anchor: int

    model_config = {"from_attributes": True}
