import { test, expect } from '@playwright/test';

test.describe('Authentication & Route Protection', () => {
  test('Landing page renders Argus branding', async ({ page }) => {
    await page.goto('http://localhost:5173/');
    await page.waitForLoadState('networkidle');

    // Title should contain Argus
    await expect(page).toHaveTitle(/Argus/);

    // Header branding should be present
    const brandHeading = page.locator('h1', { hasText: 'Argus Audit Engine' });
    await expect(brandHeading).toBeVisible();

    const subtitle = page.locator('p', { hasText: 'Sign in or create an account to access your dashboard' });
    await expect(subtitle).toBeVisible();
  });

  test('New account entry leads to sign-up before role choice', async ({ page }) => {
    await page.goto('http://localhost:5173/');
    await page.getByRole('link', { name: 'Create an account' }).click();

    await expect(page).toHaveURL(/\/sign-up$/);
    await expect(page.getByRole('heading', { name: 'Create your Argus account' })).toBeVisible();
    await expect(page.getByText('You will choose Auditor or HR next.', { exact: false })).toBeVisible();
  });

  test('Unauthenticated user cannot access protected HR routes', async ({ page }) => {
    await page.goto('http://localhost:5173/hr/dashboard');
    await page.waitForLoadState('networkidle');

    // Should not render HR dashboard internal controls
    const hrContent = page.locator('text=Workforce Overview');
    await expect(hrContent).not.toBeVisible();
  });

  test('Unauthenticated user cannot access protected Auditor routes', async ({ page }) => {
    await page.goto('http://localhost:5173/auditor/overview');
    await page.waitForLoadState('networkidle');

    // Should not render Auditor sidebar or internal panels
    const auditorContent = page.locator('text=Cryptographic Anchor State');
    await expect(auditorContent).not.toBeVisible();
  });
});
