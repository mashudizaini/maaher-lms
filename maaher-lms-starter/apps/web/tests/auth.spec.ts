import { execFileSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { test, expect, Page } from '@playwright/test';

test('staff login is explicit and unavailable until the provider is configured', async ({ page, request, context }) => {
  await page.goto('/auth');
  await expect(page.getByRole('button', { name: 'Masuk dengan Auth0', exact: true })).toBeDisabled();
  await expect(page.getByText('Login staff belum diaktifkan.')).toBeVisible();
  const result = await request.post('/api/auth/oidc/login', { headers: { origin: process.env.APP_ORIGIN! }, data: {} });
  expect(result.status()).toBe(503);
  expect((await context.cookies()).some(cookie => cookie.name === 'maaher_oidc_flow')).toBe(false);
});

test('OIDC callback rejects untrusted query fields and redirects to a fixed clean URL', async ({ request }) => {
  const callback = '/api/auth/oidc/callback';
  expect((await request.get(`${callback}?state=one&state=two&code=private`, { maxRedirects: 0 })).status()).toBe(400);
  expect((await request.get(`${callback}?return_to=https://evil.invalid`, { maxRedirects: 0 })).status()).toBe(400);
  const result = await request.get(`${callback}?state=synthetic-state-value-long&code=private-code`, { maxRedirects: 0 });
  expect(result.status()).toBe(303);
  expect(result.headers()['location']).toBe(`${process.env.APP_ORIGIN}/auth?oidc=failed`);
  expect(result.headers()['location']).not.toContain('private-code');
});

function fixture(operation: string, payload: object = {}) {
  return JSON.parse(execFileSync(process.env.LMS_TEST_PYTHON!,
    [`${process.env.LMS_TEST_ROOT}/scripts/lms01-browser-fixtures.py`, operation],
    { input: JSON.stringify(payload), encoding: 'utf8' }));
}

async function login(page: Page, email: string, password: string) {
  const section = page.getByRole('region', { name: 'Masuk', exact: true });
  await section.getByLabel('Email', { exact: true }).fill(email);
  await section.getByLabel('Kata sandi', { exact: true }).fill(password);
  await section.getByRole('button', { name: 'Masuk', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Berhasil masuk');
}

async function setupMfa(page: Page, password: string, purpose = 'bootstrap', replacement?: string) {
  await page.getByLabel('Jenis permintaan', { exact: true }).selectOption(purpose);
  await page.getByRole('button', { name: 'Minta verifikasi operator' }).click();
  const requestId = page.getByLabel('ID permintaan operator');
  await expect(requestId).toBeVisible();
  const proof = fixture('authorize', { request_id: await requestId.inputValue() });
  await page.getByLabel('Konfirmasi kata sandi').fill(password);
  await page.getByLabel('Kode otorisasi operator').fill(proof.authorization);
  if (replacement) await page.getByLabel('Kata sandi pengganti untuk pemulihan MFA').fill(replacement);
  await page.getByRole('button', { name: 'Siapkan MFA', exact: true }).click();
  const setup = page.getByLabel('Kunci penyiapan rahasia');
  await expect(setup).toBeVisible();
  const uri = await setup.inputValue();
  const otp = fixture('totp', { uri });
  await page.getByLabel('Kode autentikator').fill(otp.code);
  await page.getByRole('button', { name: 'Verifikasi MFA', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('MFA berhasil diverifikasi');
  return uri;
}

test('admin MFA, invitation, own memberships, logout and reset through browser/BFF', async ({ page, context }) => {
  const account = fixture('seed');
  await page.goto('/auth');
  await expect(page.locator('html')).toHaveAttribute('lang', 'id');
  await login(page, account.email, account.password);
  await expect(page.getByRole('button', { name: 'Gunakan organisasi' })).toBeDisabled();
  await setupMfa(page, account.password);
  await page.getByRole('button', { name: 'Gunakan organisasi' }).click();
  await expect(page.getByRole('heading', { name: 'Keanggotaan organisasi' })).toBeVisible();
  const invited = `${randomUUID()}@example.invalid`;
  await page.getByLabel('Email undangan').fill(invited);
  await page.getByLabel('Peran', { exact: true }).selectOption('student');
  await page.getByRole('button', { name: 'Kirim undangan', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('antrean pengiriman');
  const invitation = fixture('token', { email: invited, kind: 'invitation' });
  await page.getByRole('button', { name: 'Keluar', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Berhasil keluar');
  await page.goto(`/auth#invitation=${invitation.token}`);
  await expect(page.getByRole('heading', { name: 'Terima undangan' })).toBeVisible();
  await expect(page).toHaveURL(/\/auth$/);
  await page.getByLabel('Kata sandi akun baru').fill(account.password);
  await page.getByRole('button', { name: 'Terima undangan', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Undangan diterima');
  await login(page, invited, account.password);
  await page.getByRole('button', { name: 'Gunakan organisasi' }).click();
  await expect(page.getByRole('status')).toContainText('Organisasi dipilih');
  const cookie = (await context.cookies()).find(row => row.name === 'maaher_session')!;
  expect(cookie.httpOnly).toBeTruthy(); expect(cookie.sameSite).toBe('Lax');
  await page.getByLabel('Email pemulihan').fill(invited);
  await page.getByRole('button', { name: 'Kirim petunjuk pemulihan' }).click();
  await expect(page.getByRole('status')).toContainText('Jika akun tersedia');
  const reset = fixture('token', { email: invited, kind: 'password-reset' });
  await page.goto(`/auth#password-reset=${reset.token}`);
  await expect(page.getByLabel('Kata sandi baru', { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/\/auth$/);
  const replacement = 'Replacement synthetic password 123!';
  await page.getByLabel('Kata sandi baru', { exact: true }).fill(replacement);
  await page.getByRole('button', { name: 'Simpan kata sandi baru' }).click();
  await expect(page.getByRole('status')).toContainText('Kata sandi diperbarui');
  const expired = await context.request.get('/api/auth/me', { headers: { 'x-tenant-id': account.tenant } });
  expect(expired.status()).toBe(401);
  await login(page, invited, replacement);
});

test('BFF rejects foreign/missing Origin, arbitrary paths and oversized bodies', async ({ request }) => {
  const path = '/api/auth/password-reset/request';
  expect((await request.post(path, { data: { email: 'nobody@example.invalid' } })).status()).toBe(403);
  expect((await request.post(path, { headers: { origin: 'https://evil.invalid' }, data: {} })).status()).toBe(403);
  expect((await request.get('/api/auth/../../healthz')).status()).toBe(404);
  expect((await request.get('/api/auth/not-allowed')).status()).toBe(404);
  expect((await request.post(path, { headers: { origin: process.env.APP_ORIGIN! }, data: 'x'.repeat(17000) })).status()).toBe(413);
  const page = await request.get('/auth');
  expect(page.headers()['referrer-policy']).toBe('no-referrer');
  expect(page.headers()['cache-control']).toContain('no-store');
});


test('strict nonce CSP and HSTS cover pages and BFF; injected inline script is blocked', async ({ page, request }) => {
  const first = await request.get('/auth');
  const second = await request.get('/auth');
  const csp = first.headers()['content-security-policy'];
  expect(csp).toContain("object-src 'none'");
  expect(csp).toContain("frame-ancestors 'none'");
  expect(csp).not.toContain('unsafe-inline');
  expect(csp).not.toContain('unsafe-eval');
  expect(csp).not.toBe(second.headers()['content-security-policy']);
  for (const path of ['/', '/auth', '/api/auth/memberships']) {
    const response = await request.get(path);
    expect(response.headers()['strict-transport-security']).toContain('max-age=31536000');
    expect(response.headers()['content-security-policy']).toContain('nonce-');
    expect(response.headers()['x-frame-options']).toBe('DENY');
  }
  // Inject into parser-delivered HTML, not a DevTools evaluate script context.
  // Keep the server's CSP untouched; both a violation and non-execution are required.
  await page.addInitScript(() => {
    Object.assign(window, { __cspViolation: false });
    document.addEventListener('securitypolicyviolation', () => Object.assign(window, { __cspViolation: true }));
  });
  await page.route('**/auth', async route => {
    const response = await route.fetch();
    const body = (await response.text()).replace('</head>', '<script>window.__untrustedScriptRan = true</script></head>');
    await route.fulfill({ response, body });
  });
  await page.goto('/auth');
  await expect(page.getByRole('heading', { name: 'Akun Maaher LMS' })).toBeVisible();
  const allowed = await page.locator('script').evaluateAll(nodes => nodes.filter(node => (node as HTMLScriptElement).nonce).length);
  expect(allowed).toBeGreaterThan(0);
  await expect.poll(() => page.evaluate(() => Reflect.get(window, '__cspViolation'))).toBe(true);
  expect(await page.evaluate(() => Object.hasOwn(window, '__untrustedScriptRan'))).toBe(false);

});


test('admin discovers members by email, changes role and revokes without database IDs', async ({ page }) => {
  const account = fixture('seed');
  const member = fixture('member', { tenant: account.tenant });
  await page.goto('/auth');
  await login(page, account.email, account.password);
  await setupMfa(page, account.password);
  await page.getByRole('button', { name: 'Gunakan organisasi' }).click();
  await expect(page.getByRole('heading', { name: 'Keanggotaan organisasi' })).toBeVisible();
  await page.getByRole('button', { name: 'Muat anggota organisasi', exact: true }).click();
  const row = page.getByRole('row').filter({ hasText: member.email });
  await expect(row).toBeVisible();
  await row.getByRole('combobox').selectOption('teacher');
  await expect(page.getByRole('status')).toContainText('Peran keanggotaan diperbarui');
  await page.getByRole('button', { name: 'Muat anggota organisasi', exact: true }).click();
  await expect(row.getByRole('combobox')).toHaveValue('teacher');
  await row.getByRole('button', { name: `Cabut akses ${member.email}`, exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Akses organisasi dicabut');
  await expect(row.getByRole('button', { name: 'Akses dicabut', exact: true })).toBeDisabled();
});


test('legitimate owner recovers MFA through independent operator proof and a new password', async ({ page, context }) => {
  const account = fixture('seed');
  await page.goto('/auth');
  await login(page, account.email, account.password);
  await setupMfa(page, account.password);
  await page.getByRole('button', { name: 'Keluar', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Berhasil keluar');
  await login(page, account.email, account.password);
  const replacement = 'Independently recovered browser password 123!';
  const uri = await setupMfa(page, account.password, 'recovery', replacement);
  await page.getByRole('button', { name: 'Gunakan organisasi' }).click();
  await expect(page.getByRole('heading', { name: 'Keanggotaan organisasi' })).toBeVisible();
  const rejected = await context.request.post('/api/auth/login', {
    headers: { origin: process.env.APP_ORIGIN! }, data: { email: account.email, password: account.password },
  });
  expect(rejected.status()).toBe(401);
  await page.getByRole('button', { name: 'Keluar', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Berhasil keluar');
  await login(page, account.email, replacement);
  await expect(page.getByRole('button', { name: 'Gunakan organisasi' })).toBeDisabled();
  const otp = fixture('totp', { uri, offset: 30 });
  await page.getByLabel('Kode autentikator').fill(otp.code);
  await page.getByRole('button', { name: 'Verifikasi MFA', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('MFA berhasil diverifikasi');
  await page.getByRole('button', { name: 'Gunakan organisasi' }).click();
  await expect(page.getByRole('heading', { name: 'Keanggotaan organisasi' })).toBeVisible();
});
