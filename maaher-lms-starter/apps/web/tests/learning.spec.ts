import { execFileSync } from 'node:child_process';
import { test, expect } from '@playwright/test';
function fixture(operation: string, body = {}) {
  return JSON.parse(execFileSync(process.env.LMS_TEST_PYTHON!, [`${process.env.LMS_TEST_ROOT}/scripts/lms01-browser-fixtures.py`, operation], { input: JSON.stringify(body), encoding: 'utf8' }));
}

test('student completion persists; next steps work; edited material invalidates completion; revoke stops writes', async ({ page, context, browser }) => {
  const staff = fixture('oidc-seed'); const pupil = fixture('student-seed', { tenant: staff.tenant });
  await page.route('https://browser-tests.us.auth0.com/authorize*', async route => {
    const url = new URL(route.request().url()); const state = url.searchParams.get('state')!;
    const callback = new URL(url.searchParams.get('redirect_uri')!); callback.searchParams.set('state', state); callback.searchParams.set('code', state);
    await route.fulfill({ status: 302, headers: { location: callback.toString() } });
  });
  await page.goto('/auth'); await page.getByRole('button', { name: 'Masuk dengan Auth0', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Berhasil masuk melalui Auth0');
  await page.getByRole('button', { name: 'Gunakan organisasi', exact: true }).click();
  const headers = { origin: process.env.APP_ORIGIN!, 'x-tenant-id': staff.tenant };
  const created = await context.request.post('/api/courses', { headers, data: { title: 'Belajar bertahap' } }); expect(created.status()).toBe(201);
  const cid = (await created.json()).id;
  const mod = await context.request.post(`/api/courses/${cid}/modules`, { headers, data: { title: 'Modul pertama', version: 1 } }); expect(mod.status()).toBe(201);
  const mid = (await mod.json()).id;
  const lesson1 = await context.request.post(`/api/courses/${cid}/modules/${mid}/lessons`, { headers, data: { title: 'Langkah pertama', content: 'Materi pertama', version: 2 } }); expect(lesson1.status()).toBe(201);
  const first = (await lesson1.json()).id;
  const lesson2 = await context.request.post(`/api/courses/${cid}/modules/${mid}/lessons`, { headers, data: { title: 'Langkah kedua', content: 'Materi kedua', version: 3 } }); expect(lesson2.status()).toBe(201);
  const second = (await lesson2.json()).id;
  expect((await context.request.post(`/api/courses/${cid}/publish`, { headers, data: { version: 4 } })).status()).toBe(200);
  const cohort = await context.request.post('/api/enrollment/cohorts', { headers, data: { course_id: cid, title: 'Kelompok belajar' } }); expect(cohort.status()).toBe(201);
  const enrolled = await context.request.post('/api/enrollment/enrollments', { headers, data: { course_id: cid, cohort_id: (await cohort.json()).id, student_id: pupil.user } }); expect(enrolled.status()).toBe(201);
  const eid = (await enrolled.json()).id;
  const studentContext = await browser.newContext(); const student = await studentContext.newPage();
  try {
    await student.goto(process.env.APP_ORIGIN! + '/auth'); await student.getByLabel('Email', { exact: true }).fill(pupil.email);
    await student.getByLabel('Kata sandi', { exact: true }).fill(pupil.password); await student.getByRole('button', { name: 'Masuk', exact: true }).click();
    await expect(student.getByRole('status')).toContainText('Berhasil masuk'); await student.getByRole('button', { name: 'Gunakan organisasi', exact: true }).click();
    await student.getByRole('link', { name: 'Kursus saya', exact: true }).click(); await student.getByRole('button', { name: 'Belajar bertahap', exact: true }).click();
    await expect(student.getByText('0 dari 2 pelajaran selesai', { exact: true })).toBeVisible();
    await student.getByRole('button', { name: 'Lanjutkan belajar', exact: true }).click();
    await expect(student.getByRole('article', { name: 'Materi pelajaran' })).toContainText('Materi pertama');
    await expect(student.getByRole('button', { name: '← Pelajaran sebelumnya', exact: true })).toBeDisabled();
    await student.getByRole('button', { name: 'Selesai & lanjutkan', exact: true }).click();
    await expect(student.getByText('1 dari 2 pelajaran selesai', { exact: true })).toBeVisible();
    await expect(student.getByRole('article', { name: 'Materi pelajaran' })).toContainText('Materi kedua');
    await student.getByRole('button', { name: 'Tandai selesai', exact: true }).click();
    await expect(student.getByText('2 dari 2 pelajaran selesai', { exact: true })).toBeVisible();
    await expect(student.getByRole('progressbar', { name: 'Progres kursus', exact: true })).toHaveAttribute('value', '2');
    await student.reload(); await student.getByRole('button', { name: 'Belajar bertahap', exact: true }).click();
    await expect(student.getByText('2 dari 2 pelajaran selesai', { exact: true })).toBeVisible();
    await student.getByRole('button', { name: 'Langkah pertama', exact: true }).click();
    await student.getByRole('button', { name: 'Tandai belum selesai', exact: true }).click();
    await expect(student.getByText('1 dari 2 pelajaran selesai', { exact: true })).toBeVisible();
    const version = (await (await context.request.get('/api/courses/' + cid, { headers })).json()).version;
    const edit = await context.request.post(`/api/courses/${cid}/modules/${mid}/lessons/${second}`, { headers, data: { title: 'Langkah kedua', content: 'Materi kedua diperbarui', version } }); expect(edit.status()).toBe(200);
    expect((await context.request.post(`/api/courses/${cid}/publish`, { headers, data: { version: (await edit.json()).version } })).status()).toBe(200);
    await student.getByRole('button', { name: 'Muat ulang kursus', exact: true }).click(); await student.getByRole('button', { name: 'Belajar bertahap', exact: true }).click();
    await expect(student.getByText('0 dari 2 pelajaran selesai', { exact: true })).toBeVisible(); await student.getByRole('button', { name: 'Langkah kedua', exact: true }).click();
    await expect(student.getByRole('article', { name: 'Materi pelajaran' })).toContainText('Materi telah diperbarui');
    await student.getByRole('button', { name: 'Tandai selesai', exact: true }).click(); await expect(student.getByText('1 dari 2 pelajaran selesai', { exact: true })).toBeVisible();
    expect((await context.request.post(`/api/enrollment/enrollments/${eid}/revoke`, { headers, data: { version: 1 } })).status()).toBe(200);
    await student.getByRole('button', { name: 'Tandai belum selesai', exact: true }).click(); await expect(student.getByRole('status')).toContainText('Kursus tidak tersedia');
    await expect(student.getByRole('article', { name: 'Materi pelajaran' })).toHaveCount(0);
    const denied = await studentContext.request.post(process.env.APP_ORIGIN! + `/api/enrollment/learning/courses/${cid}/modules/${mid}/lessons/${first}/complete`, { headers: { origin: process.env.APP_ORIGIN!, 'x-tenant-id': staff.tenant }, data: { revision: 1 } }); expect(denied.status()).toBe(404);
  } finally { await studentContext.close(); }
});

test('completion BFF accepts only explicit mutations and validates Origin/query', async ({ request }) => {
  const id = '00000000-0000-0000-0000-000000000001'; const path = `/api/enrollment/learning/courses/${id}/modules/${id}/lessons/${id}`;
  expect((await request.get(path + '/complete')).status()).toBe(404);
  expect((await request.post(path + '/complete', { data: { revision: 1 } })).status()).toBe(403);
  expect((await request.post(path + '/complete?tenant_id=' + id, { headers: { origin: process.env.APP_ORIGIN! }, data: { revision: 1 } })).status()).toBe(400);
  expect((await request.post(path + '/delete', { headers: { origin: process.env.APP_ORIGIN! }, data: {} })).status()).toBe(404);
});
