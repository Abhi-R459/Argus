import { test, expect } from '@playwright/test';

test.describe('Authentication & Route Protection', () => {
  test('Landing page renders Argus branding and Clerk sign-in', async ({ page }) => {
    await page.goto('http://localhost:5173/');
    await page.waitForLoadState('networkidle');

    // Title should contain Argus
    await expect(page).toHaveTitle(/Argus/);

    // Header branding should be present
    const brandHeading = page.locator('h1', { hasText: 'Argus Audit Engine' });
    await expect(brandHeading).toBeVisible();

    const subtitle = page.locator('p', { hasText: 'Sign in to access your dashboard' });
    await expect(subtitle).toBeVisible();
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
