/**
 * Mock Audit Service — INT-001
 *
 * Provides static, typed mock data for the Compliance Auditor Dashboard.
 * These functions will be swapped for real API calls in Weeks 6–8 (per DEC-010).
 *
 * All types here mirror the shapes defined in contracts/api_contract.md.
 */

// ─── Types ────────────────────────────────────────────────────────────────────

export type VerificationStatus = 'VERIFIED' | 'TAMPERED' | 'PENDING';
export type AnchorStoreType = 'local_file' | 'github_repo';
export type AuditOperation = 'INSERT' | 'UPDATE' | 'DELETE';
export type Severity = 'low' | 'medium' | 'high' | 'critical';

export interface VerificationResult {
  status: VerificationStatus;
  last_run: string;            // ISO timestamp
  duration_ms: number;
  checked_entries: number;
  last_checkpoint_id: number;
  last_checkpoint_hash: string;
  error_detail: string | null;
}

export interface ChainEntry {
  entry_id: number;
  hash: string;
  prev_hash: string | null;
  table_name: string;
  operation: AuditOperation;
  actor_email: string;
  actor_role: 'hr_admin' | 'compliance_auditor' | 'system';
  timestamp: string;           // ISO timestamp
  severity: Severity;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
}

export interface AnchorInfo {
  status: 'ANCHORED' | 'STALE' | 'MISSING';
  anchor_store: AnchorStoreType;
  anchor_location: string;
  last_anchored: string;       // ISO timestamp
  anchor_hash: string;
  entries_since_anchor: number;
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

// ─── Mock Data ────────────────────────────────────────────────────────────────

const MOCK_CHAIN: ChainEntry[] = [
  {
    entry_id: 1042,
    hash: 'a3f8b2c1d4e5f607a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1',
    prev_hash: '9e2c4a6f8b0d2f4a6c8e0b2d4f6a8c0e2b4d6f8a0c2e4b6d8f0a2c4e6b8d0f2',
    table_name: 'employees',
    operation: 'UPDATE',
    actor_email: 'priya.sharma@corp.com',
    actor_role: 'hr_admin',
    timestamp: new Date(Date.now() - 12 * 60 * 1000).toISOString(),
    severity: 'low',
    old_value: { full_name: 'Raj Kumar', role_title: 'Junior Engineer', department_id: 3 },
    new_value: { full_name: 'Raj Kumar', role_title: 'Senior Engineer', department_id: 3 },
  },
  {
    entry_id: 1041,
    hash: '9e2c4a6f8b0d2f4a6c8e0b2d4f6a8c0e2b4d6f8a0c2e4b6d8f0a2c4e6b8d0f2',
    prev_hash: 'b1d3f5a7c9e1b3d5f7a9c1e3b5d7f9a1c3e5b7d9f1a3c5e7b9d1f3a5c7e9b1d3',
    table_name: 'salary_history',
    operation: 'INSERT',
    actor_email: 'priya.sharma@corp.com',
    actor_role: 'hr_admin',
    timestamp: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
    severity: 'medium',
    old_value: null,
    new_value: { employee_id: 87, amount: 95000, effective_date: '2026-08-01' },
  },
  {
    entry_id: 1040,
    hash: 'b1d3f5a7c9e1b3d5f7a9c1e3b5d7f9a1c3e5b7d9f1a3c5e7b9d1f3a5c7e9b1d3',
    prev_hash: 'c2e4f6b8d0a2c4e6b8d0f2a4c6e8b0d2f4a6c8e0b2d4f6a8c0e2b4d6f8a0c2e4',
    table_name: 'employees',
    operation: 'INSERT',
    actor_email: 'system@argus.internal',
    actor_role: 'system',
    timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    severity: 'low',
    old_value: null,
    new_value: { full_name: 'Ananya Iyer', email: 'ananya.iyer@corp.com', department_id: 2 },
  },
  {
    entry_id: 1039,
    hash: 'c2e4f6b8d0a2c4e6b8d0f2a4c6e8b0d2f4a6c8e0b2d4f6a8c0e2b4d6f8a0c2e4',
    prev_hash: 'd3f5a7b9c1e3d5f7a9b1c3e5d7f9a1b3c5e7d9f1a3b5c7e9d1f3a5b7c9e1d3f5',
    table_name: 'employees',
    operation: 'DELETE',
    actor_email: 'nidhu.admin@corp.com',
    actor_role: 'hr_admin',
    timestamp: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(),
    severity: 'high',
    old_value: { full_name: 'Vikram Nair', email: 'vikram.nair@corp.com', is_active: true },
    new_value: { is_active: false },
  },
  {
    entry_id: 1038,
    hash: 'd3f5a7b9c1e3d5f7a9b1c3e5d7f9a1b3c5e7d9f1a3b5c7e9d1f3a5b7c9e1d3f5',
    prev_hash: 'e4a6b8c0d2f4e6a8b0c2d4f6e8a0b2c4d6f8e0a2b4c6d8f0e2a4b6c8d0f2e4a6',
    table_name: 'salary_history',
    operation: 'INSERT',
    actor_email: 'priya.sharma@corp.com',
    actor_role: 'hr_admin',
    timestamp: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(),
    severity: 'medium',
    old_value: null,
    new_value: { employee_id: 44, amount: 130000, effective_date: '2026-07-15' },
  },
  {
    entry_id: 1037,
    hash: 'e4a6b8c0d2f4e6a8b0c2d4f6e8a0b2c4d6f8e0a2b4c6d8f0e2a4b6c8d0f2e4a6',
    prev_hash: 'f5b7c9d1e3f5b7c9d1e3f5b7c9d1e3f5b7c9d1e3f5b7c9d1e3f5b7c9d1e3f5b7',
    table_name: 'employees',
    operation: 'UPDATE',
    actor_email: 'nidhu.admin@corp.com',
    actor_role: 'hr_admin',
    timestamp: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    severity: 'low',
    old_value: { department_id: 1 },
    new_value: { department_id: 4 },
  },
  {
    entry_id: 1036,
    hash: 'f5b7c9d1e3f5b7c9d1e3f5b7c9d1e3f5b7c9d1e3f5b7c9d1e3f5b7c9d1e3f5b7',
    prev_hash: 'a0b2c4d6f8a0b2c4d6f8a0b2c4d6f8a0b2c4d6f8a0b2c4d6f8a0b2c4d6f8a0b2',
    table_name: 'departments',
    operation: 'INSERT',
    actor_email: 'system@argus.internal',
    actor_role: 'system',
    timestamp: new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString(),
    severity: 'low',
    old_value: null,
    new_value: { name: 'AI Research', manager_id: 12 },
  },
  {
    entry_id: 1035,
    hash: 'a0b2c4d6f8a0b2c4d6f8a0b2c4d6f8a0b2c4d6f8a0b2c4d6f8a0b2c4d6f8a0b2',
    prev_hash: 'b1c3d5e7f9b1c3d5e7f9b1c3d5e7f9b1c3d5e7f9b1c3d5e7f9b1c3d5e7f9b1c3',
    table_name: 'employees',
    operation: 'UPDATE',
    actor_email: 'priya.sharma@corp.com',
    actor_role: 'hr_admin',
    timestamp: new Date(Date.now() - 72 * 60 * 60 * 1000).toISOString(),
    severity: 'critical',
    old_value: { role_title: 'Intern', salary: 18000 },
    new_value: { role_title: 'Staff Engineer', salary: 125000 },
  },
  {
    entry_id: 1034,
    hash: 'b1c3d5e7f9b1c3d5e7f9b1c3d5e7f9b1c3d5e7f9b1c3d5e7f9b1c3d5e7f9b1c3',
    prev_hash: 'c2d4e6f8a0c2d4e6f8a0c2d4e6f8a0c2d4e6f8a0c2d4e6f8a0c2d4e6f8a0c2d4',
    table_name: 'salary_history',
    operation: 'INSERT',
    actor_email: 'nidhu.admin@corp.com',
    actor_role: 'hr_admin',
    timestamp: new Date(Date.now() - 96 * 60 * 60 * 1000).toISOString(),
    severity: 'medium',
    old_value: null,
    new_value: { employee_id: 21, amount: 72000, effective_date: '2026-08-01' },
  },
  {
    entry_id: 1033,
    hash: 'c2d4e6f8a0c2d4e6f8a0c2d4e6f8a0c2d4e6f8a0c2d4e6f8a0c2d4e6f8a0c2d4',
    prev_hash: 'd3e5f7a9b1d3e5f7a9b1d3e5f7a9b1d3e5f7a9b1d3e5f7a9b1d3e5f7a9b1d3e5',
    table_name: 'employees',
    operation: 'INSERT',
    actor_email: 'system@argus.internal',
    actor_role: 'system',
    timestamp: new Date(Date.now() - 120 * 60 * 60 * 1000).toISOString(),
    severity: 'low',
    old_value: null,
    new_value: { full_name: 'Devika Menon', email: 'devika.menon@corp.com', department_id: 1 },
  },
];

const MOCK_VERIFICATION: VerificationResult = {
  status: 'VERIFIED',
  last_run: new Date(Date.now() - 47 * 60 * 1000).toISOString(),
  duration_ms: 284,
  checked_entries: 1042,
  last_checkpoint_id: 1000,
  last_checkpoint_hash: 'd3e5f7a9b1d3e5f7a9b1d3e5f7a9b1d3e5f7a9b1d3e5f7a9b1d3e5f7a9b1d3e5',
  error_detail: null,
};

const MOCK_ANCHOR: AnchorInfo = {
  status: 'ANCHORED',
  anchor_store: 'github_repo',
  anchor_location: 'github.com/Abhi-R459/argus-anchors',
  last_anchored: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
  anchor_hash: 'sha256:a3f8b2c1d4e5f607a8b9c0d1e2f3a4b5',
  entries_since_anchor: 42,
};

const MOCK_FLAGS: SuspiciousFlag[] = [
  {
    flag_id: 7,
    employee_id: 87,
    employee_name: 'Raj Kumar',
    reason: 'Salary increased by >100% in a single transaction',
    severity: 'critical',
    flagged_at: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
    reviewed: false,
  },
  {
    flag_id: 6,
    employee_id: 44,
    employee_name: 'Meena Bhat',
    reason: 'Role changed from Intern to Staff Engineer',
    severity: 'high',
    flagged_at: new Date(Date.now() - 72 * 60 * 60 * 1000).toISOString(),
    reviewed: false,
  },
];

// ─── Service Functions ────────────────────────────────────────────────────────

/** Returns the current verification state of the hash chain. */
export function getVerificationStatus(): VerificationResult {
  return MOCK_VERIFICATION;
}

/** Returns the most recent N audit chain entries (newest first). */
export function getAuditChain(limit = 10): ChainEntry[] {
  return MOCK_CHAIN.slice(0, limit);
}

/** Returns the current cryptographic anchor state. */
export function getAnchorStatus(): AnchorInfo {
  return MOCK_ANCHOR;
}

/** Returns all unreviewed suspicious activity flags. */
export function getSuspiciousFlags(): SuspiciousFlag[] {
  return MOCK_FLAGS;
}
