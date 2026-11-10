# LMS-01 Claude Review

Reviewer: Claude Code (independent, read-only). Tanggal: 2026-11-09.
Tidak ada source aplikasi yang diubah. Satu-satunya berkas yang ditulis di workspace adalah laporan ini; skrip probe ada di scratchpad di luar repo.

## Base / head SHA

- Root workspace **bukan repository Git** (`git diff main...HEAD` tidak dapat dijalankan). `maaher-lms/.git` kosong tanpa commit. Baseline yang dicatat handoff: GitHub `8941a79dcf611df66c4ee43e78b902b62ddbfce2`. Saya tidak dapat memverifikasi SHA ini sendiri (tanpa akses jaringan/GitHub ke baseline).
- Head = **workspace yang belum di-commit**. Pemeriksaan kesegaran diff yang benar-benar dijalankan:
  - 59/59 entri `reviews/LMS-01-review-manifest.json` ada dan SHA-256 file workspace saat ini cocok; SHA-256 `LMS-01-author.patch` cocok dengan manifest.
  - Tidak ada berkas non-cache yang lebih baru dari manifest.
  - 12 berkas yang tidak ada di manifest adalah berkas baseline tak berubah (README, AGENTS.md, CLAUDE.md, spec, workflow, dsb.).
  - Saya membaca **source workspace**, bukan patch. Saya tidak meng-apply patch dan tidak memeriksa ulang 25 blob baseline.

## Files inspected

`AGENTS.md`, `CLAUDE.md`, `docs/{PROJECT-SPEC,ARCHITECTURE,AGENT-WORKFLOW,LMS-01-HANDOFF,LMS-01-CHECKLIST}.md`, `docs/adr/001-auth-lifecycle.md`, `docs/tickets/LMS-01.md`;
`apps/api/app/{auth,auth_lifecycle,auth_support,mfa,mail_worker,database,security,provision,main}.py`;
`apps/api/migrations/{identity.sql,auth_lifecycle.sql,env.py,versions/0001,0002}`; `apps/api/tests/test_identity_postgres.py` (header/fixtures);
`apps/web/app/api/auth/[...path]/route.ts`, `apps/web/app/auth/page.tsx`, `next.config.ts`, `package.json`;
`docker-compose.yml`, `.github/workflows/ci.yml`, `.env.example`, `.gitignore`, kedua Dockerfile, `infra/development-roles.sql`, `scripts/audit-server.sh`.

Tidak dibaca penuh: `test_identity_postgres.py` (±750 baris, hanya fixture), `auth.spec.ts`, skrip browser/audit/build-review, lockfile.

## Tests run and results

Lingkungan: kontainer **baru** milik reviewer `claude-review-pg16-lms01` (postgres:16, image lokal), port loopback acak, role dari `infra/development-roles.sql` + LOGIN `maaher_api` (mewarisi `maaher_runtime`, NOBYPASSRLS) + LOGIN `maaher_mail_login` (mewarisi `maaher_mailer`). Database kosong baru per run (`maaher_test_review_1/2/3`). Tidak memakai kontainer/database author. Data sintetis saja; tidak ada email/SMTP/probe pihak ketiga.

| Perintah / uji | Hasil nyata |
|---|---|
| `pytest -v apps/api/tests` pada DB `maaher_test_review_1`, runtime role `maaher_api` (macOS, Python 3.13.5, PG 16) | **36 passed, 1 warning in 22.69s**, 0 skip. Konsisten dengan klaim handoff. |
| `pip check` | No broken requirements found |
| Probe reviewer P1, P3, P5, P6, P7, P8 (pytest, DB `_3`) | 6 passed — masing-masing mengonfirmasi temuan di bawah (output dikutip pada temuan) |
| Probe P2 (uvicorn nyata + commit ditunda, DB `_2`) | Terkonfirmasi: respons+cookie terkirim sebelum COMMIT |
| `psql` sebagai `maaher_api`: INSERT sessions `mfa_verified=true` (di-ROLLBACK) | Berhasil (lihat M4) |
| Fungsi SECURITY DEFINER pada DB hasil migrasi | 3 fungsi, owner `postgres` (superuser), `search_path=pg_catalog, public` |

