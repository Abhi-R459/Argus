import { test, expect } from '@playwright/test';
import { mockArgusApi } from './fixtures/argus-api';

test.describe('Compliance Auditor Portal E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Inject E2E role for Compliance Auditor
    await page.addInitScript(() => {
      (window as any).__E2E_ROLE__ = 'compliance_auditor';
    });
    await mockArgusApi(page);
  });

  test('Auditor portal navigation and layout rendering', async ({ page }) => {
    await page.goto('http://localhost:5173/auditor/overview');
    await page.waitForLoadState('networkidle');

    // Auditor header status pill
    const poolBadge = page.locator('text=Pool: compliance_auditor');
    await expect(poolBadge).toBeVisible();
    await expect(page.getByText('Verification Complete', { exact: true })).toBeVisible();
    await expect(page.getByText('Unverified')).toBeVisible();
    await expect(page.getByText(/do not represent independent trust domains/i)).toBeVisible();

    // Sidebar navigation links (scoped to aside to avoid duplicate in-page action links)
    await expect(page.locator('aside a[href="/auditor/overview"]')).toBeVisible();
    await expect(page.locator('aside a[href="/auditor/chain"]')).toBeVisible();
    await expect(page.locator('aside a[href="/auditor/log"]')).toBeVisible();
    await expect(page.locator('aside a[href="/auditor/time-travel"]')).toBeVisible();
    await expect(page.locator('aside a[href="/auditor/counterfactual"]')).toBeVisible();
    await expect(page.locator('aside a[href="/auditor/forensic-evidence"]')).toBeVisible();
  });

  test('Auditor verification and risk refresh update the dashboard data', async ({ page }) => {
    await page.goto('http://localhost:5173/auditor/overview');
    await expect(page.getByText('1 pending flag', { exact: true })).toBeVisible();

    const verificationRequest = page.waitForRequest((request) =>
      new URL(request.url()).pathname.endsWith('/verify') && request.method() === 'POST'
    );
    await page.getByRole('button', { name: 'Re-run (Re-run chain verification)' }).click();
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

  test('Auditor risk refresh failure is visible and flags stay unreviewed', async ({ page }) => {
    await page.route('**/api/suspicious-activity/refresh', (route) =>
      route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ detail: 'Already running' }) })
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
          verification_checks: { hash_chain: 'pass', external_anchor: 'pass', checkpoint_signatures: 'unknown' },
        }),
      })
    );
    await page.goto('http://localhost:5173/auditor/overview');

    await expect(page.getByText('Verification Incomplete')).toBeVisible();
    await expect(page.getByText('2/3 verified')).toBeVisible();
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

  test('Counterfactual Simulator page rendering', async ({ page }) => {
    await page.goto('http://localhost:5173/auditor/counterfactual');
    await page.waitForLoadState('networkidle');

    // Heading
    await expect(page.locator('h1', { hasText: 'Counterfactual "What-If" Provenance Replay' })).toBeVisible();

    // Control panel labels
    await expect(page.locator('label', { hasText: 'Target Personnel' })).toBeVisible();
    await expect(page.locator('label', { hasText: 'Exclude Sequence IDs' })).toBeVisible();
  });

  test('Audit Chain Explorer page rendering', async ({ page }) => {
    await page.goto('http://localhost:5173/auditor/chain');
    await page.waitForLoadState('networkidle');

    // Search input
    const searchInput = page.locator('input#audit-chain-seq-search');
    await expect(searchInput).toBeVisible();
  });
});
