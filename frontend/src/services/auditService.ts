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

import { fetchWithAuth } from '../lib/api';

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