**Tidak dijalankan ulang**: tes browser Playwright/Chrome (2), build/typecheck Next, build image Docker, run Linux/Python 3.12, `npm audit`, audit PyPI (`scripts/audit-api-dependencies.py`, perlu jaringan), SMTP nyata, GitHub CI. Klaim handoff untuk item-item ini **tidak diverifikasi** oleh review ini.

## Findings

### HIGH

- **[HIGH] `apps/api/app/mfa.py:25-46` (+ `auth.py:58-79`) — Enrollment MFA pertama hanya butuh password; admin tanpa faktor dapat diambil alih, user biasa dapat dikunci permanen.**
  - Kondisi: `POST /auth/mfa/enroll` hanya memeriksa session password-only + kata sandi (baris 29-35); faktor ditulis jika belum ada `confirmed` (37-44). Siapa pun yang memegang kata sandi (atau mengendalikan email lewat `password-reset`, yang tidak menyentuh MFA) pada akun yang **belum enroll** dapat mendaftarkan authenticator miliknya. Klaim "admin wajib MFA setiap login" tidak melindungi jendela antara akun dibuat/diundang dan enroll pertama: undangan admin → penerima tautan → set password → enroll sendiri = admin penuh; pencuri password admin yang belum enroll idem.
  - Dampak sebaliknya: bila penyerang enroll lebih dulu pada akun user biasa (student/teacher), `principal` (`auth.py:73-75`) menolak semua rute tenant bagi pemilik sah dan reset password tidak menghapus faktor; tidak ada alur pemulihan (ADR butir 6 menyatakan belum ada). Kunci permanen sampai intervensi DB manual.
  - Bukti (probe P6): login dengan password → `enroll`+`verify` → logout → login pemilik sah dengan password yang sama → `GET /auth/me` dengan `x-tenant-id` valid = **403 "Verifikasi MFA diperlukan"**; `mfa_factors.confirmed = true`.
  - Fix: (a) enroll pertama hanya dari konteks yang terbukti — mis. token enroll sekali pakai yang dikirim ke email terverifikasi, atau admin yang sudah MFA men-trigger enroll bagi anggota; (b) admin baru tidak boleh melewati `principal` sebelum faktor terkonfirmasi, dan undangan role admin sebaiknya mensyaratkan enroll di alur penerimaan; (c) sediakan pemulihan faktor teruji (sudah ada di checklist sebagai belum selesai) sebelum akun nyata; (d) tes negatif: session password-only tidak dapat mengganti/menambah faktor pada akun yang tenant-nya mensyaratkan MFA.

### MEDIUM

- **[MEDIUM] `apps/api/app/auth.py:39-42`, `database.py:11-26` — respons (termasuk `Set-Cookie`) terkirim sebelum transaksi di-COMMIT.**
  - `connection()` adalah dependency generator `with transaction() as db: yield db`; di FastAPI 0.162.2 teardown berjalan setelah respons dikirim. Bukti (P2, uvicorn nyata, `time.sleep(1.0)` disuntikkan tepat sebelum commit pada teardown): `login` 200 diterima setelah 0,17 s; request langsung berikutnya dengan cookie itu → **401**; 1,5 s kemudian cookie sama → **200**. Penundaan sengaja untuk menampakkan urutan; pada commit normal jendelanya milidetik, tetapi tidak nol (UI memanggil `memberships` segera setelah login, `page.tsx:83`).
  - Dampak keamanan: operasi `revoke`, `reset`, `logout`, `invite` melaporkan sukses kepada klien sebelum durable; jika COMMIT gagal (deadlock/serialisasi/koneksi putus) klien tetap menerima "Akses organisasi dicabut"/"Berhasil keluar" padahal rollback. Kegagalan commit tidak dapat dikembalikan sebagai error. Saya **tidak** mereproduksi kegagalan commit alami, hanya urutan.
  - Fix: commit eksplisit di dalam handler/dependency sebelum return (mis. dependency non-generator atau middleware yang commit sebelum mengirim), atau `yield` dependency dengan scope yang diselesaikan sebelum respons; tambahkan tes yang menunda commit dan memastikan respons tidak keluar lebih dulu.

