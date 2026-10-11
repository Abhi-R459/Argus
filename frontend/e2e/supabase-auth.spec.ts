import { test, expect } from '@playwright/test';
import { mockArgusApi } from './fixtures/argus-api';

const host = 'https://abcdefghijklmnopqrst.supabase.co';
const storageKey = 'sb-abcdefghijklmnopqrst-auth-token';

test('Google sign-in uses PKCE and the exact application callback', async ({ page }) => {
  await page.route(host + '/auth/v1/authorize**', route => route.fulfill({ body: 'Google login handoff' }));
  await page.goto('/');
  await page.getByRole('button', { name: 'Continue with Google' }).click();
  await page.waitForURL(host + '/auth/v1/authorize**');
  const url = new URL(page.url());
  expect(url.searchParams.get('provider')).toBe('google');
  expect(url.searchParams.get('redirect_to')).toBe('http://localhost:5173/auth/callback');
  expect(url.searchParams.get('code_challenge_method')).toBe('s256');
  expect(url.searchParams.get('code_challenge')).toMatch(/^[A-Za-z0-9_-]{43}$/);
});

test('OAuth errors are redacted and removed from browser history', async ({ page }) => {
  await page.goto('/auth/callback?error=access_denied&error_description=private-provider-message');
  await expect(page.getByRole('button', { name: 'Continue with Google' })).toBeVisible();
  await expect(page.getByRole('alert')).toHaveText('Sign-in could not be completed. Please try again.');
  await expect(page).toHaveURL('http://localhost:5173/');
  await expect(page.getByText('private-provider-message')).not.toBeVisible();
});

test('A restored session uses server permissions and sign-out removes its workspace', async ({ page }) => {
  await page.addInitScript(({ key }) => {
    const expires = Math.floor(Date.now() / 1000) + 3600;
    const user = { id: '1ac1a96e-09fb-4dc8-a34a-cc2ac0dbe699', aud: 'authenticated', role: 'authenticated',
      email: 'hr@example.test', app_metadata: { provider: 'google' }, user_metadata: {}, identities: [], created_at: new Date().toISOString() };
    const token = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' })) + '.' +
      btoa(JSON.stringify({ sub: user.id, exp: expires, iat: expires - 3600, role: 'authenticated' })) + '.inert_test_signature';
    localStorage.setItem(key, JSON.stringify({ access_token: token, refresh_token: 'inert_test_refresh',
      token_type: 'bearer', expires_in: 3600, expires_at: expires, user }));
  }, { key: storageKey });
  await mockArgusApi(page);
  await page.route('**/api/auth/me', route => route.fulfill({ json: {
    user_id: 1, auth_user_id: 'supabase:1ac1a96e-09fb-4dc8-a34a-cc2ac0dbe699', email: 'hr@example.test',
    full_name: 'Approved HR', role: 'hr_admin', is_active: true,
  } }));
  let signedOut = false;
  await page.route(host + '/auth/v1/logout**', route => {
    signedOut = new URL(route.request().url()).searchParams.get('scope') === 'local';
    return route.fulfill({ status: 204 });
  });
  await page.goto('/');
  await expect(page).toHaveURL(/\/hr\/dashboard$/);
  await expect(page.getByText('Workforce Overview', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Continue with Google' })).toBeVisible();
  await expect(page.getByText('Workforce Overview', { exact: true })).not.toBeVisible();
  expect(signedOut).toBe(true);
  expect(await page.evaluate(key => localStorage.getItem(key), storageKey)).toBeNull();
});
