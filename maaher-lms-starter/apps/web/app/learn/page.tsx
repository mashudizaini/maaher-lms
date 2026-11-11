'use client';
import { useEffect, useState } from 'react';
import { api, ApiError, Membership } from '../components/lms-client';
import LessonContent from '../components/lesson-content';

type Course = { id: string; title: string; description: string };
type Step = { id: string; module_id: string; title?: string };
type Summary = { id: string; title: string; revision: number; completed: boolean; needs_review: boolean };
type Module = { id: string; title: string; lessons: Summary[] };
type Outline = Course & { modules: Module[]; progress: { completed: number; total: number }; resume: Step | null };
type Lesson = Summary & { content: string; resources: { label: string; url: string }[]; previous: Step | null; next: Step | null };
const base = '/api/enrollment/learning/courses';

export default function Learn() {
  const [members, setMembers] = useState<Membership[]>([]);
  const [tenant, setTenant] = useState('');
  const [courses, setCourses] = useState<Course[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [outline, setOutline] = useState<Outline | null>(null);
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [moduleId, setModuleId] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('Memuat organisasi…');

  async function run(work: () => Promise<void>) {
    setBusy(true); setMessage('');
    try { await work(); } catch (error) {
      if (error instanceof ApiError && [401, 403, 404].includes(error.status)) {
        setLesson(null); setOutline(null); setCourses([]);
      }
      setMessage(error instanceof Error ? error.message : 'Layanan sementara tidak tersedia');
    } finally { setBusy(false); }
  }

  async function load(tid: string, after?: string) {
    const result = await api(base + (after ? '?after=' + after : ''), tid);
    setCourses(current => after ? [...current, ...result.courses] : result.courses);
    setNext(result.next_cursor);
    if (!after) { setOutline(null); setLesson(null); }
    setMessage(result.courses.length ? 'Pilih kursus untuk membuka materi.' : 'Belum ada kursus terbit dengan enrollment aktif. Hubungi admin organisasi Anda.');
  }

  async function openCourse(cid: string) {
    setLesson(null); setModuleId('');
    setOutline(await api(base + '/' + cid, tenant));
    setMessage('Pilih pelajaran atau lanjutkan yang belum selesai.');
  }

  async function openLesson(cid: string, step: Step) {
    setLesson(await api(`${base}/${cid}/modules/${step.module_id}/lessons/${step.id}`, tenant));
    setModuleId(step.module_id); setMessage('Pelajaran siap dibaca.');
  }

  async function complete(advance = false) {
    if (!outline || !lesson) return;
    const wasComplete = lesson.completed;
    await api(`${base}/${outline.id}/modules/${moduleId}/lessons/${lesson.id}/${wasComplete && !advance ? 'uncomplete' : 'complete'}`,
      tenant, { revision: lesson.revision });
    const fresh: Outline = await api(base + '/' + outline.id, tenant);
    setOutline(fresh);
    const step = advance && lesson.next ? lesson.next : { id: lesson.id, module_id: moduleId };
    await openLesson(outline.id, step);
    setMessage(wasComplete && !advance ? 'Pelajaran ditandai belum selesai.' : 'Pelajaran ditandai selesai.');
  }

  useEffect(() => { void run(async () => {
    const rows: Membership[] = await api('/api/auth/memberships');
    const students = rows.filter(row => row.role === 'student'); setMembers(students);
    const requested = new URL(window.location.href).searchParams.get('tenant');
    const selected = students.find(row => row.tenant_id === requested) ?? students[0];
    if (selected) { setTenant(selected.tenant_id); await load(selected.tenant_id); }
    else setMessage('Akun ini belum memiliki keanggotaan siswa aktif.');
  }); }, []);

  return <main className="courses-page">
    <header className="studio-header"><div><p className="eyebrow">MAAHER LMS / BELAJAR</p><h1>Kursus saya</h1><p>Belajar bertahap, simpan kemajuan, dan lanjutkan langkah berikutnya.</p></div>
      <nav><a href="/work">Tugas saya</a><a href="/">Beranda</a><a href="/auth">Akun &amp; keluar</a></nav></header>
    <div className="studio-toolbar">
      <label htmlFor="learning-tenant">Organisasi</label>
      <select id="learning-tenant" value={tenant} disabled={busy} onChange={event => {
        const tid = event.target.value; setTenant(tid); setCourses([]); setOutline(null); setLesson(null); void run(() => load(tid));
      }}>{!members.length && <option value="">Pilih organisasi</option>}{members.map(m => <option key={m.tenant_id} value={m.tenant_id}>{m.name}</option>)}</select>
      <button disabled={busy || !tenant} onClick={() => void run(() => load(tenant))}>Muat ulang kursus</button>
    </div>
    <p className="studio-status" role="status" aria-live="polite">{busy ? 'Memuat…' : message}</p>
    <div className="studio-grid">
      <aside className="studio-panel"><h2>Daftar kursus</h2>
        <ul className="course-list">{courses.map(c => <li key={c.id}><button className={'course-card' + (outline?.id === c.id ? ' selected' : '')} disabled={busy} onClick={() => void run(() => openCourse(c.id))}>
          <strong>{c.title}</strong><span>{c.description}</span></button></li>)}</ul>
        {next && <button disabled={busy} onClick={() => void run(() => load(tenant, next))}>Muat kursus berikutnya</button>}
      </aside>
      <section className="studio-workspace" aria-label="Materi kursus">{outline && <>
        <section className="studio-panel"><h2>{outline.title}</h2>
          <label htmlFor="course-progress">Progres kursus</label>
          <progress id="course-progress" value={outline.progress.completed} max={Math.max(1, outline.progress.total)} />
          <p>{outline.progress.completed} dari {outline.progress.total} pelajaran selesai</p>
          {outline.resume ? <button disabled={busy} onClick={() => void run(() => openLesson(outline.id, outline.resume!))}>Lanjutkan belajar</button>
            : outline.progress.total > 0 && <p className="learning-success">Semua pelajaran pada revisi ini selesai. Anda dapat membacanya kembali.</p>}
          {outline.modules.map(m => <section key={m.id}><h3>{m.title}</h3><ol>{m.lessons.map(l => <li key={l.id}>
            <button aria-current={lesson?.id === l.id ? 'step' : undefined} disabled={busy} onClick={() => void run(() => openLesson(outline.id, { id: l.id, module_id: m.id }))}>
              {l.completed && <span aria-hidden="true">✓ </span>}{l.title}</button>
            {l.needs_review && <span className="muted"> · Materi diperbarui</span>}
          </li>)}</ol></section>)}
        </section>
        {lesson && <article className="studio-panel lesson-preview" aria-label="Materi pelajaran"><p className="eyebrow">{lesson.completed ? 'SELESAI' : 'SEDANG DIPELAJARI'}</p><h2>{lesson.title}</h2>
          {lesson.needs_review && <p className="learning-notice">Materi telah diperbarui. Baca kembali lalu tandai selesai untuk menyimpan kemajuan pada revisi ini.</p>}
          <p><a href={`/work?tenant=${tenant}&course=${outline.id}&lesson=${lesson.id}`}>Tugas pelajaran</a></p>
          <LessonContent content={lesson.content} resources={lesson.resources} />
          <div className="learning-actions">
            <button disabled={busy} onClick={() => void run(() => complete())}>{lesson.completed ? 'Tandai belum selesai' : 'Tandai selesai'}</button>
            {!lesson.completed && lesson.next && <button disabled={busy} onClick={() => void run(() => complete(true))}>Selesai &amp; lanjutkan</button>}
            <button disabled={busy} onClick={() => void run(() => openLesson(outline.id, { id: lesson.id, module_id: moduleId }))}>Muat ulang pelajaran</button>
          </div>
          <nav className="learning-actions" aria-label="Navigasi pelajaran">
            <button disabled={busy || !lesson.previous} onClick={() => lesson.previous && void run(() => openLesson(outline.id, lesson.previous!))}>← Pelajaran sebelumnya</button>
            <button disabled={busy || !lesson.next} onClick={() => lesson.next && void run(() => openLesson(outline.id, lesson.next!))}>Pelajaran berikutnya →</button>
          </nav>
        </article>}
      </>}</section>
    </div>
  </main>;
}