- **[MEDIUM] `auth.py:82-112`, `auth_support.py:19-33`, `auth_lifecycle.py:92-106`, `route.ts:19-28` — endpoint anonim memicu tulis/CPU tanpa batas dan tanpa retensi.**
  - Login memverifikasi Argon2 pada setiap percobaan, termasuk email tak dikenal (`dummy_hash`, baris 101), dan setiap percobaan membuat baris `login_attempts` + `auth_events(user_id NULL)`. Throttle hanya per email, bukan per IP; BFF tidak meneruskan IP klien. Tidak ada job pembersihan untuk `login_attempts`, `auth_events`, `sessions` kedaluwarsa, maupun `auth_mail_outbox` (alamat penerima tetap tersimpan setelah token dihapus; `mail_worker.py:38-63`).
  - Bukti (P5): 40 login + 40 reset request anonim dengan email acak → `login_attempts` 2→82, `auth_events` 1→41. Pertumbuhan linear tanpa batas.
  - Handoff mengakui rate limit edge diperlukan; temuan ini menambahkan bahwa aplikasi sendiri tidak punya penahan pertumbuhan/biaya Argon2 dan data persisten (PII email di outbox) tanpa kebijakan retensi.
  - Fix: batasan per-IP di edge **dan** aplikasi (teruskan IP tepercaya dari BFF), job retensi terjadwal + tes, hapus/anonimkan baris outbox setelah sent/expired.

- **[MEDIUM] `auth.py:82-107` — throttle login per email membuat korban dapat dikunci oleh penyerang anonim.**
  - 10 percobaan salah (juga login sukses dihitung; counter tidak di-reset saat sukses) dalam 15 menit → login sah 429. Bukti (P7): 10 password salah anonim → login dengan password benar = **429**. Penyerang mengulang tiap 15 menit untuk memblokir akun (mis. admin). Reset password tidak membantu karena throttle terpisah tetapi login tetap terblokir.
  - Fix: kunci kombinasi (email, IP/perangkat), backoff progresif yang tidak mengunci pemilik sah dari perangkat dikenal, reset counter saat sukses, dan jalur pemulihan.

- **[MEDIUM] `migrations/identity.sql:69-71`, `auth_lifecycle.sql` — role runtime dapat membaca semua `users.password_hash` dan memalsukan session ter-MFA tanpa konteks apa pun.**
  - `users` dan `sessions` tidak memakai RLS; runtime punya `SELECT users` dan `INSERT,DELETE sessions` penuh. Bukti: sebagai `maaher_api` tanpa `app.*` → `SELECT count(*) FROM users` = 2 (semua hash Argon2 terbaca), `sessions` terbaca (P1); `INSERT INTO sessions(... mfa_verified=true)` untuk user mana pun **berhasil** (di-rollback). ADR mengakui tabel global dan RLS sebagai kontrak backend tepercaya; namun arsitektur menargetkan least privilege, dan LMS-02+ akan menambah query SQL — satu SQL injection/bug di sana setara pengambilalihan akun admin lintas tenant tanpa MFA.
  - Fix: batasi kolom (`GRANT SELECT(id,email,status)`; password hash hanya lewat fungsi SECURITY DEFINER verifikasi), buat/rotasi session lewat fungsi definer yang menentukan `mfa_verified` hanya setelah verifikasi, atau RLS pada `sessions`.

