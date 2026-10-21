import { test, expect } from '@playwright/test';
import { mockArgusApi } from './fixtures/argus-api';

test.describe('Compliance Auditor Portal E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Inject E2E role for Compliance Auditor
    await page.addInitScript(() => {
      (window as Window & { __E2E_ROLE__?: string }).__E2E_ROLE__ = 'compliance_auditor';
    });
    await mockArgusApi(page);
  });

  test('scheduled integrity monitor surfaces a tamper finding and sequence detail', async ({ page }) => {
    await page.route('**/api/monitor/status', (route) => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        enabled: true,
        status: 'tampered',
        last_result_status: 'tampered',
        observed_at: new Date().toISOString(),
        age_seconds: 0,
        stale: false,
        interval_seconds: 300,
        alert_delivery: 'sent',
        entries_scanned: 18,
        last_verified_sequence_id: 17,
        tampered_sequence_id: 18,
        details: 'Hash mismatch at sequence 18.',
        verification_checks: { hash_chain: 'fail', external_anchor: 'pass' },
      }),
    }));

    await page.goto('/auditor/overview');
    await expect(page.getByRole('heading', { name: 'Integrity incident detected' })).toBeVisible();
    await expect(page.getByText('Hash mismatch at sequence 18.').first()).toBeVisible();
    await expect(page.getByText('hash chain · fail')).toBeVisible();
  });

  test('Auditor portal navigation and layout rendering', async ({ page }) => {
    const browserErrors: string[] = [];
    page.on('pageerror', (error) => {
      // The fake E2E publishable key cannot be attributed to a live Clerk
      // instance; the route fixture bypasses Clerk and tests the app itself.
      if (!error.stack?.includes('test.clerk.accounts.dev')) {
        browserErrors.push(error.message);
      }
    });
    page.on('console', (message) => {
      const text = message.text();
      const expectedMockKeyError = text.includes('Failed to load resource: the server responded with a status of 400 ()')
        || text.includes('ClerkJS: Something went wrong initializing Clerk in development mode');
      if (message.type() === 'error' && !expectedMockKeyError) browserErrors.push(text);
    });
    await page.goto('http://localhost:5173/auditor/overview');
    await page.waitForLoadState('networkidle');

    // Auditor header status pill
    const poolBadge = page.locator('text=Pool: compliance_auditor');
    await expect(poolBadge).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Scheduled integrity checks are passing' })).toBeVisible();
    await expect(page.getByText('Alert delivery: not configured')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Run Verification' })).toBeVisible();
    await page.getByRole('button', { name: 'Run Verification' }).click();
    await expect(page.getByText('Last check passed', { exact: true }).first()).toBeVisible();
    await expect(page.getByText(/Checked through sequence #142/)).toBeVisible();
    await expect(page.getByText('Unverified')).toBeVisible();
    await expect(page.getByText(/do not represent independent trust domains/i)).toBeVisible();

    // Sidebar navigation links (scoped to aside to avoid duplicate in-page action links)
    await expect(page.locator('aside a[href="/auditor/overview"]')).toBeVisible();
    await expect(page.locator('aside a[href="/auditor/chain"]')).toBeVisible();
    await expect(page.locator('aside a[href="/auditor/log"]')).toBeVisible();
    await expect(page.locator('aside a[href="/auditor/time-travel"]')).toBeVisible();
    await expect(page.locator('aside a[href="/auditor/counterfactual"]')).toBeVisible();
    await expect(page.locator('aside a[href="/auditor/forensic-evidence"]')).toBeVisible();
    expect(browserErrors).toEqual([]);
  });

  test('Auditor verification and risk refresh update the dashboard data', async ({ page }) => {
    await page.goto('http://localhost:5173/auditor/overview');
    await expect(page.getByText('1 pending flag', { exact: true })).toBeVisible();

    const verificationRequest = page.waitForRequest((request) =>
      new URL(request.url()).pathname.endsWith('/verify') && request.method() === 'POST'
    );
    await page.getByRole('button', { name: 'Run Verification' }).click();
    await verificationRequest;

    await page.getByRole('link', { name: 'Open Risk Panel' }).click();
    await expect(page.getByRole('heading', { name: 'Flagged Events' })).toBeVisible();
    const detectionResponse = page.waitForResponse((response) =>
      new URL(response.url()).pathname.endsWith('/suspicious-activity/refresh') && response.request().method() === 'POST'
    );
    await page.getByRole('button', { name: /Refresh detections/ }).click();
    expect((await detectionResponse).ok()).toBeTruthy();

    const reviewResponse = page.waitForResponse((response) =>
      new URL(response.url()).pathname.endsWith('/suspicious-activity/7/review') && response.request().method() === 'POST'
    );
    await page.getByRole('button', { name: 'Mark Safe' }).click();
    expect((await reviewResponse).ok()).toBeTruthy();
    await expect(page.getByText('No unreviewed flags found.')).toBeVisible();

    await page.locator('aside a[href="/auditor/overview"]').click();
    await expect(page.getByText('0 pending flags', { exact: true })).toBeVisible();
  });

  test('Auditor analytics, audit-log, and chain sync controls call their data APIs', async ({ page }) => {
    await page.goto('http://localhost:5173/auditor/analytics');
    await expect(page.getByRole('heading', { name: 'Security & Isolation Posture' })).toBeVisible();

    const metricsRequest = page.waitForRequest((request) =>
      new URL(request.url()).pathname.endsWith('/analytics/system-metrics') && request.method() === 'GET'
    );
    await page.getByRole('button', { name: 'Re-verify posture' }).click();
    await metricsRequest;

    await page.goto('http://localhost:5173/auditor/log');
    await expect(page.getByRole('heading', { name: 'Audit Log' })).toBeVisible();
    const auditLogRequest = page.waitForRequest((request) =>
      new URL(request.url()).pathname.endsWith('/audit-logs') && request.method() === 'GET'
    );
    await page.getByRole('button', { name: 'Sync (Refresh audit logs)' }).click();
    await auditLogRequest;

    await page.goto('http://localhost:5173/auditor/chain');
    await expect(page.locator('input#audit-chain-seq-search')).toBeVisible();
    const chainRequest = page.waitForRequest((request) =>
      new URL(request.url()).pathname.endsWith('/audit-logs/chain') && request.method() === 'GET'
    );
    await page.getByRole('button', { name: 'Sync (Sync chain now)' }).click();
    await chainRequest;
  });

  test('National ID searches stay out of request URLs', async ({ page }) => {
    const identifier = 'PRIVATE-IDENTIFIER-123';
    const requestUrls: string[] = [];
    page.on('request', (request) => requestUrls.push(request.url()));
    await page.goto('http://localhost:5173/auditor/log');
    await expect(page.getByRole('heading', { name: 'Audit Log' })).toBeVisible();
    const searchRequest = page.waitForRequest((request) =>
      new URL(request.url()).pathname.endsWith('/audit-logs/search') && request.method() === 'POST'
    );
    await page.locator('#audit-log-blind-id-filter').fill(identifier);
    const request = await searchRequest;
    expect(request.postDataJSON().national_id_search).toBe(identifier);
    expect(requestUrls.every((url) => !url.includes(identifier) && !url.includes('national_id_search'))).toBeTruthy();
    expect(new URL(page.url()).search).not.toContain(identifier);
  });

  test('Auditor risk refresh explains contention with the background detector', async ({ page }) => {
    await page.route('**/api/suspicious-activity/refresh', (route) =>
      route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ detail: 'Suspicious-activity detection is already running.' }) })
    );
    await page.goto('/auditor/activity');
    await page.getByRole('button', { name: 'Refresh detections (Run risk detection and reload flags)' }).click();
    await expect(page.getByRole('alert')).toContainText('Risk detection is already running. Wait a moment, then refresh again.');
    await expect(page.getByRole('button', { name: 'Mark Safe', exact: true })).toBeVisible();
  });

  test('Auditor risk refresh failure is visible and flags stay unreviewed', async ({ page }) => {
    await page.route('**/api/suspicious-activity/refresh', (route) =>
      route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Detection unavailable' }) })
    );
    await page.goto('http://localhost:5173/auditor/activity');
    await expect(page.getByRole('heading', { name: 'Flagged Events' })).toBeVisible();

    await page.getByRole('button', { name: /Refresh detections/ }).click();
    await expect(page.getByRole('alert').filter({ hasText: 'Risk detection failed. Existing flags are unchanged.' })).toBeVisible();
    await expect(page.getByText('Unreviewed (1)')).toBeVisible();
  });

  test('Incomplete chain evidence is shown as unverified rather than tampered or healthy', async ({ page }) => {
    await page.route('**/api/verify', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'unknown',
          entries_scanned: 142,
          anchor_match: true,
          last_verified_sequence_id: 142,
          tampered_sequence_id: null,
          details: 'Checkpoint signatures are unavailable.',
          verification_checks: { hash_chain: 'pass', checkpoint_binding: 'pass', external_anchor: 'pass', checkpoint_signatures: 'unknown' },
        }),
      })
    );
    await page.goto('http://localhost:5173/auditor/overview');

    await page.getByRole('button', { name: 'Run Verification' }).click();
    await expect(page.getByText('Verification Incomplete')).toBeVisible();
    await expect(page.getByText('3/4 verified')).toBeVisible();
    await expect(page.getByText('Tampering Detected')).toHaveCount(0);
  });

  test('Forensic Evidence page input formatting and layout', async ({ page }) => {
    await page.goto('http://localhost:5173/auditor/forensic-evidence');
    await page.waitForLoadState('networkidle');

    // Page title and description
    await expect(page.locator('h1', { hasText: 'Forensic Evidence & Selective Merkle Capsules' })).toBeVisible();

    // Sequence ID input verification
    const seqInput = page.locator('input[type="number"]');
    await expect(seqInput).toBeVisible();

    // Verify computed styles: dark background and light text (no white box bug)
    const bgColor = await seqInput.evaluate((el) => window.getComputedStyle(el).backgroundColor);
    const textColor = await seqInput.evaluate((el) => window.getComputedStyle(el).color);
    
    // Keep the control dark and the foreground bright across browser autofill states.
    const channelMean = (color: string) => {
      const values = color.match(/[\d.]+/g)?.map(Number) ?? [];
      return values.slice(0, 3).reduce((total, value) => total + value, 0) / 3;
    };
    expect(channelMean(bgColor)).toBeLessThan(80);
    expect(channelMean(textColor)).toBeGreaterThan(180);

    // Action buttons
    const genProofBtn = page.locator('button', { hasText: 'Generate Merkle Proof' });
    const downloadCapsuleBtn = page.locator('button', { hasText: 'Download .arguscap' });

    await expect(genProofBtn).toBeVisible();
    await expect(downloadCapsuleBtn).toBeVisible();

    // Form allows entering a new sequence ID
    await seqInput.fill('42');
    await expect(seqInput).toHaveValue('42');
  });

  test('Forensic capsule export completes with the server filename', async ({ page }) => {
    await page.route('**/audit-logs/125/capsule', (route) => route.fulfill({
      status: 200,
      contentType: 'application/vnd.argus.capsule',
      headers: { 'Content-Disposition': 'attachment; filename="proof_seq125.arguscap"' },
      body: 'argus-capsule-test-payload',
    }));
    await page.goto('http://localhost:5173/auditor/forensic-evidence');
    await page.locator('input[type="number"]').fill('125');

    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Download .arguscap' }).click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toBe('proof_seq125.arguscap');
    await expect(page.getByRole('status').getByText('Download started: proof_seq125.arguscap')).toBeVisible();
  });

  test('Counterfactual Simulator page rendering', async ({ page }) => {
    await page.goto('http://localhost:5173/auditor/counterfactual');
    await page.waitForLoadState('networkidle');

    // Heading
    await expect(page.locator('h1', { hasText: 'Counterfactual "What-If" Provenance Replay' })).toBeVisible();

    // Control panel labels
    await expect(page.locator('label', { hasText: 'Target Personnel' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Choose events to exclude' })).toBeVisible();
    await expect(page.getByPlaceholder('Find event')).toHaveValue('');
    await expect(page.getByRole('checkbox', { name: 'Exclude sequence 142', exact: true })).toBeVisible();
  });

  for (const liveRecordAvailable of [true, false]) {
    test(`time travel compares an exact employee outside the first 100: available=${liveRecordAvailable}`, async ({ page }) => {
      const employee = { employee_id: 101, full_name: 'QA Current Name', email: 'qa101@example.com',
        role_title: 'Analyst', department_name: 'Compliance', salary: 975000,
        date_hired: '2024-01-01T00:00:00', is_active: true, pii_redacted: false };
      let exactRequests = 0;
      await page.route('**/api/employees?**', async (route) => {
        const url = new URL(route.request().url());
        const exact = url.searchParams.get('employee_id') === '101';
        if (exact) { exactRequests++; expect(url.searchParams.has('search')).toBe(false); }
        const items = exact ? liveRecordAvailable ? [employee] : [] : Array.from({ length: 100 }, (_, index) => ({ ...employee, employee_id: index + 1 }));
        await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items, total: exact ? items.length : 101, page: 1, pages: exact ? 1 : 2 }) });
      });
      await page.route('**/api/employees/101/time-travel?**', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ ...employee,
        full_name: 'QA Historical Name', role_title: 'Lead', as_of: '2026-10-15T00:00:00Z', sequence_id: 207 }) }));
      await page.goto('/auditor/time-travel?emp_id=101&as_of=2026-10-15T00%3A00%3A00Z&seq=207');
      await expect(page.getByRole('heading', { name: 'State Reconstructed Successfully' })).toBeVisible();
      await expect(page.getByText(liveRecordAvailable ? 'Past Delta Detected' : 'Live comparison unavailable', { exact: true })).toBeVisible();
      await expect(page.getByText('Matches Live State', { exact: true })).toHaveCount(0);
      expect(exactRequests).toBeGreaterThan(0);
    });
  }

  test('Counterfactual can select personnel beyond the preloaded directory by ID', async ({ page }) => {
    await page.goto('http://localhost:5173/auditor/counterfactual');
    await expect(page.getByRole('combobox')).toHaveValue('1001');
    await page.getByLabel('Employee ID', { exact: true }).fill('9001');
    const requested = page.waitForRequest((request) => {
      const url = new URL(request.url());
      return url.pathname.endsWith('/audit-logs') && url.searchParams.get('employee_id') === '9001';
    });
    await page.getByRole('button', { name: 'Use employee ID', exact: true }).click();
    await requested;
    await expect(page.getByRole('combobox')).toHaveValue('9001');
    await expect(page.getByText(/events for Employee #9001/)).toBeVisible();
    await page.getByLabel('Employee ID', { exact: true }).fill('0');
    await expect(page.getByRole('button', { name: 'Use employee ID', exact: true })).toBeDisabled();
  });

  test('Counterfactual replay requires a selected audit event before calling the API', async ({ page }) => {
    let simulationRequests = 0;
    page.on('request', (request) => {
      if (new URL(request.url()).pathname.endsWith('/audit-logs/counterfactual')) {
        simulationRequests += 1;
      }
    });

    await page.goto('http://localhost:5173/auditor/counterfactual');
    await expect(page.getByRole('checkbox', { name: 'Exclude sequence 142', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Run Provenance Simulation' })).toBeDisabled();
    expect(simulationRequests).toBe(0);
  });

  test('Counterfactual salary results are formatted in INR', async ({ page }) => {
    let submittedPayload: unknown;
    await page.route('**/api/audit-logs/counterfactual', async (route) => {
      submittedPayload = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          employee_id: 1001,
          as_of: new Date().toISOString(),
          skip_sequence_ids: [142],
          actual_state: { salary: 900000 },
          counterfactual_state: { salary: 800000 },
          blast_radius: {
            salary_actual: 900000,
            salary_counterfactual: 800000,
            salary_overpaid_annual: 100000,
            salary_overpaid_cumulative: 50000,
            tenure_months: 6,
            skipped_events_count: 1,
            skipped_sequence_ids: [142],
          },
          skipped_events: [],
          applied_events_count: 4,
          simulation_duration_ms: 2,
        }),
      });
    });

    await page.goto('http://localhost:5173/auditor/counterfactual');
    await expect(page.getByRole('combobox')).toHaveValue('1001');
    await page.getByRole('checkbox', { name: 'Exclude sequence 142', exact: true }).check();
    await expect(page.getByRole('button', { name: 'Run Provenance Simulation' })).toBeDisabled();
    await page.getByRole('checkbox', { name: /Reveal employee and salary details in the replay/ }).check();
    await page.getByRole('button', { name: 'Run Provenance Simulation' }).click();
    await expect(page.getByText('₹1,00,000.00')).toBeVisible();
    await expect(page.getByText('$100,000.00')).toHaveCount(0);
    expect(submittedPayload).toMatchObject({ employee_id: 1001, skip_sequence_ids: [142], include_pii: true });
  });

  test('Audit Chain Explorer page rendering', async ({ page }) => {
    await page.goto('http://localhost:5173/auditor/chain');
    await page.waitForLoadState('networkidle');

    // Search input
    const searchInput = page.locator('input#audit-chain-seq-search');
    await expect(searchInput).toBeVisible();
  });
});
