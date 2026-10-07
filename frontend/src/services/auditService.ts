/**
 * Audit Service — INT-002 / INT-003 / INT-004 / LIVE-001
 *
 * Real API calls for the Compliance Auditor Dashboard, Live HR Dashboard,
 * PostgreSQL engine telemetry, and high-concurrency simulation.
 */

import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import { fetchWithAuth, API_BASE_URL } from '../lib/api';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface AuditChainOptions {
  limit?: number;
  offset?: number;
  around_seq?: number;
  table_name?: string;
  action?: string;
}

export interface IncidentState {
  isCompromised: boolean;
  tamperedSeqId: number | null;
  anchorMismatch: boolean;
  verificationStatus: VerificationResult['status'] | 'checking';
  verificationChecks: Record<string, 'pass' | 'fail' | 'unknown'>;
  unreviewedFlagsCount: number;
  lastVerifiedAt: string | null;
  details: string | null;
  isLoading: boolean;
  isUnavailable: boolean;
  refetch: () => void;
}

export type VerificationStatus = 'VERIFIED' | 'TAMPERED' | 'PENDING';
export type AnchorStoreType = 'local_file' | 'github_repo' | 'multi_witness' | string;
export type AuditOperation = 'INSERT' | 'UPDATE' | 'DELETE';
export type Severity = 'low' | 'medium' | 'high' | 'critical';
export type AuditLogSeverity = 'INFO' | 'WARNING' | 'CRITICAL';

export interface ChainEntry {
  entry_id: number;
  hash: string;
  prev_hash: string | null;
  table_name: string;
  operation: AuditOperation;
  actor_email: string;
  actor_user_id?: number | null;
  actor_role: 'hr_admin' | 'compliance_auditor' | 'system' | 'unknown';
  timestamp: string;           // ISO timestamp
  severity: Severity;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
}

export interface WitnessItem {
  witness_name: string;
  status: 'VALID' | 'FAILED' | 'UNKNOWN' | string;
  reason?: string | null;
  signature_hex?: string | null;
  timestamp?: string | null;
}

export interface WitnessReport {
  quorum_satisfied: boolean;
  required_threshold: number;
  total_witnesses: number;
  cosigned_witnesses: number;
  message?: string | null;
  per_witness: WitnessItem[];
  verification_status?: 'pass' | 'fail' | 'unknown';
  deployment_mode?: string;
  independent_trust_domains?: boolean;
}

export interface AnchorInfo {
  status: 'ANCHORED' | 'STALE' | 'MISSING' | 'MISMATCH' | 'UNVERIFIED';
  anchor_store: AnchorStoreType;
  anchor_location: string;
  last_anchored: string | null; // ISO timestamp only when recorded by the anchor
  anchor_hash: string;
  entries_since_anchor: number;
  witness_report?: WitnessReport | null;
}

export interface SuspiciousFlag {
  flag_id: number;
  employee_id: number;
  employee_name: string;
  reason: string;
  severity: Severity;
  flagged_at: string;
  reviewed: boolean;
}

export interface VerificationBannerResult {
  status: 'VERIFIED' | 'TAMPERED' | 'PENDING';
  last_run: string;
  duration_ms: number;
  checked_entries: number;
  last_checkpoint_id: number;
  last_checkpoint_hash: string;
  error_detail: string | null;
}

export interface DashboardRecentActivity {
  sequence_id: number;
  actor_name: string;
  action: string;
  table_name: string;
  created_at: string;
}

export interface DashboardStats {
  total_employees: number;
  active_employees: number;
  total_audit_events: number;
  unreviewed_flags: number;
  recent_activity: DashboardRecentActivity[];
}

export interface TableStat {
  table_name: string;
  seq_scans: number;
  idx_scans: number;
  inserts: number;
  updates: number;
}

export interface SystemMetrics {
  security_score: number;
  security_checks: {
    role_isolation: boolean;
    pgcrypto_active: boolean;
    chain_continuous: boolean;
    auth_enforced: boolean;
  };
  security_check_details?: Record<string, 'pass' | 'fail' | 'unknown'>;
  cache_hit_rate: number;
  db_size: string;
  audit_log_size: string;
  total_audit_entries: number;
  total_checkpoints: number;
  table_stats: TableStat[];
}

export interface ConcurrencyLog {
  tx_id: string;
  worker_id: number;
  action: string;
  status: 'pending' | 'success' | 'error';
  sequence_id?: number | null;
  latency_ms: number;
  timestamp: string;
}

export interface ConcurrencyResult {
  workers: number;
  total_time_ms: number;
  success_count: number;
  failed_count: number;
  logs: ConcurrencyLog[];
}