- **[MEDIUM] `mail_worker.py:37-48,69-78` — satu baris outbox rusak memblokir seluruh antrean (poison pill).**
  - `InvalidToken` (atau error non-SMTP lain) dilempar dari `deliver_one`, transaksi di-rollback, `attempts` tidak naik, dan baris yang sama tetap `ORDER BY expires_at` paling awal. Bukti (P8): baris "bad" (token terenkripsi kunci lain, kedaluwarsa lebih awal) + baris "good" valid → 3 run berturut-turut `InvalidToken`, **email good tidak pernah terkirim**, kedua baris `attempts=0`. Berlangsung sampai baris rusak kedaluwarsa (≤1 jam) — cukup untuk memblokir reset/undangan lain, atau selamanya jika crash-loop menahan scheduler.
  - Fix: tangkap error dekripsi/format per baris, tandai `attempts`/dead-letter, lanjutkan ke baris berikutnya; tes untuk itu.

- **[MEDIUM] `migrations/auth_lifecycle.sql:103-188`, ADR "Migration owner … BYPASSRLS/superuser" — fungsi SECURITY DEFINER dimiliki superuser.**
  - Terverifikasi di DB hasil migrasi: owner `postgres` (superuser). Fungsi memakai konteks GUC `app.user_id`/`app.tenant_id` (dapat diset sesi runtime mana pun) dan melewati RLS. `search_path=pg_catalog, public` tanpa `pg_temp` di akhir. Parameter divalidasi ketat dan akses tidak ditemukan salah di fungsi yang ada, tetapi privilege superuser pada fungsi definer memperbesar dampak setiap bug berikutnya.
  - Fix: pemilik NOLOGIN khusus dengan hak minimum (+BYPASSRLS hanya jika perlu), `SET search_path = pg_catalog, public, pg_temp`, dokumentasikan di runbook migrasi.

### LOW

- **[LOW] `auth_lifecycle.py:77`, `auth.py:44-47` — cookie sesi basi memblokir penerimaan undangan akun baru.** `accept` memanggil `session_user` bila cookie ada; cookie kedaluwarsa/palsu → 401 "Silakan masuk kembali" walau penerima belum punya akun (P3: 401 dengan cookie basi vs 400 tanpa cookie). Fix: abaikan cookie yang tidak valid pada endpoint ini (tetap sertakan user hanya bila valid).
- **[LOW] `auth_support.py:13-15` — satu kunci Fernet tanpa `MultiFernet`/versi kunci.** Rotasi tidak mungkin tanpa migrasi data manual (ADR mengakui). Fix: `MultiFernet` + penanda versi kunci dan prosedur rotasi teruji.
- **[LOW] `mail_worker.py:40,60` — retry efektif 4×, bukan 5.** Max 5 percobaan × 15 menit (75 mnt) > masa berlaku 1 jam (`auth_support.py:53`). Selaraskan angka atau dokumentasi.
- **[LOW] `.github/workflows/ci.yml` — tanpa blok `permissions:` (token default), actions dipin tag bukan SHA; tes browser dan audit dependensi tidak ada di CI.** Handoff mengakui CI belum pernah dijalankan.
- **[LOW] `apps/web/next.config.ts:5-10` — header keamanan hanya untuk `/auth`; tidak ada CSP/HSTS.** Halaman auth memuat token dari fragmen dan menampilkan provisioning URI; CSP ketat layak ditambahkan.
- **[LOW] `identity.sql:43-44`, `page.tsx:164` — admin tidak dapat melihat daftar anggota; revoke meminta UUID mentah tanpa endpoint penemuan.** Tidak ada endpoint ubah/turunkan role. Fungsional untuk LMS-10, tetapi UI revoke saat ini tidak dapat dipakai tanpa akses DB.
- **[LOW] `auth.py:123-137` (+ ADR) — `memberships`, `security-events`, `invitations/accept`, `logout` hanya butuh session password-only untuk user yang sudah punya MFA.** Dinyatakan sengaja di ADR; dicatat sebagai risiko residual bila session dicuri.

