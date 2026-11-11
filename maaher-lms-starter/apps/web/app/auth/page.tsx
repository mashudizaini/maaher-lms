'use client';

import { FormEvent, useEffect, useState } from 'react';

type Membership = { tenant_id: string; name: string; role: string };
type Event = { id: string; action: string; created_at: string };
type Member = { user_id: string; email: string; role: string; status: string };
const roleNames: Record<string, string> = { student: 'Siswa', teacher: 'Pengajar', admin: 'Admin' };
const actionNames: Record<string, string> = {
  'login.succeeded': 'Berhasil masuk', 'login.failed': 'Gagal masuk', 'login.throttled': 'Percobaan masuk dibatasi',
  logout: 'Keluar', 'reset.requested': 'Pemulihan diminta', 'password.reset': 'Kata sandi diperbarui',
  'mfa.enrollment_started': 'Penyiapan MFA dimulai', 'mfa.verified': 'MFA diverifikasi', 'mfa.failed': 'Verifikasi MFA gagal',
  'invitation.created': 'Undangan dibuat', 'invitation.accepted': 'Undangan diterima',
  'membership.revoked': 'Keanggotaan dicabut', 'tenant.selected': 'Organisasi dipilih',
  'membership.role_changed': 'Peran diperbarui', 'mfa.operator_authorized': 'Otorisasi operator dicatat', 'mfa.recovered': 'MFA dipulihkan',
};

