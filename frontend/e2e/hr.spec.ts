import { test, expect } from '@playwright/test';
import { mockArgusApi } from './fixtures/argus-api';

test.describe('HR Admin Portal E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Inject E2E role for HR Admin
    await page.addInitScript(() => {
      (window as Window & { __E2E_ROLE__?: string }).__E2E_ROLE__ = 'hr_admin';
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

  test('salary adjustment refreshes the open employee details and states PII protection accurately', async ({ page }) => {
    await page.goto('http://localhost:5173/hr/employees');
    await page.getByRole('row', { name: /M Maya Rao #1001/ })
      .getByRole('button', { name: 'Adjust compensation for Maya Rao' })
      .click();

    await expect(page.getByText('Current annual compensation')).toBeVisible();
    await expect(page.getByRole('dialog').getByText('₹7,80,000', { exact: true })).toBeVisible();
    await page.locator('input[type="number"]').fill('1000000');
    await page.getByRole('button', { name: 'Record Salary Adjustment' }).click();

    await expect(page.getByText('Compensation adjustment validated and recorded to immutable ledger.')).toBeVisible();
    await expect(page.getByRole('dialog').getByText('₹10,00,000', { exact: true })).toBeVisible();
    await expect(page.getByRole('dialog').getByText('Sensitive fields encrypted')).toBeVisible();
    await expect(page.getByRole('dialog').getByText(/Employee names and work email addresses remain plaintext/)).toBeVisible();
  });

  test('HR Settings page rendering', async ({ page }) => {
    await page.goto('http://localhost:5173/hr/settings');
    await page.waitForLoadState('networkidle');

    // Settings header
    await expect(page.locator('h1', { hasText: 'Security & Access Management' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Create checkpoint now' })).toBeVisible();
  });

  test('profile edits can keep the current role and retain blank contact details', async ({ page }) => {
    let submitted: Record<string, unknown> | undefined;
    await page.route('**/api/employees/1001', async (route) => {
      submitted = route.request().postDataJSON();
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ employee_id: 1001 }) });
    });
    await page.goto('http://localhost:5173/hr/employees');
    await page.getByRole('button', { name: 'Edit profile for Maya Rao' }).first().click();
    await page.getByPlaceholder('Full Name', { exact: true }).fill('Maya Rao Updated');
    await page.getByRole('button', { name: 'Save Profile Changes' }).click();
    await expect(page.getByText('Profile updated and cryptographically hashed into audit trail.')).toBeVisible();
    expect(submitted).toEqual({ full_name: 'Maya Rao Updated' });
  });

  test('registration states sensitive-field encryption accurately', async ({ page }) => {
    await page.goto('http://localhost:5173/hr/employees');
    await page.getByRole('button', { name: 'Add Personnel' }).click();
    const dialog = page.getByRole('dialog', { name: 'Register Personnel' });
    await expect(dialog.getByText('Encrypted at rest', { exact: true })).toHaveCount(2);
    await expect(dialog.getByText('Encryption not configured')).toHaveCount(0);
    await expect(dialog.getByText(/Names and work email addresses remain plaintext/)).toBeVisible();
  });

  test('HR can bootstrap a department and job role without demo data', async ({ page }) => {
    const departments: { department_id: number; name: string }[] = [];
    await page.route('**/api/departments', async (route) => {
      if (route.request().method() === 'POST') {
        const body = route.request().postDataJSON() as { name: string };
        departments.push({ department_id: 42, name: body.name });
        await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(departments[0]) });
      } else {
        await route.fulfill({ contentType: 'application/json', body: JSON.stringify(departments) });
      }
    });
    let submittedRole: unknown;
    await page.route('**/api/roles', async (route) => {
      submittedRole = route.request().postDataJSON();
      await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ role_id: 9 }) });
    });
    await page.goto('http://localhost:5173/hr/settings');
    await expect(page.getByRole('button', { name: 'Create job role' })).toBeDisabled();
    await page.getByLabel('Department name').fill('Operations');
    await page.getByRole('button', { name: 'Create department', exact: true }).click();
    await expect(page.getByText('Department created.', { exact: true })).toBeVisible();
    await page.getByLabel('Job title').fill('Operations Analyst');
    await page.getByLabel('Department', { exact: true }).selectOption('42');
    await page.getByLabel('Minimum annual salary (₹)').fill('400000');
    await page.getByLabel('Maximum annual salary (₹)').fill('800000');
    await page.getByRole('button', { name: 'Create job role' }).click();
    await expect(page.getByText('Job role created. You can now add employees with this role.')).toBeVisible();
    expect(submittedRole).toMatchObject({ title: 'Operations Analyst', department_id: 42,
      salary_band_min: '400000', salary_band_max: '800000' });
  });

  test('HR Admin can create a checkpoint and sees its signed range', async ({ page }) => {
    await page.goto('http://localhost:5173/hr/settings');

    const requestPromise = page.waitForRequest((request) =>
      new URL(request.url()).pathname.endsWith('/checkpoints/create') && request.method() === 'POST'
    );
    await page.getByRole('button', { name: 'Create checkpoint now' }).click();
    const request = await requestPromise;

    expect(request.postData()).toBeNull();
    await expect(page.getByRole('status').filter({ hasText: 'Checkpoint #7 created and signed.' })).toBeVisible();
    await expect(page.getByText(/Sealed 12 audit events through sequence #142/)).toBeVisible();
    await expect(page.getByText(/No external anchor was created/)).toBeVisible();
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
