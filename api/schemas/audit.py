"""Pydantic v2 schemas for Audit Log, Verification, and Suspicious Activity endpoints.

Shapes mirror contracts/api_contract.md §4 and §6 exactly.
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional
from datetime import datetime


# ─── Audit Log ────────────────────────────────────────────────────────────────

class AuditLogSearchRequest(BaseModel):
    """Keep the national identifier and associated search filters out of URLs."""

    national_id_search: str = Field(min_length=1, max_length=255)
    actor_id: Optional[int] = None
    action: Optional[str] = Field(default=None, max_length=255)
    table_name: Optional[str] = Field(default=None, max_length=255)
    severity: Optional[str] = Field(default=None, max_length=255)
    sequence_id: Optional[int] = None
    employee_id: Optional[int] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
    before_sequence_id: Optional[int] = Field(default=None, ge=1)
    include_pii: bool = False

    model_config = {"extra": "forbid", "str_strip_whitespace": True}


class AuditLogItem(BaseModel):
    """One row from GET /api/audit-logs.

    actor_name is resolved by joining audit_log → users.
    old_value / new_value are nullable JSONB payloads.
    """

    sequence_id: int
    actor_user_id: Optional[int]
    actor_name: str
    employee_id: Optional[int]
    action: str          # INSERT | UPDATE | DELETE
    table_name: str
    row_id: int
    old_value: Optional[Dict[str, Any]]
    new_value: Optional[Dict[str, Any]]
    forensic_before_value: Optional[Dict[str, Any]] = None
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

    status: Literal["intact", "tampered", "unknown", "error"]
    entries_scanned: int
    anchor_match: bool
    last_verified_sequence_id: int
    tampered_sequence_id: Optional[int]
    details: str
    verification_checks: Dict[str, Literal["pass", "fail", "unknown"]] = Field(default_factory=dict)
    checkpoint_signature_evidence: Optional[Dict[str, Any]] = None
    deleted_entry_evidence: Optional[Dict[str, Any]] = None


# ─── Suspicious Activity ───────────────────────────────────────────────────────

class SuspiciousFlagItem(BaseModel):
    """One row from GET /api/suspicious-activity."""

    flag_id: int
    audit_log_sequence_id: int
    flag_reason: str
    affected_event_count: int = 1
    reviewed_by: Optional[int]          # reviewed_by_user_id
    reviewed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class SuspiciousReviewResponse(BaseModel):
    """Response from POST /api/suspicious-activity/{id}/review."""

    flag_id: int
    reviewed_by_user_id: int
    reviewed_at: datetime


class SuspiciousReviewRequest(BaseModel):
    """Optional rationale attached to a review decision."""

    note: Optional[str] = Field(default=None, max_length=2000)


class SuspiciousReviewHistoryItem(BaseModel):
    """One immutable decision in a suspicious flag's review history."""

    review_id: int
    flag_id: int
    reviewer_user_id: int
    action: str
    note: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Time-Travel ───────────────────────────────────────────────────────────────

class TimeTravelResponse(BaseModel):
    """Response from GET /api/employees/{id}/time-travel."""

    employee_id: int
    full_name: Optional[str]
    email: Optional[str]
    role_title: str
    department_name: str
    salary: Optional[float]
    date_hired: datetime
    is_active: bool
    as_of: datetime
    sequence_id: Optional[int] = None
    pii_redacted: bool = False


# ─── Live Chain & Anchor Status ───────────────────────────────────────────────

class ChainEntry(BaseModel):
    """One block/node from GET /api/audit-logs/chain."""

    entry_id: int
    hash: str
    prev_hash: Optional[str] = None
    table_name: str
    operation: str                      # INSERT | UPDATE | DELETE
    actor_email: str
    actor_user_id: Optional[int] = None
    actor_role: str
    timestamp: datetime
    severity: str                       # low | medium | high | critical
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    forensic_before_value: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class WitnessItem(BaseModel):
    witness_name: str
    status: str                         # VALID | FAILED | UNKNOWN
    reason: Optional[str] = None
    signature_hex: Optional[str] = None
    timestamp: Optional[str] = None


class WitnessReport(BaseModel):
    quorum_satisfied: bool
    required_threshold: int = 2
    total_witnesses: int = 0
    cosigned_witnesses: int = 0
    message: Optional[str] = None
    per_witness: List[WitnessItem] = Field(default_factory=list)
    verification_status: str = "unknown"
    deployment_mode: str = "in_process_reference"
    independent_trust_domains: bool = False


class AnchorInfo(BaseModel):
    """Response from GET /api/anchor/status."""

    status: str                         # ANCHORED | STALE | MISSING | MISMATCH | UNVERIFIED
    anchor_store: str                   # none | local_file | github_repo
    anchor_location: str
    last_anchored: Optional[datetime] = None
    anchor_hash: str
    entries_since_anchor: int
    witness_report: Optional[WitnessReport] = None

    model_config = {"from_attributes": True}


# ─── Counterfactual Replay ───────────────────────────────────────────────────

class CounterfactualRequest(BaseModel):
    """Request payload for POST /api/audit-logs/counterfactual."""

    employee_id: int = Field(gt=0)
    skip_sequence_ids: List[int] = Field(max_length=100)
    as_of: Optional[str] = None
    include_pii: bool = False


class SkippedEventSchema(BaseModel):
    """Forensic metadata for an excluded audit entry in counterfactual simulation."""

    sequence_id: int
    actor_user_id: int
    action: str
    table_name: str
    created_at: str
    severity: str
    delta_summary: str
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None


class BlastRadiusSchema(BaseModel):
    """Quantified blast radius from skipping designated anomalous transactions."""

    salary_actual: float
    salary_counterfactual: float
    salary_overpaid_annual: float
    salary_overpaid_cumulative: float
    tenure_months: float
    skipped_events_count: int
    skipped_sequence_ids: List[int]
    first_fraud_event_timestamp: Optional[str] = None
    as_of_timestamp: Optional[str] = None


class CounterfactualResponse(BaseModel):
    """Response from POST /api/audit-logs/counterfactual."""

    employee_id: int
    as_of: str
    skip_sequence_ids: List[int]
    actual_state: Optional[Dict[str, Any]] = None
    counterfactual_state: Optional[Dict[str, Any]] = None
    blast_radius: BlastRadiusSchema
    skipped_events: List[SkippedEventSchema]
    applied_events_count: int
    simulation_duration_ms: float


# ─── Merkle Proof & Selective Capsules ───────────────────────────────────────

class MerkleAuditStep(BaseModel):
    level: int
    direction: str
    sibling_hash: str


class MerkleProofResponse(BaseModel):
    """Forensic Merkle inclusion proof metadata for a single audit sequence (NOVEL-009)."""

    sequence_id: int
    checkpoint_id: int
    leaf_index: int
    leaf_hash: str
    merkle_root: str
    tree_size: int
    audit_path_depth: int
    audit_path: List[MerkleAuditStep]
    created_at: Optional[str] = None
    retrospective: bool = False
    retrospective_attested_at: Optional[str] = None

