import { execFileSync } from 'node:child_process';
import { test, expect } from '@playwright/test';
function fixture(operation: string, body = {}) {
  return JSON.parse(execFileSync(process.env.LMS_TEST_PYTHON!, [`${process.env.LMS_TEST_ROOT}/scripts/lms01-browser-fixtures.py`, operation], { input: JSON.stringify(body), encoding: 'utf8' }));
}

test('versioned tasks and immutable submissions survive reload and revoke in two browser sessions', async ({ page, context, browser }) => {
  test.setTimeout(90000);
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
  const created = await context.request.post('/api/courses', { headers, data: { title: 'Kursus tugas' } }); expect(created.status()).toBe(201);
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

  await page.goto('/assignments'); await page.getByLabel('Kursus', {exact:true}).selectOption(cid);
  await page.getByLabel('Pelajaran', {exact:true}).selectOption(first);
  await page.getByLabel('Judul tugas', {exact:true}).fill('Latihan penjumlahan');
  await page.getByLabel('Instruksi Markdown', {exact:true}).fill('Buat fungsi penjumlahan dua angka.');
  await page.getByLabel('Kode awal', {exact:true}).fill('def add(a, b):\n    pass');
  await page.getByLabel('Deadline (WIB, opsional)', {exact:true}).fill('2099-01-02T07:30');
  await page.getByLabel('Batas total percobaan', {exact:true}).fill('2');
  await page.getByRole('button', {name:'Simpan tugas',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Versi draf tersimpan');
  await page.getByRole('button',{name:'Terbitkan tugas',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Status tugas diperbarui');
  const tasks=await (await context.request.get(`/api/assignments?course_id=${cid}`,{headers})).json(); const aid=tasks.assignments[0].id;
  const badInstructions=await context.request.post(`/api/assignments/${aid}`,{headers:{...headers,'content-type':'application/json'},data:JSON.stringify({version:2,title:'Invalid text',instructions:'redact-this-value-\ud800',rubric:[{criterion:'All',max_points:100}]})});
  expect(badInstructions.status()).toBe(422);expect(await badInstructions.text()).not.toContain('redact-this-value');
  const badDate=await context.request.post(`/api/assignments/${aid}`,{headers,data:{version:2,title:'Invalid date',instructions:'Valid',rubric:[{criterion:'All',max_points:100}],due_at:'0001-01-01T00:00:00+01:00'}});expect(badDate.status()).toBe(422);

  const otherTask=await context.request.post('/api/assignments',{headers,data:{course_id:cid,lesson_id:second,title:'Tugas pelajaran lain',instructions:'Latihan lain',rubric:[{criterion:'Semua',max_points:100}]}});expect(otherTask.status()).toBe(201);
  const otherId=(await otherTask.json()).id;expect((await context.request.post(`/api/assignments/${otherId}/publish`,{headers,data:{version:1}})).status()).toBe(200);
  const studentContext = await browser.newContext(); const student = await studentContext.newPage();
  try {
    await student.goto(process.env.APP_ORIGIN! + '/auth'); await student.getByLabel('Email',{exact:true}).fill(pupil.email);
    await student.getByLabel('Kata sandi',{exact:true}).fill(pupil.password);await student.getByRole('button',{name:'Masuk',exact:true}).click();
    await expect(student.getByRole('status')).toContainText('Berhasil masuk');await student.getByRole('button',{name:'Gunakan organisasi',exact:true}).click();
    await student.goto(process.env.APP_ORIGIN!+`/work?tenant=${staff.tenant}&course=${cid}&lesson=${first}`);
    await expect(student.getByRole('button',{name:'Tugas pelajaran lain',exact:true})).toHaveCount(0);
    await student.getByRole('button',{name:'Tampilkan semua tugas kursus',exact:true}).click();await expect(student.getByRole('button',{name:'Tugas pelajaran lain',exact:true})).toBeVisible();
    await student.getByRole('button',{name:'Latihan penjumlahan',exact:true}).click();
    await expect(student.getByRole('region',{name:'Tugas aktif'})).toContainText('07.30 WIB');
    const answer='<script>window.maaherUnsafe=true</script>\nprint("jawaban satu")';
    await student.getByLabel('Jawaban (python)',{exact:true}).fill(answer);
    await student.getByRole('button',{name:'Simpan draf jawaban',exact:true}).click();await expect(student.getByRole('status')).toContainText('Draf tersimpan');
    const state=await (await studentContext.request.get(process.env.APP_ORIGIN!+`/api/work/assignments/${aid}`,{headers})).json();
    const invalidDraft=await studentContext.request.post(process.env.APP_ORIGIN!+`/api/work/assignments/${aid}/draft`,{headers:{...headers,'content-type':'application/json'},data:JSON.stringify({version_id:state.published.id,revision:state.draft.revision,source_code:'redact-this-value-\ud800'})});
    expect(invalidDraft.status()).toBe(422);expect(await invalidDraft.text()).not.toContain('redact-this-value');

    student.on('dialog',dialog=>dialog.accept());
    await student.getByRole('button',{name:'Kirim jawaban',exact:true}).click();await expect(student.getByRole('status')).toContainText('Jawaban terkirim');
    await expect(student.getByRole('article',{name:'Salinan submission'}).locator('pre')).toHaveText(answer);
    expect(await student.evaluate(()=>Reflect.get(window,'maaherUnsafe'))).toBeUndefined();
    const history=await (await studentContext.request.get(process.env.APP_ORIGIN!+`/api/work/submissions?course_id=${cid}`,{headers})).json();const sid=history.submissions[0].id;
    await student.reload();await student.getByRole('button',{name:'Latihan penjumlahan',exact:true}).click();await expect(student.getByLabel('Jawaban (python)',{exact:true})).toHaveValue(answer);
    await page.getByLabel('Judul tugas',{exact:true}).fill('Latihan penjumlahan revisi');await page.getByRole('button',{name:'Simpan versi baru',exact:true}).click();await expect(page.getByRole('status')).toContainText('Versi draf tersimpan');
    await student.getByRole('button',{name:'Muat ulang tugas',exact:true}).click();await expect(student.getByRole('heading',{name:'Latihan penjumlahan',exact:true})).toBeVisible();
    await page.getByRole('button',{name:'Terbitkan tugas',exact:true}).click();await expect(page.getByRole('status')).toContainText('Status tugas diperbarui');
    await student.getByRole('button',{name:'Muat ulang tugas',exact:true}).click();await expect(student.getByText('Draf tersimpan masih memakai versi lama.',{exact:false})).toBeVisible();
    await expect(student.getByRole('button',{name:'Simpan draf jawaban',exact:true})).toBeDisabled();await expect(student.getByLabel('Jawaban (python)',{exact:true})).toHaveValue(answer);
    await student.getByLabel('Saya sudah memeriksa versi baru dan ingin menyimpan jawaban ini pada versi baru',{exact:true}).check();
    await student.getByLabel('Jawaban (python)',{exact:true}).fill('print("jawaban versi dua")');await student.getByRole('button',{name:'Simpan draf jawaban',exact:true}).click();await expect(student.getByRole('status')).toContainText('Draf tersimpan');
    await student.getByRole('button',{name:'Kirim jawaban',exact:true}).click();await expect(student.getByRole('status')).toContainText('Jawaban terkirim');
    await expect(student.getByText('Percobaan 2 dari 2 (total lintas versi).',{exact:true})).toBeVisible();await expect(student.getByRole('button',{name:'Kirim jawaban',exact:true})).toBeDisabled();
    const old=await studentContext.request.get(process.env.APP_ORIGIN!+'/api/work/submissions/'+sid,{headers});expect((await old.json()).source_code).toBe(answer);
    await page.getByRole('button',{name:'Muat submission',exact:true}).click();await expect(page.getByRole('button',{name:/Percobaan 1 ·/})).toBeVisible();
    await page.getByRole('button',{name:/Percobaan 1 ·/}).click();await expect(page.getByRole('article',{name:'Detail submission'}).locator('pre')).toHaveText(answer);
    expect((await context.request.post(`/api/enrollment/enrollments/${eid}/revoke`,{headers,data:{version:1}})).status()).toBe(200);
    await student.getByRole('button',{name:'Muat ulang riwayat',exact:true}).click();await expect(student.getByRole('status')).toContainText('Kursus tidak ditemukan');
    await expect(student.getByRole('article',{name:'Salinan submission'})).toHaveCount(0);
    expect((await studentContext.request.get(process.env.APP_ORIGIN!+'/api/work/submissions/'+sid,{headers})).status()).toBe(404);
    expect((await context.request.get(`/api/assignment-submissions?course_id=${cid}&assignment_id=${aid}`,{headers})).status()).toBe(200);
  } finally { await studentContext.close(); }
});

test('assignment BFF denies unsupported methods, forged query, absent Origin and oversized body',async({request})=>{
 const id='00000000-0000-0000-0000-000000000001';const origin=process.env.APP_ORIGIN!;
 expect((await request.get(`/api/work/assignments/${id}/submit`)).status()).toBe(404);
 expect((await request.post(`/api/work/assignments/${id}/submit`,{data:{}})).status()).toBe(403);
 expect((await request.post(`/api/assignments/${id}/publish?tenant_id=${id}`,{headers:{origin},data:{version:1}})).status()).toBe(400);
 expect((await request.post(`/api/work/assignments/${id}/draft`,{headers:{origin},data:'x'.repeat(262145)})).status()).toBe(413);
 expect((await request.get(`/api/assignments?course_id=${id}&course_id=${id}`)).status()).toBe(400);
 expect((await request.post(`/api/assignment-submissions/${id}`,{headers:{origin},data:{}})).status()).toBe(405);
 expect((await request.get(`/api/work/submissions/${id}?source_code=x`)).status()).toBe(400);
});
