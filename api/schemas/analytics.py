from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal


class RecentActivityItem(BaseModel):
    sequence_id: int
    action: str
    table_name: str
    actor_name: str
    severity: str
    created_at: datetime


class DashboardStatsResponse(BaseModel):
    total_employees: int
    active_employees: int = 0
    total_audit_events: int
    unreviewed_flags: int
    recent_activity: List[RecentActivityItem]


class DepartmentItem(BaseModel):
    department_id: int
    name: str


class RoleItem(BaseModel):
    role_id: int
    title: str
    department_id: int
    department_name: Optional[str] = None
    salary_band_min: Decimal
    salary_band_max: Decimal
    min_salary: Optional[Decimal] = None
    max_salary: Optional[Decimal] = None


class TableStatItem(BaseModel):
    table_name: str
    seq_scans: int
    idx_scans: int
    inserts: int
    updates: int


class SystemMetricsResponse(BaseModel):
    security_score: int
    security_checks: Dict[str, bool]
    cache_hit_rate: float
    db_size: str
    audit_log_size: str
    total_audit_entries: int
    total_checkpoints: int
    table_stats: List[TableStatItem]


class ConcurrencyLogItem(BaseModel):
    tx_id: str
    worker_id: int
    action: str
    status: str
    sequence_id: Optional[int] = None
    latency_ms: float
    timestamp: str


class ConcurrencyRunRequest(BaseModel):
    workers: int = 5


class ConcurrencyRunResponse(BaseModel):
    workers: int
    total_time_ms: float
    success_count: int
    failed_count: int
    logs: List[ConcurrencyLogItem]
