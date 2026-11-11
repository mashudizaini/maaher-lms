import { execFileSync } from 'node:child_process';
import { test, expect } from '@playwright/test';
function fixture(operation: string, body = {}) { return JSON.parse(execFileSync(process.env.LMS_TEST_PYTHON!, [`${process.env.LMS_TEST_ROOT}/scripts/lms01-browser-fixtures.py`, operation], { input: JSON.stringify(body), encoding: 'utf8' })); }

test('assigned teacher drafts, releases, corrects and withdraws original-rubric grades; student sees only releases', async ({ page, context, browser }) => {
  test.setTimeout(90000);
  const staff = fixture('oidc-seed'), pupil = fixture('student-seed', { tenant: staff.tenant });
  const seeded = fixture('grading-seed', { tenant: staff.tenant, user: staff.user, student: pupil.user });
  await page.route('https://browser-tests.us.auth0.com/authorize*', async route => { const url = new URL(route.request().url()), state = url.searchParams.get('state')!; const callback = new URL(url.searchParams.get('redirect_uri')!); callback.searchParams.set('state', state); callback.searchParams.set('code', state); await route.fulfill({ status: 302, headers: { location: callback.toString() } }); });
  await page.goto('/auth'); await page.getByRole('button', { name: 'Masuk dengan Auth0', exact: true }).click(); await expect(page.getByRole('status')).toContainText('Berhasil masuk melalui Auth0'); await page.getByRole('button', { name: 'Gunakan organisasi', exact: true }).click();
  const headers = { origin: process.env.APP_ORIGIN!, 'x-tenant-id': staff.tenant };
  expect((await (await context.request.get('/api/auth/me', { headers })).json()).role).toBe('teacher');
  const body = { title: 'Latihan untuk dinilai', instructions: 'Buat fungsi penjumlahan.', language: 'python', rubric: [{ criterion: 'Ketepatan', max_points: 70 }, { criterion: 'Keterbacaan', max_points: 30 }], max_attempts: 3 };
  const created = await context.request.post('/api/assignments', { headers, data: { ...body, course_id: seeded.course, lesson_id: seeded.lesson } }); expect(created.status()).toBe(201); const aid = (await created.json()).id;
  expect((await context.request.post(`/api/assignments/${aid}/publish`, { headers, data: { version: 1 } })).status()).toBe(200);
  const studentContext = await browser.newContext(), student = await studentContext.newPage();
  try {
    await student.goto(process.env.APP_ORIGIN! + '/auth'); await student.getByLabel('Email', { exact: true }).fill(pupil.email); await student.getByLabel('Kata sandi', { exact: true }).fill(pupil.password); await student.getByRole('button', { name: 'Masuk', exact: true }).click(); await expect(student.getByRole('status')).toContainText('Berhasil masuk'); await student.getByRole('button', { name: 'Gunakan organisasi', exact: true }).click();
    await student.goto(process.env.APP_ORIGIN! + `/work?tenant=${staff.tenant}&course=${seeded.course}`); await student.getByRole('button', { name: body.title, exact: true }).click();
    await student.getByLabel('Jawaban (python)', { exact: true }).fill('def add(a, b):\n    return a + b'); await student.getByRole('button', { name: 'Simpan draf jawaban', exact: true }).click(); await expect(student.getByRole('status')).toContainText('Draf tersimpan'); student.on('dialog', dialog => dialog.accept());
    await student.getByRole('button', { name: 'Kirim jawaban', exact: true }).click(); await expect(student.getByRole('status')).toContainText('Jawaban terkirim'); await expect(student.getByRole('region', { name: 'Nilai submission' })).toContainText('Nilai belum dibagikan');
    const list = await (await studentContext.request.get(process.env.APP_ORIGIN! + `/api/work/submissions?course_id=${seeded.course}`, { headers })).json(), sid = list.submissions[0].id;
    // A later task rubric must never replace the submitted version's70/30 rules.
    expect((await context.request.post('/api/assignments/' + aid, { headers, data: { ...body, version: 2, rubric: [{ criterion: 'Rubrik baru', max_points: 100 }] } })).status()).toBe(200);
    expect((await context.request.post(`/api/assignments/${aid}/publish`, { headers, data: { version: 3 } })).status()).toBe(200);
    await page.goto('/grading'); await page.getByLabel('Kursus', { exact: true }).selectOption(seeded.course); await page.getByRole('button', { name: 'Latihan untuk dinilai · Percobaan 1', exact: true }).click();
    await page.getByLabel('Poin kriteria 1 (maks 70)', { exact: true }).fill('50'); await page.getByLabel('Poin kriteria 2 (maks 30)', { exact: true }).fill('20');
    const feedback = '<script>window.gradeUnsafe=true</script>\nUmpan balik pertama 😀'; await page.getByLabel('Feedback untuk siswa', { exact: true }).fill(feedback);
    let limited = false; await page.route(`**/api/grading/submissions/${sid}/draft`, async route => { if (!limited) { limited = true; await route.fulfill({ status: 429, contentType: 'application/json', headers: { 'retry-after': '60' }, body: JSON.stringify({ detail: 'Batas tes penilaian' }) }); } else await route.continue(); });
    await page.getByRole('button', { name: 'Simpan draf nilai', exact: true }).click(); await expect(page.getByRole('status')).toContainText('Batas tes penilaian'); await expect(page.getByLabel('Feedback untuk siswa', { exact: true })).toHaveValue(feedback); await expect(page.getByLabel('Poin kriteria 1 (maks 70)', { exact: true })).toHaveValue('50');
    await page.getByRole('button', { name: 'Simpan draf nilai', exact: true }).click(); await expect(page.getByRole('status')).toContainText('Draf nilai tersimpan');
    await student.getByRole('button', { name: 'Muat ulang nilai', exact: true }).click(); await expect(student.getByRole('region', { name: 'Nilai submission' })).toContainText('Nilai belum dibagikan'); await expect(student.getByText(feedback, { exact: true })).toHaveCount(0);
    page.on('dialog', dialog => dialog.accept()); await page.getByRole('button', { name: 'Bagikan nilai', exact: true }).click(); await expect(page.getByRole('status')).toContainText('Nilai dan feedback dibagikan');
    await student.getByRole('button', { name: 'Muat ulang nilai', exact: true }).click(); await expect(student.getByRole('region', { name: 'Nilai submission' })).toContainText('Nilai 70/100'); await expect(student.getByText(feedback, { exact: true })).toBeVisible(); expect(await student.evaluate(() => Reflect.get(window, 'gradeUnsafe'))).toBeUndefined();
    await page.getByLabel('Poin kriteria 1 (maks 70)', { exact: true }).fill('60'); await page.getByLabel('Feedback untuk siswa', { exact: true }).fill('Feedback koreksi'); await page.getByLabel('Alasan penilaian/perubahan (hanya staf)', { exact: true }).fill('Alasan privat koreksi');
    await page.getByRole('button', { name: 'Simpan draf nilai', exact: true }).click(); await expect(page.getByRole('status')).toContainText('Draf nilai tersimpan'); await student.getByRole('button', { name: 'Muat ulang nilai', exact: true }).click(); await expect(student.getByRole('region', { name: 'Nilai submission' })).toContainText('Nilai 70/100'); await expect(student.getByText('Feedback koreksi', { exact: true })).toHaveCount(0);
    await page.getByRole('button', { name: 'Bagikan nilai', exact: true }).click(); await expect(page.getByRole('status')).toContainText('Nilai dan feedback dibagikan'); await student.getByRole('button', { name: 'Muat ulang nilai', exact: true }).click(); await expect(student.getByRole('region', { name: 'Nilai submission' })).toContainText('Nilai 80/100'); await expect(student.getByText('Alasan privat koreksi', { exact: false })).toHaveCount(0);
    await page.getByLabel('Alasan penilaian/perubahan (hanya staf)', { exact: true }).fill('Moderasi ulang'); await page.getByRole('button', { name: 'Tarik nilai', exact: true }).click(); await expect(page.getByRole('status')).toContainText('Nilai ditarik'); await student.getByRole('button', { name: 'Muat ulang nilai', exact: true }).click(); await expect(student.getByRole('region', { name: 'Nilai submission' })).toContainText('Nilai ditarik'); await expect(student.getByText('Feedback koreksi', { exact: true })).toHaveCount(0);
    await page.getByRole('button', { name: 'Riwayat penilaian', exact: true }).click(); await expect(page.getByText('Alasan internal: Moderasi ulang', { exact: true })).toBeVisible();
    const preserved = await studentContext.request.get(process.env.APP_ORIGIN! + '/api/work/submissions/' + sid, { headers }); expect((await preserved.json()).source_code).toContain('return a + b');
    expect((await studentContext.request.get(process.env.APP_ORIGIN! + `/api/grading/submissions/${sid}/history`, { headers })).status()).toBe(403);
  } finally { await studentContext.close(); }
});

test('grading BFF restricts methods, Origin, queries and body size', async ({ request }) => {
  const id = '00000000-0000-0000-0000-000000000001', origin = process.env.APP_ORIGIN!;
  expect((await request.get(`/api/grading/submissions/${id}/draft`)).status()).toBe(404);
  expect((await request.post(`/api/grading/submissions/${id}/release`, { data: { version: 1 } })).status()).toBe(403);
  expect((await request.post(`/api/grading/submissions/${id}/withdraw?version=1`, { headers: { origin }, data: { version: 1 } })).status()).toBe(400);
  expect((await request.get(`/api/grading/submissions?course_id=${id}&state=bad`)).status()).toBe(400);
  expect((await request.get(`/api/grading/submissions?course_id=${id}&course_id=${id}`)).status()).toBe(400);
  expect((await request.get(`/api/grading/submissions/${id}/history?after=301`)).status()).toBe(400);
  expect((await request.post(`/api/grading/submissions/${id}/draft`, { headers: { origin }, data: 'x'.repeat(262145) })).status()).toBe(413);
  expect((await request.post(`/api/work/submissions/${id}/grade`, { headers: { origin }, data: {} })).status()).toBe(404);
});
