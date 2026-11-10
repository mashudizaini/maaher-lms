import { execFileSync } from 'node:child_process';
import { test, expect } from '@playwright/test';

test('Auth0 OIDC browser flow uses the callback cookie, opaque session and tenant permissions', async ({ page, context }) => {
  const account = JSON.parse(execFileSync(process.env.LMS_TEST_PYTHON!,
    [`${process.env.LMS_TEST_ROOT}/scripts/lms01-browser-fixtures.py`, 'oidc-seed'],
    { input: '{}', encoding: 'utf8' }));
  await page.route('https://browser-tests.us.auth0.com/authorize*', async route => {
    const authorize = new URL(route.request().url());
    expect(authorize.searchParams.get('code_challenge_method')).toBe('S256');
    expect(authorize.searchParams.get('redirect_uri')).toBe(`${process.env.APP_ORIGIN}/api/auth/oidc/callback`);
    const callback = new URL(authorize.searchParams.get('redirect_uri')!);
    const state = authorize.searchParams.get('state')!;
    callback.searchParams.set('state', state); callback.searchParams.set('code', state);
    await route.fulfill({ status: 302, headers: { location: callback.toString() } });
  });
  await page.goto('/auth');
  await expect(page.getByRole('button', { name: 'Masuk dengan Auth0', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Masuk dengan Auth0', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Berhasil masuk melalui Auth0');
  await expect(page).toHaveURL(`${process.env.APP_ORIGIN}/auth`);
  await expect(page.getByRole('heading', { name: 'Keamanan akun organisasi' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Minta verifikasi operator' })).toHaveCount(0);
  const session = (await context.cookies()).find(cookie => cookie.name === 'maaher_session')!;
  expect(session.httpOnly).toBe(true); expect(session.sameSite).toBe('Lax');
  expect(session.value).not.toContain('.');
  expect((await context.cookies()).some(cookie => cookie.name === 'maaher_oidc_flow')).toBe(false);
  await page.getByRole('button', { name: 'Gunakan organisasi', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Organisasi dipilih');
  const self = await context.request.get('/api/auth/me', { headers: { 'x-tenant-id': account.tenant } });
  expect(self.status()).toBe(200); expect((await self.json()).role).toBe('admin');
  await page.getByRole('button', { name: 'Keluar', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Berhasil keluar');
  expect((await context.request.get('/api/auth/me', { headers: { 'x-tenant-id': account.tenant } })).status()).toBe(401);
});
