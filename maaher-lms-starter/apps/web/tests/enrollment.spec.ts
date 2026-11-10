import { execFileSync } from 'node:child_process';
import { test,expect } from '@playwright/test';
function fixture(operation:string,body={}) {return JSON.parse(execFileSync(process.env.LMS_TEST_PYTHON!,[`${process.env.LMS_TEST_ROOT}/scripts/lms01-browser-fixtures.py`,operation],{input:JSON.stringify(body),encoding:'utf8'}));}

test('admin manages cohort and enrollment; a separate student reads only while access remains active',async({page,context,browser})=>{
  const staff=fixture('oidc-seed');const pupil=fixture('student-seed',{tenant:staff.tenant});
  await page.route('https://browser-tests.us.auth0.com/authorize*',async route=>{
    const url=new URL(route.request().url());const state=url.searchParams.get('state')!;const callback=new URL(url.searchParams.get('redirect_uri')!);
    callback.searchParams.set('state',state);callback.searchParams.set('code',state);
    await route.fulfill({status:302,headers:{location:callback.toString()}});
  });
  await page.goto('/auth');await page.getByRole('button',{name:'Masuk dengan Auth0',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Berhasil masuk melalui Auth0');
  await page.getByRole('button',{name:'Gunakan organisasi',exact:true}).click();
  const headers={'origin':process.env.APP_ORIGIN!,'x-tenant-id':staff.tenant};
  const create=await context.request.post('/api/courses',{headers,data:{title:'Python untuk siswa'}});expect(create.status()).toBe(201);const cid=(await create.json()).id;
  const mod=await context.request.post(`/api/courses/${cid}/modules`,{headers,data:{title:'Dasar coding',version:1}});expect(mod.status()).toBe(201);const mid=(await mod.json()).id;
  const lesson=await context.request.post(`/api/courses/${cid}/modules/${mid}/lessons`,{headers,data:{title:'Program pertama',version:2,content:'# Halo siswa\n\n```python\nprint("Halo siswa")\n```\n\n![Gambar](https://assets.example.invalid/lesson.png)',resources:[{label:'Dokumentasi',url:'https://docs.python.org/3/'}]}});
  expect(lesson.status()).toBe(201);const lid=(await lesson.json()).id;
  expect((await context.request.post(`/api/courses/${cid}/publish`,{headers,data:{version:3}})).status()).toBe(200);
  await page.getByRole('link',{name:'Cohort & enrollment',exact:true}).click();
  await page.getByLabel('Kursus',{exact:true}).selectOption(cid);
  await page.getByLabel('Nama cohort baru',{exact:true}).fill('Kelas November');await page.getByRole('button',{name:'Buat cohort',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Cohort dibuat');
  const hid=(await (await context.request.get('/api/enrollment/cohorts?course_id='+cid,{headers})).json()).cohorts[0].id;
  await page.getByRole('button',{name:'Muat daftar siswa',exact:true}).click();await page.getByLabel('Siswa aktif',{exact:true}).selectOption(pupil.user);
  await page.getByLabel('Cohort tujuan',{exact:true}).selectOption(hid);await page.getByRole('button',{name:'Daftarkan siswa',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Siswa didaftarkan');
  const studentContext=await browser.newContext();const student=await studentContext.newPage();
  try{
    await student.goto(process.env.APP_ORIGIN!+'/auth');await student.getByLabel('Email',{exact:true}).fill(pupil.email);await student.getByLabel('Kata sandi',{exact:true}).fill(pupil.password);
    await student.getByRole('button',{name:'Masuk',exact:true}).click();await expect(student.getByRole('status')).toContainText('Berhasil masuk');
    await student.getByRole('button',{name:'Gunakan organisasi',exact:true}).click();await student.getByRole('link',{name:'Kursus saya',exact:true}).click();
    await student.getByRole('button',{name:'Python untuk siswa',exact:true}).click();await student.getByRole('button',{name:'Program pertama',exact:true}).click();
    const article=student.getByRole('article',{name:'Materi pelajaran'});await expect(article.locator('pre')).toContainText('print("Halo siswa")');
    await expect(article.locator('img,script')).toHaveCount(0);await expect(article.getByRole('link',{name:'Dokumentasi',exact:true})).toHaveAttribute('href','https://docs.python.org/3/');
    page.once('dialog',dialog=>dialog.accept());await page.getByRole('button',{name:'Cabut enrollment '+pupil.email,exact:true}).click();await expect(page.getByRole('status')).toContainText('Enrollment dicabut');
    await student.reload();await expect(student.getByRole('status')).toContainText('Belum ada kursus terbit');await expect(student.getByRole('article')).toHaveCount(0);
    expect((await studentContext.request.get(process.env.APP_ORIGIN!+`/api/enrollment/learning/courses/${cid}/modules/${mid}/lessons/${lid}`,{headers:{'x-tenant-id':staff.tenant}})).status()).toBe(404);
    await page.getByRole('combobox',{name:'Status enrollment',exact:true}).selectOption('revoked');await page.getByRole('button',{name:'Aktifkan ulang',exact:true}).click();await expect(page.getByRole('status')).toContainText('Enrollment diaktifkan ulang');
    await student.reload();await expect(student.getByRole('button',{name:'Python untuk siswa',exact:true})).toBeVisible();
    page.once('dialog',dialog=>dialog.accept());await page.getByRole('button',{name:'Arsipkan Kelas November',exact:true}).click();await expect(page.getByRole('status')).toContainText('Cohort diarsipkan');
    await page.getByLabel('Tampilkan cohort arsip',{exact:true}).check();await page.getByRole('button',{name:'Pulihkan Kelas November',exact:true}).click();await expect(page.getByRole('status')).toContainText('enrollment tetap dicabut');
    await student.reload();await expect(student.getByRole('status')).toContainText('Belum ada kursus terbit');
    await student.getByRole('link',{name:'Akun & keluar',exact:true}).click();await student.getByRole('button',{name:'Keluar',exact:true}).click();await expect(student.getByRole('status')).toContainText('Berhasil keluar');
    expect((await studentContext.request.get(process.env.APP_ORIGIN!+'/api/enrollment/learning/courses',{headers:{'x-tenant-id':staff.tenant}})).status()).toBe(401);
  }finally{await studentContext.close();}
});

test('enrollment BFF restricts routes, methods, query, origin and body size',async({request})=>{
  expect((await request.get('/api/enrollment/learning/courses')).status()).toBe(401);
  expect((await request.post('/api/enrollment/cohorts',{data:{}})).status()).toBe(403);
  expect((await request.post('/api/enrollment/cohorts',{data:{},headers:{origin:'https://evil.invalid'}})).status()).toBe(403);
  expect((await request.post('/api/enrollment/learning/courses',{data:{}})).status()).toBe(404);
  expect((await request.get('/api/enrollment/auth/session')).status()).toBe(404);
  expect((await request.get('/api/enrollment/cohorts?archived=true&archived=false')).status()).toBe(400);
  expect((await request.get('/api/enrollment/enrollments?status=other')).status()).toBe(400);
  expect((await request.get('/api/enrollment/learning/courses?student_id=spoof')).status()).toBe(400);
  expect((await request.post('/api/enrollment/cohorts',{data:'x'.repeat(262145),headers:{origin:process.env.APP_ORIGIN!}})).status()).toBe(413);
});
