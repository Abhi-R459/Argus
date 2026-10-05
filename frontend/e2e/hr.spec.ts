import { test, expect } from '@playwright/test';
import { mockArgusApi } from './fixtures/argus-api';

test.describe('HR Admin Portal E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Inject E2E role for HR Admin
    await page.addInitScript(() => {
      (window as any).__E2E_ROLE__ = 'hr_admin';
    });
    await mockArgusApi(page);
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
    await expect(page.getByText('66', { exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Recent Personnel Activity' })).toBeVisible();
  });

  test('HR dashboard refresh calls the workforce stats API', async ({ page }) => {
    await page.goto('http://localhost:5173/hr/dashboard');
    await expect(page.getByText('66', { exact: true })).toBeVisible();

    const refreshRequest = page.waitForRequest((request) =>
      new URL(request.url()).pathname.endsWith('/dashboard/stats') && request.method() === 'GET'
    );
    await page.getByRole('button', { name: 'Refresh (Refresh workforce metrics)' }).click();
    await refreshRequest;
  });

  test('HR dashboard shows a visible error when refresh fails', async ({ page }) => {
    await page.route('**/api/dashboard/stats', (route) =>
      route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Unavailable' }) })
    );
    await page.goto('http://localhost:5173/hr/dashboard');

    await page.getByRole('button', { name: 'Refresh (Refresh workforce metrics)' }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Refresh workforce metrics failed. Try again.' })).toBeVisible();
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

  test('HR mobile navigation opens and closes after route change', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('http://localhost:5173/hr/dashboard');

    const menuButton = page.getByRole('button', { name: 'Toggle navigation menu' });
    await expect(menuButton).toHaveAttribute('aria-expanded', 'false');
    await menuButton.click();
    await expect(menuButton).toHaveAttribute('aria-expanded', 'true');

    const settingsLink = page.locator('#hr-primary-navigation a[href="/hr/settings"]');
    await expect(settingsLink).toBeVisible();
    await settingsLink.click();

    await expect(page).toHaveURL(/\/hr\/settings$/);
    await expect(menuButton).toHaveAttribute('aria-expanded', 'false');
    await expect(page.locator('h1', { hasText: 'Security & Access Management' })).toBeVisible();
  });
});
