'use client';

import { FormEvent, useEffect, useState } from 'react';
import Markdown from 'react-markdown';

type Membership = { tenant_id: string; name: string; role: string };
type Course = { id: string; title: string; description: string; state: string; version: number };
type LessonSummary = { id: string; title: string; position: number };
type Module = { id: string; title: string; position: number; lessons: LessonSummary[] };
type Detail = Course & { modules: Module[]; teachers: string[] };
type Resource = { label: string; url: string };
type Lesson = { id: string; title: string; content: string; resources: Resource[] };
type Member = { user_id: string; email: string; role: string; status: string };
const blank: Lesson = { id: '', title: '', content: '', resources: [] };
const states: Record<string, string> = { draft: 'Draft', published: 'Terbit', archived: 'Arsip' };

function safeHttps(value: string | undefined) {
  if (!value || /[\s\\\u0000-\u001f]/.test(value)) return false;
  try { const url = new URL(value); return url.protocol === 'https:' && !url.username && !url.password; } catch { return false; }
}

class RequestError extends Error { constructor(message: string, public status: number) { super(message); } }

export default function Courses() {
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [tenant, setTenant] = useState(''); const [role, setRole] = useState('');
  const [courses, setCourses] = useState<Course[]>([]); const [next, setNext] = useState<string | null>(null);
  const [archived, setArchived] = useState(false); const [course, setCourse] = useState<Detail | null>(null);
  const [title, setTitle] = useState(''); const [description, setDescription] = useState('');
  const [members, setMembers] = useState<Member[]>([]); const [memberNext, setMemberNext] = useState<string | null>(null);
  const [teacher, setTeacher] = useState(''); const [moduleId, setModuleId] = useState('');
  const [lesson, setLesson] = useState<Lesson | null>(null); const [savedLesson, setSavedLesson] = useState('');
  const [busy, setBusy] = useState(false); const [message, setMessage] = useState('Memuat organisasi…');
  const metadataDirty = !!course && (title !== course.title || description !== course.description);
  const lessonDirty = !!lesson && JSON.stringify(lesson) !== savedLesson;
  const dirty = metadataDirty || lessonDirty;

  async function run(action: () => Promise<void>) {
    setBusy(true); setMessage('');
    try { await action(); } catch (error) {
      if (error instanceof RequestError && [401, 403].includes(error.status)) { setCourse(null); setLesson(null); setCourses([]); setMembers([]); setRole(''); }
      if (error instanceof RequestError && error.status === 404) { setCourse(null); setLesson(null); }
      setMessage(error instanceof Error ? error.message : 'Layanan sementara tidak tersedia');
    } finally { setBusy(false); }
  }

  async function request(path: string, body?: object, selectedTenant = tenant) {
    const response = await fetch(path, { method: body ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store',
      headers: { 'content-type': 'application/json', ...(selectedTenant ? { 'x-tenant-id': selectedTenant } : {}) }, body: body ? JSON.stringify(body) : undefined });
    const data = await response.json();
    if (!response.ok) throw new RequestError(typeof data.detail === 'string' ? data.detail : 'Periksa judul, materi, dan tautan yang diisi', response.status);
    return data;
  }

  async function list(tid = tenant, archive = archived, after?: string) {
    const data = await request(`/api/courses?archived=${archive}${after ? `&after=${after}` : ''}`, undefined, tid);
    setCourses(current => after ? [...current, ...data.courses] : data.courses); setNext(data.next_cursor);
  }

  async function selectTenant(tid: string, archive = false) {
    setCourse(null); setLesson(null); setCourses([]); setMembers([]); setTeacher(''); setMemberNext(null); setNext(null); setModuleId(''); setTenant(tid); setRole(''); setArchived(archive);
    if (!tid) return;
    const self = await request('/api/auth/me', undefined, tid); setRole(self.role);
    await list(tid, archive);
    setMessage('Organisasi siap. Pilih kursus untuk mulai mengelola materi.');
  }

  useEffect(() => { void run(async () => {
    const rows: Membership[] = await request('/api/auth/memberships'); setMemberships(rows);
    const candidate = new URLSearchParams(window.location.search).get('tenant');
    const tid = rows.find(row => row.tenant_id === candidate)?.tenant_id ?? rows[0]?.tenant_id;
    if (tid) await selectTenant(tid); else setMessage('Anda belum menjadi anggota organisasi.');
  }); }, []);

  async function openCourse(cid: string) {
    const data: Detail = await request(`/api/courses/${cid}`); setCourse(data); setTitle(data.title); setDescription(data.description);
  }

  async function mutate(path: string, body: object = {}) {
    if (!course) throw new Error('Pilih kursus terlebih dahulu');
    const result = await request(`/api/courses/${course.id}${path}`, { ...body, version: course.version });
    await openCourse(course.id); await list(); return result;
  }

  async function openLesson(mid: string, lid: string) {
    const data: Lesson = await request(`/api/courses/${course!.id}/modules/${mid}/lessons/${lid}`);
    setModuleId(mid); setLesson(data); setSavedLesson(JSON.stringify(data));
  }

  async function loadMembers(after?: string) {
    const data = await request(`/api/auth/tenant-members${after ? `?after=${after}` : ''}`);
    setMembers(current => after ? [...current, ...data.members] : data.members); setMemberNext(data.next_cursor);
  }

  function form(event: FormEvent<HTMLFormElement>, action: (data: FormData) => Promise<void>) {
    event.preventDefault(); const element = event.currentTarget; const data = new FormData(element);
    void run(async () => { await action(data); element.reset(); });
  }

  function switchContext(action: () => Promise<void>) {
    if (dirty && !window.confirm('Perubahan belum disimpan. Tinggalkan perubahan ini?')) return;
    void run(action);
  }

  function newLesson(mid: string) { setModuleId(mid); setLesson({ ...blank, resources: [] }); setSavedLesson(JSON.stringify(blank)); }
  function ordered(ids: string[], index: number, direction: number) { const next = [...ids]; [next[index], next[index + direction]] = [next[index + direction], next[index]]; return next; }
  const editable = !!course && course.state !== 'archived';

  return <main className="courses-page">
    <header className="studio-header"><div><p className="eyebrow">MAAHER LMS / PENGELOLAAN</p><h1>Kursus &amp; materi</h1><p>Susun langkah belajar coding, satu pelajaran pada satu waktu.</p></div>
      <nav aria-label="Navigasi utama"><a href="/">Beranda</a><a href="/auth">Akun &amp; keluar</a></nav></header>
    <div className="studio-toolbar"><label>Organisasi <select aria-label="Organisasi kursus" value={tenant} disabled={busy} onChange={event => switchContext(() => selectTenant(event.target.value))}>
      <option value="">Pilih organisasi</option>{memberships.map(row => <option key={row.tenant_id} value={row.tenant_id}>{row.name}</option>)}</select></label>
      <button type="button" disabled={busy || !tenant} onClick={() => switchContext(async () => { setLesson(null); if (course) await openCourse(course.id); await list(); })}>Muat ulang kursus</button></div>
    <p role="status" aria-live="polite" className="studio-status">{busy ? 'Memproses…' : message}</p>
    {!role && <p><a href="/auth">Masuk atau pilih organisasi melalui halaman akun</a></p>}
    {['admin','teacher'].includes(role) && <div className="studio-grid">
      <aside className="studio-panel"><h2>Daftar kursus</h2><label className="check-label"><input type="checkbox" checked={archived} disabled={busy} onChange={event => switchContext(async () => { setCourse(null); setLesson(null); setArchived(event.target.checked); await list(tenant, event.target.checked); })} /> Tampilkan arsip</label>
        <ul className="course-list">{courses.map(item => <li key={item.id}><button type="button" className={course?.id === item.id ? 'course-card selected' : 'course-card'} disabled={busy} onClick={() => switchContext(async () => { setLesson(null); setModuleId(''); await openCourse(item.id); setMessage('Kursus dimuat'); })}>
          <span className={`badge ${item.state}`}>{states[item.state]}</span><strong>{item.title}</strong><span>{item.description || 'Belum ada deskripsi'}</span></button></li>)}</ul>
        {!courses.length && <p className="muted">Belum ada kursus pada daftar ini.</p>}
        {next && <button disabled={busy} onClick={() => void run(() => list(tenant, archived, next))}>Muat kursus berikutnya</button>}
        {role === 'admin' && <form className="stack-form" onSubmit={event => form(event, async fields => {
          if (dirty && !window.confirm('Tinggalkan perubahan yang belum disimpan?')) return;
          const result = await request('/api/courses', { title: fields.get('title'), description: fields.get('description') });
          setArchived(false); setLesson(null); await list(tenant, false); await openCourse(result.id); setMessage('Kursus baru dibuat');
        })}><h3>Kursus baru</h3><label>Judul kursus baru<input name="title" required maxLength={160} disabled={busy} /></label>
          <label>Deskripsi singkat<textarea name="description" maxLength={2000} disabled={busy} /></label><button disabled={busy}>Buat kursus</button></form>}
      </aside>
      <section className="studio-workspace" aria-label="Editor kursus">
        {!course ? <div className="studio-panel empty-state"><h2>Mulai susun kelas Anda</h2><p>Pilih kursus dari daftar, atau buat kursus baru untuk menambahkan modul dan pelajaran.</p></div> : <>
          <section className="studio-panel"><div className="panel-heading"><h2>{course.title}</h2><span className={`badge ${course.state}`}>{states[course.state]}</span></div>
            <form className="stack-form" onSubmit={event => { event.preventDefault(); void run(async () => { await mutate('', { title, description }); setMessage('Informasi kursus disimpan sebagai draft'); }); }}>
              <label>Judul kursus<input value={title} onChange={event => setTitle(event.target.value)} required maxLength={160} disabled={busy || !editable || lessonDirty} /></label>
              <label htmlFor="course-description">Deskripsi kursus</label><textarea id="course-description" value={description} onChange={event => setDescription(event.target.value)} maxLength={2000} disabled={busy || !editable || lessonDirty} />
              <button disabled={busy || !editable || !metadataDirty || lessonDirty}>Simpan informasi kursus</button></form>
            <div className="button-row"><button disabled={busy || !editable || dirty} onClick={() => void run(async () => { await mutate(course.state === 'published' ? '/unpublish' : '/publish'); setMessage(course.state === 'published' ? 'Publikasi ditarik' : 'Kursus berhasil diterbitkan'); })}>{course.state === 'published' ? 'Tarik publikasi' : 'Terbitkan kursus'}</button>
              {role === 'admin' && <button disabled={busy || dirty} onClick={() => void run(async () => { await mutate(course.state === 'archived' ? '/restore' : '/archive'); setCourse(null); setLesson(null); await list(); setMessage(course.state === 'archived' ? 'Kursus dipulihkan sebagai draft' : 'Kursus diarsipkan'); })}>{course.state === 'archived' ? 'Pulihkan kursus' : 'Arsipkan kursus'}</button>}
            </div><p className="muted">Perubahan materi mengembalikan kursus ke draft. Isi setiap modul dan pelajaran sebelum menerbitkan.</p>
          </section>
          {role === 'admin' && editable && <section className="studio-panel"><h3>Pengajar kursus</h3><button disabled={busy || dirty} onClick={() => void run(() => loadMembers())}>Muat daftar pengajar</button>
            {memberNext && <button disabled={busy || dirty} onClick={() => void run(() => loadMembers(memberNext))}>Muat anggota berikutnya</button>}
            <form className="inline-form" onSubmit={event => { event.preventDefault(); void run(async () => { await mutate('/teachers', { user_id: teacher, assigned: true }); setMessage('Pengajar ditugaskan'); }); }}>
              <label>Pengajar aktif<select value={teacher} onChange={event => setTeacher(event.target.value)} disabled={busy || dirty} required><option value="">Pilih pengajar</option>{members.filter(m => m.role === 'teacher' && m.status === 'active').map(m => <option key={m.user_id} value={m.user_id}>{m.email}</option>)}</select></label>
              <button disabled={busy || dirty || !teacher}>Tugaskan pengajar</button></form>
            <ul>{course.teachers.map(id => <li key={id}>{members.find(m => m.user_id === id)?.email ?? 'Pengajar terdaftar'}{' '}<button disabled={busy || dirty} onClick={() => void run(async () => { await mutate('/teachers', { user_id: id, assigned: false }); setMessage('Penugasan pengajar dicabut'); })}>Cabut penugasan</button></li>)}</ul></section>}
          <section className="studio-panel"><h3>Struktur pembelajaran</h3>
            <ol className="module-list">{course.modules.map((mod, index) => <li key={mod.id}><div className="module-heading"><strong>{index + 1}. {mod.title}</strong><div className="button-row">
              <button aria-label={`Naikkan modul ${mod.title}`} disabled={busy || !editable || dirty || index === 0} onClick={() => void run(async () => { await mutate('/reorder-modules', { ids: ordered(course.modules.map(m => m.id), index, -1) }); setMessage('Urutan modul diperbarui'); })}>↑</button>
              <button aria-label={`Turunkan modul ${mod.title}`} disabled={busy || !editable || dirty || index === course.modules.length - 1} onClick={() => void run(async () => { await mutate('/reorder-modules', { ids: ordered(course.modules.map(m => m.id), index, 1) }); setMessage('Urutan modul diperbarui'); })}>↓</button>
              <button aria-label={`Hapus modul ${mod.title}`} disabled={busy || !editable || dirty} onClick={() => { if (window.confirm('Hapus modul beserta seluruh pelajarannya?')) void run(async () => { await mutate(`/modules/${mod.id}/delete`); setLesson(null); setModuleId(''); setMessage('Modul dihapus'); }); }}>Hapus</button></div></div>
              {editable && <form className="inline-form" key={`${mod.id}-${mod.title}`} onSubmit={event => form(event, async fields => { await mutate(`/modules/${mod.id}`, { title: fields.get('title') }); setMessage('Judul modul diperbarui'); })}><label>Nama modul<input name="title" defaultValue={mod.title} required maxLength={160} disabled={busy || dirty} /></label><button disabled={busy || dirty}>Ubah nama modul</button></form>}
              <ol>{mod.lessons.map((item, li) => <li key={item.id}><button className="text-button" disabled={busy} onClick={() => switchContext(() => openLesson(mod.id, item.id))}>{item.title}</button>{' '}
                <button aria-label={`Naikkan pelajaran ${item.title}`} disabled={busy || !editable || dirty || li === 0} onClick={() => void run(async () => { await mutate(`/modules/${mod.id}/reorder-lessons`, { ids: ordered(mod.lessons.map(l => l.id), li, -1) }); setMessage('Urutan pelajaran diperbarui'); })}>↑</button>
                <button aria-label={`Turunkan pelajaran ${item.title}`} disabled={busy || !editable || dirty || li === mod.lessons.length - 1} onClick={() => void run(async () => { await mutate(`/modules/${mod.id}/reorder-lessons`, { ids: ordered(mod.lessons.map(l => l.id), li, 1) }); setMessage('Urutan pelajaran diperbarui'); })}>↓</button></li>)}</ol>
              <button disabled={busy || !editable || dirty} onClick={() => newLesson(mod.id)}>Tambah pelajaran ke {mod.title}</button></li>)}</ol>
            {!course.modules.length && <p className="muted">Tambahkan modul pertama untuk menyusun materi.</p>}
            {editable && <form className="inline-form" onSubmit={event => form(event, async fields => { await mutate('/modules', { title: fields.get('title') }); setMessage('Modul ditambahkan'); })}><label>Judul modul baru<input name="title" required maxLength={160} disabled={busy || dirty} /></label><button disabled={busy || dirty}>Tambah modul</button></form>}
          </section>
          {lesson && <section className="studio-panel"><h3>{lesson.id ? 'Edit pelajaran' : 'Pelajaran baru'}</h3>
            <form className="stack-form" onSubmit={event => { event.preventDefault(); void run(async () => {
              const result = await mutate(`/modules/${moduleId}/lessons${lesson.id ? '/' + lesson.id : ''}`, { title: lesson.title, content: lesson.content, resources: lesson.resources });
              await openLesson(moduleId, lesson.id || result.id); setMessage('Pelajaran disimpan sebagai draft');
            }); }}><label>Judul pelajaran<input value={lesson.title} required maxLength={160} disabled={busy || !editable || metadataDirty} onChange={event => setLesson({ ...lesson, title: event.target.value })} /></label>
              <label htmlFor="lesson-markdown">Materi Markdown</label><textarea id="lesson-markdown" className="markdown-editor" value={lesson.content} maxLength={30000} disabled={busy || !editable || metadataDirty} onChange={event => setLesson({ ...lesson, content: event.target.value })} />
              <p className="muted">Gunakan # untuk judul, daftar, dan blok kode dengan tiga backtick. Tautan materi memakai HTTPS.</p>
              <fieldset disabled={busy || !editable || metadataDirty}><legend>Tautan materi tambahan</legend>{lesson.resources.map((resource, index) => <div className="resource-row" key={index}>
                <label>Nama tautan {index + 1}<input value={resource.label} required maxLength={120} onChange={event => setLesson({ ...lesson, resources: lesson.resources.map((r, i) => i === index ? { ...r, label: event.target.value } : r) })} /></label>
                <label>URL HTTPS {index + 1}<input value={resource.url} required type="url" maxLength={2048} onChange={event => setLesson({ ...lesson, resources: lesson.resources.map((r, i) => i === index ? { ...r, url: event.target.value } : r) })} /></label>
                <button type="button" onClick={() => setLesson({ ...lesson, resources: lesson.resources.filter((_, i) => i !== index) })}>Hapus tautan {index + 1}</button></div>)}
                <button type="button" disabled={lesson.resources.length >= 10} onClick={() => setLesson({ ...lesson, resources: [...lesson.resources, { label: '', url: '' }] })}>Tambah tautan materi</button></fieldset>
              <div className="button-row"><button disabled={busy || !editable || metadataDirty}>Simpan pelajaran</button><button type="button" disabled={busy} onClick={() => { if (!lessonDirty || window.confirm('Tutup editor dan tinggalkan perubahan yang belum disimpan?')) { setLesson(null); setSavedLesson(''); } }}>Tutup editor</button>
                {lesson.id && <button type="button" disabled={busy || !editable || metadataDirty} onClick={() => { if (window.confirm('Hapus pelajaran ini beserta materinya?')) void run(async () => { await mutate(`/modules/${moduleId}/lessons/${lesson.id}/delete`); setLesson(null); setMessage('Pelajaran dihapus'); }); }}>Hapus pelajaran</button>}</div></form>
            <article className="lesson-preview" aria-label="Pratinjau pelajaran"><p className="eyebrow">PRATINJAU MATERI</p><h2>{lesson.title || 'Judul pelajaran'}</h2>
              <Markdown skipHtml urlTransform={url => safeHttps(url) ? url : ''} components={{ a: ({ href, children }) => <a href={safeHttps(href) ? href : undefined} target="_blank" rel="noopener noreferrer">{children}</a>, img: ({ src, alt }) => <span>{safeHttps(typeof src === 'string' ? src : '') ? <a href={src as string} target="_blank" rel="noopener noreferrer">Gambar: {alt || 'Buka materi gambar'}</a> : alt}</span> }}>{lesson.content}</Markdown>
              {lesson.resources.length > 0 && <><h3>Materi tambahan</h3><ul>{lesson.resources.map((r, i) => <li key={i}>{safeHttps(r.url) ? <a href={r.url} target="_blank" rel="noopener noreferrer">{r.label}</a> : r.label}</li>)}</ul></>}
            </article></section>}
        </>}
      </section>
    </div>}
  </main>;
}
