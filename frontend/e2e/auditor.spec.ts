import { test, expect } from '@playwright/test';

test.describe('Compliance Auditor Portal E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Inject E2E role for Compliance Auditor
    await page.addInitScript(() => {
      (window as any).__E2E_ROLE__ = 'compliance_auditor';
    });
  });

  test('Auditor portal navigation and layout rendering', async ({ page }) => {
    await page.goto('http://localhost:5173/auditor/overview');
    await page.waitForLoadState('networkidle');

    // Auditor header status pill
    const poolBadge = page.locator('text=Pool: compliance_auditor');
    await expect(poolBadge).toBeVisible();

    // Sidebar navigation links (scoped to aside to avoid duplicate in-page action links)
    await expect(page.locator('aside a[href="/auditor/overview"]')).toBeVisible();
    await expect(page.locator('aside a[href="/auditor/chain"]')).toBeVisible();
    await expect(page.locator('aside a[href="/auditor/log"]')).toBeVisible();
    await expect(page.locator('aside a[href="/auditor/time-travel"]')).toBeVisible();
    await expect(page.locator('aside a[href="/auditor/counterfactual"]')).toBeVisible();
    await expect(page.locator('aside a[href="/auditor/forensic-evidence"]')).toBeVisible();
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
    
    // rgb(20, 21, 22) corresponds to #141516 (linear-surface-2)
    expect(bgColor).toBe('rgb(20, 21, 22)');
    // rgb(247, 248, 248) corresponds to #f7f8f8 (linear-ink)
    expect(textColor).toBe('rgb(247, 248, 248)');

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