export default function Authentication() {
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [tenant, setTenant] = useState('');
  const [role, setRole] = useState('');
  const [token, setToken] = useState('');
  const [mode, setMode] = useState('');
  const [uri, setUri] = useState('');
  const [events, setEvents] = useState<Event[]>([]);
  const [requestId, setRequestId] = useState('');
  const [purpose, setPurpose] = useState('bootstrap');
  const [members, setMembers] = useState<Member[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [myUser, setMyUser] = useState('');
  const [oidcAvailable, setOidcAvailable] = useState(false);
  const [externalLogin, setExternalLogin] = useState(false);

  useEffect(() => {
    function readLink() {
      const fragment = new URLSearchParams(window.location.hash.slice(1));
      for (const name of ['invitation', 'password-reset']) {
        const value = fragment.get(name);
        if (value) { setMode(name); setToken(value); }
      }
      if (window.location.hash) window.history.replaceState(null, '', window.location.pathname);
    }
    readLink();
    void fetch('/api/auth/oidc/config', { cache: 'no-store' })
      .then(response => response.ok ? response.json() : { enabled: false })
      .then(config => setOidcAvailable(config.enabled === true)).catch(() => setOidcAvailable(false));
    const result = new URLSearchParams(window.location.search).get('oidc');
    if (result) {
      window.history.replaceState(null, '', window.location.pathname);
      if (result === 'success') {
        void run(async () => { await loadMemberships(); setMessage('Berhasil masuk melalui Auth0'); });
      } else setMessage('Login Auth0 gagal atau tidak diizinkan. Silakan mulai kembali.');
    }
    window.addEventListener('hashchange', readLink);
    return () => window.removeEventListener('hashchange', readLink);
  }, []);

  async function call(path: string, body?: object) {
    const response = await fetch(`/api/auth/${path}`, { method: body ? 'POST' : 'GET',
      headers: { 'content-type': 'application/json', ...(tenant ? { 'x-tenant-id': tenant } : {}) },
      body: body ? JSON.stringify(body) : undefined, credentials: 'same-origin', cache: 'no-store' });
    const data = await response.json();
    if (!response.ok) {
      setRole('');
      throw new Error(typeof data.detail === 'string' ? data.detail : 'Periksa kembali data yang diisi');
    }
    return data;
  }

  async function run(action: () => Promise<void>) {
    setBusy(true); setMessage('');
    try { await action(); } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Layanan sementara tidak tersedia');
    } finally { setBusy(false); }
  }

  function form(event: FormEvent<HTMLFormElement>, action: (fields: FormData) => Promise<void>) {
    event.preventDefault();
    const element = event.currentTarget;
    const fields = new FormData(element);
    void run(async () => { await action(fields); element.reset(); });
  }

  async function loadMemberships() {
    const rows: Membership[] = await call('memberships');
    const provider = await fetch('/api/auth/oidc/session', { cache: 'no-store' });
    setExternalLogin(provider.ok);
    setMemberships(rows); setRole(''); setEvents([]);
    setTenant(current => rows.some(row => row.tenant_id === current) ? current : rows[0]?.tenant_id ?? '');
  }

  async function loadMembers(after?: string) {
    const result = await call(`tenant-members${after ? `?after=${encodeURIComponent(after)}` : ''}`);
    setMembers(current => after ? [...current, ...result.members] : result.members);
    setNextCursor(result.next_cursor);
  }

  return <main>
    <h1>Akun Maaher LMS</h1>
    <p><a href="/">Beranda</a></p>
    <p role="status" aria-live="polite">{busy ? 'Memproses…' : message}</p>
    <fieldset disabled={busy}>
      <legend>Masuk dan keamanan akun</legend>
      <section aria-labelledby="oidc-heading">
        <h2 id="oidc-heading">Admin dan operator</h2>
        <p>Gunakan akun organisasi yang telah didaftarkan dan selesaikan verifikasi yang diminta.</p>
        <button type="button" disabled={!oidcAvailable} onClick={() => void run(async () => {
          const result = await call('oidc/login', {});
          window.location.assign(result.authorization_url);
        })}>Masuk dengan Auth0</button>
        {!oidcAvailable && <p>Login staff belum diaktifkan.</p>}
      </section>
      <section aria-labelledby="login-heading">
        <h2 id="login-heading">Masuk</h2>
        <form onSubmit={event => form(event, async fields => {
          const login = await call('login', { email: fields.get('email'), password: fields.get('password') });
          setExternalLogin(false);
          setUri(''); setRole(''); setMembers([]); setRequestId(''); setEvents([]);
          if (login.mfa_required) { setMemberships([]); setTenant(''); } else { await loadMemberships(); }
          setMessage('Berhasil masuk. Verifikasi MFA jika diminta.');
        })}>
          <p><label>Email <input name="email" type="email" autoComplete="username" required /></label></p>
          <p><label>Kata sandi <input name="password" type="password" autoComplete="current-password" required /></label></p>
          <button>Masuk</button>
        </form>
        <p><button type="button" onClick={() => void run(async () => {
          await call('logout', {}); setMemberships([]); setTenant(''); setRole(''); setUri(''); setEvents([]); setMembers([]); setRequestId('');
          setExternalLogin(false);
          setMessage('Berhasil keluar');
        })}>Keluar</button></p>
      </section>
      <section aria-labelledby="tenant-heading">
        <h2 id="tenant-heading">Organisasi</h2>
        <button type="button" onClick={() => void run(loadMemberships)}>Muat organisasi saya</button>
        <p><label>Pilih organisasi <select value={tenant} onChange={event => { setTenant(event.target.value); setRole(''); setEvents([]); setMembers([]); setNextCursor(null); }}>
          <option value="">Pilih organisasi</option>
          {memberships.map(row => <option key={row.tenant_id} value={row.tenant_id}>{row.name} ({roleNames[row.role] ?? row.role})</option>)}
        </select></label></p>
        <button type="button" disabled={!tenant} onClick={() => void run(async () => {
          const selected = await call('tenant-selection', {}); setRole(selected.role); setMessage('Organisasi dipilih');
          const self = await call('me'); setMyUser(self.user_id);
        })}>Gunakan organisasi</button>
        {['admin','teacher'].includes(role) && <p><a href={`/courses?tenant=${encodeURIComponent(tenant)}`}>Kelola kursus</a> · <a href="/grading">Penilaian &amp; feedback</a> · <a href="/assignments">Tugas &amp; submission</a> · <a href="/enrollments">Cohort &amp; enrollment</a></p>}
        {role === 'student' && <p><a href="/learn">Kursus saya</a> · <a href="/work">Tugas saya</a></p>}
      </section>
      {externalLogin ? <section aria-labelledby="external-security-heading">
        <h2 id="external-security-heading">Keamanan akun organisasi</h2>
        <p>Faktor autentikasi akun ini dikelola melalui Auth0. Gunakan prosedur keamanan dan pemulihan akun organisasi.</p>
      </section> : <section aria-labelledby="mfa-heading">
        <h2 id="mfa-heading">Verifikasi dua langkah (MFA)</h2>
        <p>Admin wajib memakai MFA. Aktivasi pertama dan pemulihan membutuhkan verifikasi operator independen, bukan email atau kata sandi saja. Jalur operator untuk akun nyata belum dikonfigurasi.</p>
        <p><label htmlFor="mfa-purpose">Jenis permintaan</label>{' '}<select id="mfa-purpose" value={purpose} onChange={event => { setPurpose(event.target.value); setRequestId(''); }}>
          <option value="bootstrap">Aktivasi pertama</option><option value="recovery">Pemulihan perangkat</option>
        </select></p>
        <button type="button" onClick={() => void run(async () => {
          const result = await call('mfa/request', { purpose }); setRequestId(result.request_id);
          setMessage('Tunjukkan ID pada operator melalui jalur verifikasi independen. Jangan gunakan email login/reset.');
        })}>Minta verifikasi operator</button>
        {requestId && <p><label>ID permintaan operator <input readOnly value={requestId} /></label></p>}
        <form onSubmit={event => form(event, async fields => {
          const result = await call('mfa/enroll', { password: fields.get('password'), authorization: fields.get('authorization'),
            ...(purpose === 'recovery' ? { new_password: fields.get('new_password') } : {}) });
          setUri(result.provisioning_uri); setMessage('Tambahkan kunci ke autentikator, lalu verifikasi kode.');
        })}>
          <p><label>Konfirmasi kata sandi <input name="password" type="password" autoComplete="current-password" required /></label></p>
          <p><label>Kode otorisasi operator <input name="authorization" type="password" autoComplete="off" required /></label></p>
          {purpose === 'recovery' && <p><label>Kata sandi pengganti untuk pemulihan MFA <input name="new_password" type="password" minLength={15} maxLength={1024} autoComplete="new-password" required /></label></p>}
          <button>Siapkan MFA</button>
        </form>
        {uri && <p><label>Kunci penyiapan rahasia <input readOnly value={uri} onFocus={event => event.target.select()} /></label></p>}
        <form onSubmit={event => form(event, async fields => {
          await call('mfa/verify', { code: fields.get('code') }); setUri(''); setRequestId(''); await loadMemberships(); setMessage('MFA berhasil diverifikasi');
        })}>
          <p><label>Kode autentikator <input name="code" inputMode="numeric" pattern="[0-9]{6}" autoComplete="one-time-code" required /></label></p>
          <button>Verifikasi MFA</button>
        </form>
      </section>}
      {mode === 'invitation' && <section aria-labelledby="invite-accept-heading">
        <h2 id="invite-accept-heading">Terima undangan</h2>
        <p>Jika sudah punya akun, masuk dengan akun penerima terlebih dahulu. Untuk akun baru, isi kata sandi minimal 15 karakter.</p>
        <form onSubmit={event => form(event, async fields => {
          const password = fields.get('password');
          await call('invitations/accept', { token, ...(password ? { password } : {}) });
          setToken(''); setMode(''); setMessage('Undangan diterima. Silakan masuk.');
        })}>
          <p><label>Kata sandi akun baru <input name="password" type="password" minLength={15} maxLength={1024} autoComplete="new-password" /></label></p>
          <button>Terima undangan</button>
        </form>
      </section>}
      <section aria-labelledby="reset-heading">
        <h2 id="reset-heading">Lupa kata sandi</h2>
        <form onSubmit={event => form(event, async fields => {
          const result = await call('password-reset/request', { email: fields.get('email') }); setMessage(result.message);
        })}>
          <p><label>Email pemulihan <input name="email" type="email" autoComplete="email" required /></label></p>
          <button>Kirim petunjuk pemulihan</button>
        </form>
        {mode === 'password-reset' && <form onSubmit={event => form(event, async fields => {
          await call('password-reset/confirm', { token, password: fields.get('password') });
          setMode(''); setToken(''); setMemberships([]); setRole(''); setUri('');
          setMessage('Kata sandi diperbarui. Silakan masuk kembali.');
        })}>
          <p><label>Kata sandi baru <input name="password" type="password" minLength={15} maxLength={1024} autoComplete="new-password" required /></label></p>
          <button>Simpan kata sandi baru</button>
        </form>}
      </section>
      {role === 'admin' && <section aria-labelledby="admin-heading">
        <h2 id="admin-heading">Keanggotaan organisasi</h2>
        <form onSubmit={event => form(event, async fields => {
          const result = await call('invitations', { email: fields.get('email'), role: fields.get('role') }); setMessage(result.message);
        })}>
          <p><label>Email undangan <input name="email" type="email" required /></label></p>
          <p><label htmlFor="invitation-role">Peran</label>{' '}<select id="invitation-role" name="role"><option value="student">Siswa</option><option value="teacher">Pengajar</option><option value="admin">Admin</option></select></p>
          <button>Kirim undangan</button>
        </form>
        <p><button type="button" onClick={() => void run(() => loadMembers())}>Muat anggota organisasi</button></p>
        {members.length > 0 && <table><caption>Anggota organisasi terpilih</caption><thead><tr><th>Email</th><th>Peran</th><th>Akses</th></tr></thead><tbody>
          {members.map(member => <tr key={member.user_id}><td>{member.email}</td><td>
            <select aria-label={`Peran ${member.email}`} value={member.role} disabled={member.user_id === myUser || member.status !== 'active'} onChange={event => {
              const next = event.target.value; void run(async () => {
                const result = await call(`memberships/${member.user_id}/role`, { role: next });
                setMembers(current => current.map(row => row.user_id === member.user_id ? { ...row, role: next } : row)); setMessage(result.message);
              });
            }}><option value="student">Siswa</option><option value="teacher">Pengajar</option><option value="admin">Admin</option></select>
          </td><td><button type="button" disabled={member.user_id === myUser || member.status !== 'active'} onClick={() => void run(async () => {
            const result = await call(`memberships/${member.user_id}/revoke`, {});
            setMembers(current => current.map(row => row.user_id === member.user_id ? { ...row, status: 'revoked' } : row)); setMessage(result.message);
          })}>{member.status === 'active' ? `Cabut akses ${member.email}` : 'Akses dicabut'}</button></td></tr>)}
        </tbody></table>}
        {nextCursor && <button type="button" onClick={() => void run(() => loadMembers(nextCursor))}>Muat anggota berikutnya</button>}
        <p><button type="button" onClick={() => void run(async () => { setEvents(await call('audit')); })}>Muat audit organisasi</button></p>
      </section>}
      <p><button type="button" onClick={() => void run(async () => { setEvents(await call('security-events')); })}>Muat riwayat keamanan saya</button></p>
      {events.length > 0 && <table><caption>Riwayat aktivitas</caption><thead><tr><th scope="col">Aktivitas</th><th scope="col">Waktu (Jakarta)</th></tr></thead>
        <tbody>{events.map(row => <tr key={row.id}><td>{actionNames[row.action] ?? 'Aktivitas keamanan'}</td><td>{new Date(row.created_at).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' })}</td></tr>)}</tbody></table>}
    </fieldset>
  </main>;
}
