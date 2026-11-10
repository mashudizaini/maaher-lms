'use client';
import { useEffect,useState } from 'react';
import { api,ApiError,Membership } from '../components/lms-client';
import LessonContent from '../components/lesson-content';
type Course = { id:string;title:string;description:string };
type Module = { id:string;title:string;lessons:{id:string;title:string}[] };
type Outline = Course & {modules:Module[]};
type Lesson = {id:string;title:string;content:string;resources:{label:string;url:string}[]};
export default function Learn() {
  const [members,setMembers]=useState<Membership[]>([]); const [tenant,setTenant]=useState('');
  const [courses,setCourses]=useState<Course[]>([]);const [next,setNext]=useState<string|null>(null);
  const [outline,setOutline]=useState<Outline|null>(null);const [lesson,setLesson]=useState<Lesson|null>(null);
  const [busy,setBusy]=useState(false);const [message,setMessage]=useState('Memuat organisasi…');
  async function run(work:()=>Promise<void>) {
    setBusy(true);setMessage('');
    try { await work(); } catch(error) {
      if (error instanceof ApiError && [401,403,404].includes(error.status)) {setLesson(null);setOutline(null);setCourses([]);}
      setMessage(error instanceof Error ? error.message : 'Layanan sementara tidak tersedia');
    } finally {setBusy(false);}
  }
  async function load(tid:string,after?:string) {
    const result=await api('/api/enrollment/learning/courses'+(after?'?after='+after:''),tid);
    setCourses(current=>after?[...current,...result.courses]:result.courses);setNext(result.next_cursor);
    if (!after) {setOutline(null);setLesson(null);}
    setMessage(result.courses.length ? 'Pilih kursus untuk membuka materi.' : 'Belum ada kursus terbit dengan enrollment aktif. Hubungi admin organisasi Anda.');
  }
  useEffect(()=>{void run(async()=>{
    const rows:Membership[]=await api('/api/auth/memberships');const students=rows.filter(row=>row.role==='student');setMembers(students);
    if(students.length){setTenant(students[0].tenant_id);await load(students[0].tenant_id);}else setMessage('Akun ini belum memiliki keanggotaan siswa aktif.');
  });},[]);
  return <main className="courses-page"><header className="studio-header"><div><p className="eyebrow">MAAHER LMS / BELAJAR</p><h1>Kursus saya</h1><p>Materi coding untuk langkah belajar Anda.</p></div><nav><a href="/">Beranda</a><a href="/auth">Akun &amp; keluar</a></nav></header>
    <div className="studio-toolbar"><label htmlFor="learning-tenant">Organisasi</label><select id="learning-tenant" value={tenant} disabled={busy} onChange={event=>{const tid=event.target.value;setTenant(tid);setCourses([]);setOutline(null);setLesson(null);void run(()=>load(tid));}}>{!members.length&&<option value="">Pilih organisasi</option>}{members.map(m=><option key={m.tenant_id} value={m.tenant_id}>{m.name}</option>)}</select><button disabled={busy||!tenant} onClick={()=>void run(()=>load(tenant))}>Muat ulang kursus</button></div>
    <p className="studio-status" role="status" aria-live="polite">{busy?'Memuat…':message}</p>
    <div className="studio-grid"><aside className="studio-panel"><h2>Daftar kursus</h2><ul className="course-list">{courses.map(c=><li key={c.id}><button className="course-card" disabled={busy} onClick={()=>void run(async()=>{setLesson(null);setOutline(await api('/api/enrollment/learning/courses/'+c.id,tenant));setMessage('Pilih pelajaran.');})}><strong>{c.title}</strong><span>{c.description}</span></button></li>)}</ul>{next&&<button disabled={busy} onClick={()=>void run(()=>load(tenant,next))}>Muat kursus berikutnya</button>}</aside>
      <section className="studio-workspace" aria-label="Materi kursus">{outline&&<><section className="studio-panel"><h2>{outline.title}</h2>{outline.modules.map(m=><section key={m.id}><h3>{m.title}</h3><ol>{m.lessons.map(l=><li key={l.id}><button disabled={busy} onClick={()=>void run(async()=>{setLesson(await api(`/api/enrollment/learning/courses/${outline.id}/modules/${m.id}/lessons/${l.id}`,tenant));setMessage('Pelajaran siap dibaca.');})}>{l.title}</button></li>)}</ol></section>)}</section>{lesson&&<article className="studio-panel lesson-preview" aria-label="Materi pelajaran"><h2>{lesson.title}</h2><LessonContent content={lesson.content} resources={lesson.resources}/></article>}</>}</section>
    </div></main>;
}