## Acceptance criteria yang belum terpenuhi

Dari PROJECT-SPEC (LMS-01) dan ARCHITECTURE:

1. **MFA operator** (ARCHITECTURE "Auth implementation") — belum terpenuhi; diakui handoff/ADR/checklist. Bukan celah kode, tetapi gate sebelum real learner.
2. **Pemulihan faktor MFA** — tidak ada workflow; dikombinasikan dengan H-1 menghasilkan lockout permanen.
3. **Invitation/reset sampai inbox** — SMTP nyata tidak diuji; hanya callback tiruan. Tidak diverifikasi ulang oleh review ini.
4. **"MFA mandatory … every newly authenticated admin session"** — dipenuhi di `principal`, tetapi tidak berlaku saat enroll pertama (H-1).
5. **Isolasi tenant — "negative cross-tenant tests"**: terpenuhi untuk resource LMS-01 (36 tes lulus); tidak ada resource tenant lain untuk diuji. Least-privilege role runtime atas `users`/`sessions` belum memenuhi semangat kontrak (M-4).
6. **Release gates di PROJECT-SPEC** — TLS publik, rate limit edge, backup/restore drill, retensi, signoff manusia: belum ada. Hanya DB disposable yang dimigrasi; downgrade menghapus data (dengan benar didokumentasikan).
7. **Review independen** — laporan ini; belum sampai tahap re-review/persetujuan manusia.

## Hal yang dinilai baik (terverifikasi dari source/tes)

Token opak 256-bit hanya disimpan sebagai SHA-256; cookie HttpOnly/Secure/Lax; Origin eksak pada semua mutation; tenant hanya dari membership aktif per request; FORCE RLS; role runtime ditolak jika superuser/BYPASSRLS/pemilik tabel; fungsi definer memvalidasi token/konteks dan `REVOKE ... FROM PUBLIC`; token undangan/reset sekali pakai dengan lock advisory; reset mencabut semua session; BFF allowlist tanpa URL tujuan dari klien; secret tidak masuk audit; `.env` tidak ada dan di-ignore.

## Untested risks

- Kegagalan COMMIT alami (M-1), SMTP/TLS/SPF/DKIM nyata, browser/aksesibilitas (tes Playwright tidak dijalankan ulang), Linux/py3.12 dan image Docker, kerentanan dependensi (tanpa jaringan), perilaku di belakang Cloudflare/proksi (IP, header), beban/konkurensi di atas yang diuji author, restore dari backup, `compose up` end-to-end, race revoke-vs-revoke antar dua admin (deadlock tidak dicoba).
- `test_identity_postgres.py` tidak saya baca penuh; kecukupan assertion per tes tidak diaudit — hanya hasil eksekusi.

## Decision: **CHANGES_REQUESTED**

Alasan: H-1 (enroll MFA hanya dengan password, plus tanpa pemulihan) melemahkan kontrol admin MFA yang diwajibkan arsitektur; enam temuan MEDIUM terbukti dengan reproduksi; dan acceptance eksternal (MFA operator, pemulihan faktor, inbox nyata) masih terbuka. Setelah perbaikan H-1/M-1..M-6 dan tes regresinya, minta review ulang atas source terbaru. APPROVED, bila kelak diberikan, tetap bukan otoritas produksi; keputusan merge/deploy ada pada manusia.

Catatan operasional: kontainer reviewer `claude-review-pg16-lms01` (dan tiga database `maaher_test_review_*`) dihentikan (tidak dihapus) untuk inspeksi; mulai dengan `docker start claude-review-pg16-lms01`, hapus dengan `docker rm -f claude-review-pg16-lms01`.