export interface DepartmentItem {
  department_id: number;
  name: string;
}

export interface RoleItem {
  role_id: number;
  department_id: number;
  department_name: string;
  title: string;
  salary_band_min: number;
  salary_band_max: number;
  min_salary: number;
  max_salary: number;
}

export interface AuditLogItem {
  sequence_id: number;
  actor_user_id: number | null;
  actor_name: string;
  employee_id: number | null;
  action: 'INSERT' | 'UPDATE' | 'DELETE';
  table_name: string;
  row_id: number;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  severity: 'INFO' | 'WARNING' | 'CRITICAL';
  entry_hash: string;
  previous_hash: string;
  created_at: string; // ISO timestamp
}

export interface AuditLogPage {
  items: AuditLogItem[];
  total: number;
  page: number;
  pages: number;
  next_cursor?: number | null;
  has_more?: boolean;
}

export interface AuditLogFilters {
  actor_id?: number;
  action?: 'INSERT' | 'UPDATE' | 'DELETE' | '';
  table_name?: string;
  severity?: 'INFO' | 'WARNING' | 'CRITICAL' | '';
  national_id_search?: string;
  sequence_id?: number;
  employee_id?: number;
  page?: number;
  limit?: number;
  before_sequence_id?: number;
}

export interface EmployeeListItem {
  employee_id: number;
  full_name: string;
  email: string;
  role_title: string;
  department_name: string;
  salary: number | null;
  date_hired: string;
  is_active: boolean;
  pii_redacted?: boolean;
}

export interface VerificationResult {
  status: 'intact' | 'tampered' | 'unknown' | 'error';
  entries_scanned: number;
  anchor_match: boolean;
  last_verified_sequence_id: number;
  tampered_sequence_id: number | null;
  details: string;
  verification_checks?: Record<string, 'pass' | 'fail' | 'unknown'>;
}

export interface SuspiciousFlagItem {
  flag_id: number;
  audit_log_sequence_id: number;
  flag_reason: string;
  reviewed_by: number | null;
  reviewed_at: string | null; // ISO timestamp
  created_at: string; // ISO timestamp
}

export interface SuspiciousReviewResponse {
  flag_id: number;
  reviewed_by_user_id: number;
  reviewed_at: string; // ISO timestamp
}

// ─── INT-002: GET /api/audit-logs ─────────────────────────────────────────────

export async function fetchAuditLogs(
  filters: AuditLogFilters,
  getToken: () => Promise<string | null>,
): Promise<AuditLogPage> {
  const params = new URLSearchParams();
  if (filters.actor_id)   params.set('actor_id',   String(filters.actor_id));
  if (filters.action)     params.set('action',      filters.action);
  if (filters.table_name) params.set('table_name',  filters.table_name);
  if (filters.severity)   params.set('severity',    filters.severity);
  if (filters.national_id_search) params.set('national_id_search', filters.national_id_search);
  if (filters.sequence_id !== undefined && filters.sequence_id !== null) {
    params.set('sequence_id', String(filters.sequence_id));
  }
  if (filters.employee_id !== undefined && filters.employee_id !== null) {
    params.set('employee_id', String(filters.employee_id));
  }
  params.set('page',  String(filters.page  ?? 1));
  params.set('limit', String(filters.limit ?? 20));
  if (filters.before_sequence_id !== undefined) {
    params.set('before_sequence_id', String(filters.before_sequence_id));
  }

  return fetchWithAuth(`/audit-logs?${params.toString()}`, {}, getToken);
}

// ─── INT-003: POST /api/verify ────────────────────────────────────────────────

export async function runVerification(
  getToken: () => Promise<string | null>,
): Promise<VerificationResult> {
  return fetchWithAuth('/verify', { method: 'POST' }, getToken);
}

// ─── INT-004: Suspicious Activity ─────────────────────────────────────────────

export const SUSPICIOUS_FLAGS_QUERY_KEY = ['suspiciousFlags'] as const;

export async function fetchSuspiciousFlags(
  getToken: () => Promise<string | null>,
): Promise<SuspiciousFlagItem[]> {
  return fetchWithAuth('/suspicious-activity', {}, getToken);
}

export async function refreshSuspiciousFlags(
  getToken: () => Promise<string | null>,
): Promise<{ status: 'refreshed' }> {
  return fetchWithAuth('/suspicious-activity/refresh', { method: 'POST' }, getToken);
}

export async function reviewSuspiciousFlag(
  flagId: number,
  getToken: () => Promise<string | null>,
): Promise<SuspiciousReviewResponse> {
  return fetchWithAuth(`/suspicious-activity/${flagId}/review`, { method: 'POST' }, getToken);
}

