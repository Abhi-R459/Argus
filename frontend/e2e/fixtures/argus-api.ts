import type { Page } from '@playwright/test';

/**
 * Stable, read-only data for browser rendering checks. These responses are
 * inspired by the user's populated workspace screenshots; they do not touch
 * the running database and never contain a real Clerk token.
 */
export async function mockArgusApi(page: Page): Promise<void> {
  const now = Date.now();
  const isoDaysAgo = (days: number) => new Date(now - days * 86_400_000).toISOString();
  const employees = Array.from({ length: 12 }, (_, index) => ({
    employee_id: 1001 + index,
    full_name: ['Maya Rao', 'Noah Patel', 'Amara Iyer', 'Ethan Shah'][index % 4],
    email: `employee${index + 1}@example.test`,
    role_title: ['Engineer', 'Analyst', 'People Partner'][index % 3],
    department_name: ['Engineering', 'Finance', 'People'][index % 3],
    salary: 780_000 + index * 35_000,
    date_hired: isoDaysAgo(400 + index * 60),
    is_active: index !== 10,
  }));
  const chainEntries = Array.from({ length: 10 }, (_, index) => {
    const sequence = 142 - index;
    const hash = sequence.toString(16).padStart(4, '0').repeat(16);
    const previousHash = (sequence - 1).toString(16).padStart(4, '0').repeat(16);
    return {
      entry_id: sequence,
      hash,
      prev_hash: previousHash,
      table_name: sequence % 4 === 0 ? 'salary_history' : 'employees',
      operation: sequence % 3 === 0 ? 'UPDATE' : 'INSERT',
      actor_email: 'auditor@example.test',
      actor_role: 'hr_admin',
      timestamp: isoDaysAgo(9),
      severity: sequence === 142 ? 'medium' : 'low',
      old_value: { status: 'pending' },
      new_value: { status: 'active', record: `EMP-${1000 + sequence}` },
    };
  });
  const suspiciousFlags = [{
    flag_id: 7,
    audit_log_sequence_id: 138,
    flag_reason: 'Compensation change outside the usual review window',
    reviewed_by: null as number | null,
    reviewed_at: null as string | null,
    created_at: isoDaysAgo(2),
  }];

  await page.route('**/api/**', async (route) => {
    const requestUrl = new URL(route.request().url());
    const endpoint = requestUrl.pathname.replace(/^\/api/, '');
    const method = route.request().method();
    let response: unknown;

    const salaryMatch = endpoint.match(/^\/employees\/(\d+)\/salary$/);
    if (salaryMatch && method === 'POST') {
      const employee = employees.find((item) => item.employee_id === Number(salaryMatch[1]));
      const body = route.request().postDataJSON() as { amount?: number };
      if (employee && typeof body.amount === 'number') employee.salary = body.amount;
      await route.fulfill({
        status: employee ? 200 : 404,
        contentType: 'application/json',
        body: JSON.stringify(employee ? { employee_id: employee.employee_id, salary: employee.salary } : { detail: 'Employee not found' }),
      });
      return;
    }

    if (endpoint === '/suspicious-activity/refresh' && method === 'POST') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'refreshed' }) });
      return;
    }

    if (endpoint === '/checkpoints/create' && method === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          checkpoint_id: 7,
          sequence_id: 142,
          checkpoint_hash: 'a'.repeat(64),
          merkle_root: 'b'.repeat(64),
          merkle_leaf_count: 12,
          entries_sealed: 12,
          signature_status: 'signed',
          key_id: 'local:ed25519:v1',
          created_at: new Date().toISOString(),
          external_anchor_created: false,
        }),
      });
      return;
    }

    const reviewMatch = endpoint.match(/^\/suspicious-activity\/(\d+)\/review$/);
    if (reviewMatch && method === 'POST') {
      const flag = suspiciousFlags.find((item) => item.flag_id === Number(reviewMatch[1]));
      if (flag) {
        flag.reviewed_by = 101;
        flag.reviewed_at = new Date().toISOString();
      }
      await route.fulfill({ status: flag ? 200 : 404, contentType: 'application/json', body: JSON.stringify(flag ? { flag_id: flag.flag_id, reviewed_by_user_id: 101, reviewed_at: flag.reviewed_at } : { detail: 'Not found' }) });
      return;
    }

    switch (endpoint) {
      case '/dashboard/stats':
        response = {
          total_employees: 68,
          active_employees: 66,
          total_audit_events: 142,
          unreviewed_flags: suspiciousFlags.filter((flag) => !flag.reviewed_at).length,
          recent_activity: Array.from({ length: 8 }, (_, index) => ({
            sequence_id: 142 - index,
            actor_name: 'Compliance Operator',
            action: index % 3 === 0 ? 'UPDATE' : 'INSERT',
            table_name: index % 2 ? 'employees' : 'salary_history',
            created_at: isoDaysAgo(9),
          })),
        };
        break;
      case '/verify':
        response = {
          status: 'intact',
          entries_scanned: 142,
          anchor_match: true,
          last_verified_sequence_id: 142,
          tampered_sequence_id: null,
          details: 'Chain walks successfully across 142 entries. Tail hash matches the anchor store.',
          verification_checks: {
            hash_chain: 'pass',
            external_anchor: 'pass',
            checkpoint_signatures: 'pass',
          },
        };
        break;
      case '/anchor/status':
        response = {
          status: 'ANCHORED',
          anchor_store: 'multi_witness',
          anchor_location: './anchor/chain_anchor.log',
          last_anchored: isoDaysAgo(12),
          anchor_hash: 'sha256:905015044f773248b96c8eb6f0833f985008f144815de1e36c186f0b1735a9c2',
          entries_since_anchor: 15,
          witness_report: {
            verification_status: 'unknown',
            deployment_mode: 'in_process_reference',
            independent_trust_domains: false,
            quorum_satisfied: false,
            required_threshold: 2,
            total_witnesses: 3,
            cosigned_witnesses: 0,
            per_witness: [],
            message: 'Witness status is unknown because no persisted witness note is available.',
          },
        };
        break;
      case '/audit-logs/chain':
        response = chainEntries;
        break;
      case '/suspicious-activity':
        response = suspiciousFlags;
        break;
      case '/departments':
        response = [
          { department_id: 1, name: 'Engineering' },
          { department_id: 2, name: 'Finance' },
          { department_id: 3, name: 'People' },
        ];
        break;
      case '/roles':
        response = [
          { role_id: 1, department_id: 1, department_name: 'Engineering', title: 'Engineer', salary_band_min: 600_000, salary_band_max: 1_500_000 },
          { role_id: 2, department_id: 2, department_name: 'Finance', title: 'Analyst', salary_band_min: 500_000, salary_band_max: 1_200_000 },
          { role_id: 3, department_id: 3, department_name: 'People', title: 'People Partner', salary_band_min: 550_000, salary_band_max: 1_100_000 },
        ];
        break;
      case '/employees':
        response = { items: employees, total: 68, page: 1, pages: 6 };
        break;
      case '/analytics/system-metrics':
        response = {
          security_score: 96,
          security_checks: { role_isolation: true, pgcrypto_active: true, chain_continuous: true, auth_enforced: true },
          cache_hit_rate: 98.4,
          db_size: '82 MB',
          audit_log_size: '14 MB',
          total_audit_entries: 142,
          total_checkpoints: 6,
          table_stats: [
            { table_name: 'employees', seq_scans: 22, idx_scans: 218, inserts: 8, updates: 19 },
            { table_name: 'salary_history', seq_scans: 4, idx_scans: 72, inserts: 12, updates: 0 },
          ],
        };
        break;
      default:
        await route.fulfill({
          status: 501,
          contentType: 'application/json',
          body: JSON.stringify({ detail: `Unhandled E2E API route: ${method} ${endpoint}` }),
        });
        return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(response),
    });
  });
}
