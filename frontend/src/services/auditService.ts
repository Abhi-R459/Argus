/**
 * Audit Service — INT-002 / INT-003 / INT-004
 *
 * Real API calls for the Compliance Auditor Dashboard.
 * Replaces the mock functions in mockAuditService.ts for:
 *   - Audit log listing (GET /api/audit-logs)
 *   - Chain verification  (POST /api/verify)
 *   - Suspicious activity (GET /api/suspicious-activity, POST .../review)
 *
 * mockAuditService.ts is still used for anchor status and chain summary
 * until those real endpoints land in Weeks 7–8.
 */

import { fetchWithAuth, API_BASE_URL } from '../lib/api';

// ─── Types (mirror api_contract.md §4) ────────────────────────────────────────

export interface AuditLogItem {
  sequence_id: number;
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
}

export interface AuditLogFilters {
  actor_id?: number;
  action?: 'INSERT' | 'UPDATE' | 'DELETE' | '';
  table_name?: string;
  severity?: 'INFO' | 'WARNING' | 'CRITICAL' | '';
  page?: number;
  limit?: number;
}

export interface VerificationResult {
  status: 'intact' | 'tampered';
  entries_scanned: number;
  anchor_match: boolean;
  last_verified_sequence_id: number;
  tampered_sequence_id: number | null;
  details: string;
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
  params.set('page',  String(filters.page  ?? 1));
  params.set('limit', String(filters.limit ?? 20));

  return fetchWithAuth(`/audit-logs?${params.toString()}`, {}, getToken);
}

// ─── INT-003: POST /api/verify ────────────────────────────────────────────────

export async function runVerification(
  getToken: () => Promise<string | null>,
): Promise<VerificationResult> {
  return fetchWithAuth('/verify', { method: 'POST' }, getToken);
}

// ─── INT-004: Suspicious Activity ─────────────────────────────────────────────

export async function fetchSuspiciousFlags(
  getToken: () => Promise<string | null>,
): Promise<SuspiciousFlagItem[]> {
  return fetchWithAuth('/suspicious-activity', {}, getToken);
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
  full_name: string;
  email: string;
  role_title: string;
  department_name: string;
  salary: number;
  date_hired: string; // ISO timestamp
  is_active: boolean;
  as_of: string; // ISO timestamp
}

export async function fetchTimeTravelState(
  employeeId: number,
  timestamp: string,
  getToken: () => Promise<string | null>,
): Promise<TimeTravelResult> {
  return fetchWithAuth(`/employees/${employeeId}/time-travel?timestamp=${encodeURIComponent(timestamp)}`, {}, getToken);
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

  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