// ─── API-009: Time-Travel ─────────────────────────────────────────────────────

export interface TimeTravelResult {
  employee_id: number;
  full_name: string | null;
  email: string | null;
  role_title: string;
  department_name: string;
  salary: number | null;
  date_hired: string; // ISO timestamp
  is_active: boolean;
  as_of: string; // ISO timestamp
  sequence_id?: number | null;
  pii_redacted: boolean;
}

export async function fetchTimeTravelState(
  employeeId: number,
  timestamp: string,
  getToken: () => Promise<string | null>,
  sequenceId?: number | null,
  includePii = false,
): Promise<TimeTravelResult> {
  const seqParam = sequenceId !== undefined && sequenceId !== null ? `&sequence_id=${sequenceId}` : '';
  const piiParam = `&include_pii=${includePii}`;
  return fetchWithAuth(
    `/employees/${employeeId}/time-travel?timestamp=${encodeURIComponent(timestamp)}${seqParam}${piiParam}`,
    {},
    getToken,
  );
}

// ─── INT-006: Signed JSON Evidence Export ─────────────────────────────────────

export async function downloadSignedEvidence(
  getToken: () => Promise<string | null>,
): Promise<void> {
  const token = await getToken();
  const headers = new Headers();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  // Use raw fetch to get the blob directly
  const response = await fetch(`${API_BASE_URL}/audit-logs/export`, { headers });
  
  if (!response.ok) {
    let errorDetail = 'Failed to export evidence';
    try {
      const errorData = await response.json();
      errorDetail = errorData.detail || errorDetail;
    } catch {
      // Ignore
    }
    throw new Error(errorDetail);
  }

  const blob = await response.blob();
  
  // Extract filename from Content-Disposition if possible
  let filename = `argus_evidence_${new Date().toISOString()}.json`;
  const disposition = response.headers.get('Content-Disposition');
  if (disposition && disposition.indexOf('filename=') !== -1) {
    const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(disposition);
    if (matches != null && matches[1]) {
      filename = matches[1].replace(/['"]/g, '');
    }
  }

  saveBlobDownload(blob, filename);
}

function saveBlobDownload(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = 'none';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // Revoke after the browser has had time to consume the blob URL. Immediate
  // revocation can cancel downloads in some browser implementations.
  window.setTimeout(() => window.URL.revokeObjectURL(url), 1000);
}

// ─── BRIDGE-001 / BRIDGE-002: Live Chain & Anchor Synchronization ───────────

export async function fetchAuditChain(
  getToken: () => Promise<string | null>,
  options: number | AuditChainOptions = 10,
): Promise<ChainEntry[]> {
  const opts: AuditChainOptions = typeof options === 'number' ? { limit: options } : options;
  const params = new URLSearchParams();
  if (opts.limit !== undefined) params.set('limit', String(opts.limit));
  if (opts.offset !== undefined) params.set('offset', String(opts.offset));
  if (opts.around_seq !== undefined) params.set('around_seq', String(opts.around_seq));
  if (opts.table_name) params.set('table_name', opts.table_name);
  if (opts.action) params.set('action', opts.action);

  const queryStr = params.toString();
  return fetchWithAuth(`/audit-logs/chain${queryStr ? `?${queryStr}` : ''}`, {}, getToken);
}

export function useIncidentStatus(): IncidentState {
  const { getToken } = useAuth();

  const verificationQuery = useQuery({
    queryKey: ['chain-verification'],
    enabled: false,
    queryFn: () => runVerification(getToken),
  });

  const anchorQuery = useQuery({
    queryKey: ['anchor-status'],
    queryFn: () => fetchAnchorStatus(getToken),
  });

  const flagsQuery = useQuery({
    queryKey: SUSPICIOUS_FLAGS_QUERY_KEY,
    queryFn: () => fetchSuspiciousFlags(getToken),
  });

  const isVerificationTampered = verificationQuery.data?.status === 'tampered';
  const anchorMismatch = anchorQuery.data?.status === 'MISMATCH';
  const isCompromised = Boolean(isVerificationTampered || anchorMismatch);
  const tamperedSeqId = verificationQuery.data?.tampered_sequence_id ?? null;
  const unreviewedFlagsCount = flagsQuery.data ? flagsQuery.data.filter((f) => !f.reviewed_at).length : 0;
  const isUnavailable =
    (verificationQuery.isError && !verificationQuery.data) ||
    (anchorQuery.isError && !anchorQuery.data) ||
    (flagsQuery.isError && !flagsQuery.data);

  return {
    isCompromised,
    tamperedSeqId,
    anchorMismatch,
    verificationStatus: verificationQuery.data?.status ?? (verificationQuery.isFetching ? 'checking' : 'unknown'),
    verificationChecks: verificationQuery.data?.verification_checks ?? {},
    unreviewedFlagsCount,
    lastVerifiedAt: verificationQuery.dataUpdatedAt
      ? new Date(verificationQuery.dataUpdatedAt).toISOString()
      : null,
    details: verificationQuery.data?.details ?? null,
    isLoading: verificationQuery.isFetching || anchorQuery.isLoading,
    isUnavailable,
    refetch: () => {
      verificationQuery.refetch();
      anchorQuery.refetch();
      flagsQuery.refetch();
    },
  };
}

export async function fetchAnchorStatus(
  getToken: () => Promise<string | null>,
): Promise<AnchorInfo> {
  return fetchWithAuth('/anchor/status', {}, getToken);
}

// ─── PACK-002 / PACK-003: Portable Evidence Bundle (.arguspack) ─────────────

export async function downloadEvidencePack(
  getToken: () => Promise<string | null>,
): Promise<void> {
  const token = await getToken();
  const headers = new Headers();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}/audit-logs/export-pack`, { headers });
  
  if (!response.ok) {
    let errorDetail = 'Failed to export evidence pack';
    try {
      const errorData = await response.json();
      errorDetail = errorData.detail || errorDetail;
    } catch {
      // Ignore
    }
    throw new Error(errorDetail);
  }

  const blob = await response.blob();
  
  let filename = `audit_evidence_${new Date().toISOString().replace(/[:.]/g, '-')}.arguspack`;
  const disposition = response.headers.get('Content-Disposition');
  if (disposition && disposition.indexOf('filename=') !== -1) {
    const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(disposition);
    if (matches != null && matches[1]) {
      filename = matches[1].replace(/['"]/g, '');
    }
  }

  saveBlobDownload(blob, filename);
}

// ─── LIVE-001: Live Telemetry, Dashboard Stats & Real Engine Testing ──────────

export async function fetchDashboardStats(
  getToken: () => Promise<string | null>,
): Promise<DashboardStats> {
  return fetchWithAuth('/dashboard/stats', {}, getToken);
}

export async function fetchSystemMetrics(
  getToken: () => Promise<string | null>,
): Promise<SystemMetrics> {
  return fetchWithAuth('/analytics/system-metrics', {}, getToken);
}

export async function runConcurrencyTest(
  workers: number,
  getToken: () => Promise<string | null>,
): Promise<ConcurrencyResult> {
  return fetchWithAuth('/analytics/diagnostics/concurrency-benchmark', {
    method: 'POST',
    body: JSON.stringify({ workers }),
  }, getToken);
}


export async function fetchDepartments(
  getToken: () => Promise<string | null>,
): Promise<DepartmentItem[]> {
  return fetchWithAuth('/departments', {}, getToken);
}

export async function fetchRoles(
  getToken: () => Promise<string | null>,
): Promise<RoleItem[]> {
  const data: unknown = await fetchWithAuth('/roles', {}, getToken);
  if (!Array.isArray(data)) return [];

  return data.filter((item): item is Record<string, unknown> =>
    typeof item === 'object' && item !== null && !Array.isArray(item),
  ).map((role) => {
    const minVal = Number(role.salary_band_min ?? role.min_salary ?? 0);
    const maxVal = Number(role.salary_band_max ?? role.max_salary ?? 0);
    return {
      role_id: Number(role.role_id),
      department_id: Number(role.department_id),
      department_name: typeof role.department_name === 'string' ? role.department_name : '',
      title: typeof role.title === 'string' ? role.title : '',
      salary_band_min: minVal,
      salary_band_max: maxVal,
      min_salary: minVal,
      max_salary: maxVal,
    };
  });
}

export async function fetchEmployees(
  getToken: () => Promise<string | null>,
  limit: number = 100,
  search?: string,
  page: number = 1,
  department?: string,
  isActive?: boolean,
  includePii: boolean = false,
): Promise<{ items: EmployeeListItem[]; total: number; page: number; pages: number }> {
  const searchParam = search ? `&search=${encodeURIComponent(search)}` : '';
  const deptParam = department && department !== 'all' ? `&department=${encodeURIComponent(department)}` : '';
  const statusParam = isActive !== undefined ? `&is_active=${isActive}` : '';
  const piiParam = `&include_pii=${includePii}`;
  return fetchWithAuth(`/employees?limit=${limit}&page=${page}${searchParam}${deptParam}${statusParam}${piiParam}`, {}, getToken);
}

export interface UserProfile {
  user_id: number;
  clerk_user_id: string;
  full_name: string;
  email: string;
  role: 'hr_admin' | 'compliance_auditor';
  is_active: boolean;
  created_at: string;
}

export async function fetchMyProfile(
  getToken: () => Promise<string | null>,
): Promise<UserProfile> {
  return fetchWithAuth('/auth/me', {}, getToken);
}


// ─── Counterfactual Replay (NOVEL-011) ───────────────────────────────────────

export interface CounterfactualRequest {
  employee_id: number;
  skip_sequence_ids: number[];
  as_of?: string;
}

export interface SkippedEventInfo {
  sequence_id: number;
  actor_user_id: number;
  action: string;
  table_name: string;
  created_at: string;
  severity: string;
  delta_summary: string;
  old_value?: Record<string, unknown> | null;
  new_value?: Record<string, unknown> | null;
}

export interface BlastRadius {
  salary_actual: number;
  salary_counterfactual: number;
  salary_overpaid_annual: number;
  salary_overpaid_cumulative: number;
  tenure_months: number;
  skipped_events_count: number;
  skipped_sequence_ids: number[];
  first_fraud_event_timestamp?: string | null;
  as_of_timestamp?: string | null;
}

export interface CounterfactualResult {
  employee_id: number;
  as_of: string;
  skip_sequence_ids: number[];
  actual_state: Record<string, unknown> | null;
  counterfactual_state: Record<string, unknown> | null;
  blast_radius: BlastRadius;
  skipped_events: SkippedEventInfo[];
  applied_events_count: number;
  simulation_duration_ms: number;
}

export async function runCounterfactualSimulation(
  payload: CounterfactualRequest,
  getToken: () => Promise<string | null>,
): Promise<CounterfactualResult> {
  return fetchWithAuth(
    '/audit-logs/counterfactual',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
    getToken,
  );
}


// ─── NOVEL-009: Selective Merkle Proof & .arguscap Capsule ───────────────────

export interface MerkleAuditStep {
  level: number;
  direction: 'left' | 'right';
  sibling_hash: string;
}

export interface MerkleProof {
  sequence_id: number;
  checkpoint_id: number;
  leaf_index: number;
  leaf_hash: string;
  merkle_root: string;
  tree_size: number;
  audit_path_depth: number;
  audit_path: MerkleAuditStep[];
  created_at?: string | null;
}

export async function getMerkleProof(
  seqId: number,
  getToken: () => Promise<string | null>,
): Promise<MerkleProof> {
  return fetchWithAuth(`/audit-logs/${seqId}/proof`, {}, getToken);
}

export interface CreatedCheckpoint {
  checkpoint_id: number;
  sequence_id: number;
  checkpoint_hash: string;
  merkle_root: string;
  merkle_leaf_count: number;
  entries_sealed: number;
  signature_status: 'signed';
  key_id: string;
  created_at: string;
  external_anchor_created: false;
}

export async function createCheckpointNow(
  getToken: () => Promise<string | null>,
): Promise<CreatedCheckpoint> {
  return fetchWithAuth('/checkpoints/create', { method: 'POST' }, getToken);
}

export async function downloadCapsule(
  seqId: number,
  getToken: (options?: { skipCache?: boolean }) => Promise<string | null>,
): Promise<string> {
  let token = await getToken();
  const headers = new Headers();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  let response = await fetch(`${API_BASE_URL}/audit-logs/${seqId}/capsule`, { headers });
  if (response.status === 401) {
    const freshToken = await getToken({ skipCache: true });
    if (freshToken && freshToken !== token) {
      token = freshToken;
      headers.set('Authorization', `Bearer ${token}`);
      response = await fetch(`${API_BASE_URL}/audit-logs/${seqId}/capsule`, { headers });
    }
  }
  
  if (!response.ok) {
    let errorDetail = 'Failed to export forensic capsule';
    try {
      const errorData = await response.json();
      errorDetail = errorData.detail || errorDetail;
    } catch {
      // Ignore
    }
    throw new Error(errorDetail);
  }

  const blob = await response.blob();
  
  let filename = `proof_seq${seqId}.arguscap`;
  const disposition = response.headers.get('Content-Disposition');
  if (disposition && disposition.indexOf('filename=') !== -1) {
    const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(disposition);
    if (matches != null && matches[1]) {
      filename = matches[1].replace(/['"]/g, '');
    }
  }

  saveBlobDownload(blob, filename);
  return filename;
}







