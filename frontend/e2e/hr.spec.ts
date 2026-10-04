import { test, expect } from '@playwright/test';

test.describe('HR Admin Portal E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Inject E2E role for HR Admin
    await page.addInitScript(() => {
      (window as any).__E2E_ROLE__ = 'hr_admin';
    });
  });

  test('HR Dashboard layout and navigation links', async ({ page }) => {
    await page.goto('http://localhost:5173/hr/dashboard');
    await page.waitForLoadState('networkidle');

    // Sidebar navigation links
    await expect(page.locator('aside a[href="/hr/dashboard"]')).toBeVisible();
    await expect(page.locator('aside a[href="/hr/employees"]')).toBeVisible();
    await expect(page.locator('aside a[href="/hr/settings"]')).toBeVisible();

    // HR dashboard sections
    await expect(page.locator('h1', { hasText: 'Workforce Overview' })).toBeVisible();
  });

  test('Employee Directory search and modal triggers', async ({ page }) => {
    await page.goto('http://localhost:5173/hr/employees');
    await page.waitForLoadState('networkidle');

    // Heading
    await expect(page.locator('h1', { hasText: 'Workforce Directory' })).toBeVisible();

    // Search and filter inputs
    const searchInput = page.locator('input[placeholder*="Search"]');
    await expect(searchInput).toBeVisible();

    // Add Personnel button
    const addBtn = page.locator('button', { hasText: 'Add Personnel' });
    await expect(addBtn).toBeVisible();

    // Clicking Add Personnel opens modal
    await addBtn.click();
    const modalHeading = page.locator('text=Register Personnel');
    await expect(modalHeading).toBeVisible();

    // Close modal
    const closeBtn = page.locator('button', { hasText: 'Cancel' }).or(page.locator('button[aria-label="Close dialog"]'));
    if (await closeBtn.first().isVisible()) {
      await closeBtn.first().click();
    }
  });

  test('HR Settings page rendering', async ({ page }) => {
    await page.goto('http://localhost:5173/hr/settings');
    await page.waitForLoadState('networkidle');

    // Settings header
    await expect(page.locator('h1', { hasText: 'Security & Access Management' })).toBeVisible();
  });
});
