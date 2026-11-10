# LMS-01 — respons AUTHOR terhadap review Claude

Status: **perbaikan lokal siap review ulang; bukan approval dan bukan LMS-01
selesai/siap produksi**. Reviewer harus menilai source terbaru secara independen.
Nomor H1/M1–M6/L1–L7 di bawah mengikuti urutan kelompok severity pada laporan
asli. Urutan pekerjaan mengikuti permintaan pemilik: H1 → M4/M6 → M1 → M2 →
M3 → M5 → seluruh LOW. Tidak mengubah laporan reviewer atau meng-apply patch lama.

Laporan asli: `reviews/LMS-01-claude.md`, SHA-256
`004a19183409b152d0947ab6f5b99af2000d9dd3324c9a2c77ea66a4106032ce`.
Baseline GitHub tetap `8941a79dcf611df66c4ee43e78b902b62ddbfce2`.
Snapshot sebelum perbaikan: `/private/tmp/maaher-lms01-before-claude-fixes-20261109`.
Lihat [ADR-002](../docs/adr/002-auth-security-review.md),
[checklist](../docs/LMS-01-CHECKLIST.md) dan [handoff](../docs/LMS-01-HANDOFF.md).

## Penanganan setiap temuan

| ID | Penanganan dan bukti source | Regresi/bukti; status |
|---|---|---|
| H1 — bootstrap/takeover/recovery | `mfa.py`, `mfa_operator.py`, migrasi 0003. Password/email tidak berotoritas enroll. Request dan grant 256-bit terikat user/session/purpose, sekali pakai/10 menit; role operator terpisah. Pending tidak mengganti faktor aktif sampai OTP baru benar; recovery mengganti password dan revoke seluruh session/reset token. `trust_verified=false` untuk faktor warisan, elevasi session lama dibatalkan. Audit operator tidak hilang bersama session. | `test_h1_password_and_compromised_email_cannot_bootstrap_mfa`, authorization session-bound/replay, legitimate-owner recovery dari faktor legacy penyerang, boolean/production denied; browser recovery. **LOCAL_FIXED, PROD_BLOCKED**: adapter hanya sintetis test DB; root/operator MFA nyata belum dipilih/diintegrasikan. Tidak memakai email yang sudah dikuasai penyerang. |
| M4 — hash/session MFA runtime | DATABASE_URL tenant dan AUTH_DATABASE_URL verifier berbeda, role bercampur ditolak. Runtime tidak SELECT users/hash/session/factor/auth history atau INSERT session (true/false). Sensitive accept/reset hanya auth role. Resolver mengembalikan identitas/status dari capability yang valid; runtime RLS memakai capability tersebut, bukan GUC userid yang bisa dipalsukan. | `test_m4_runtime_actual_login_cannot_read_hashes_or_mint_mfa_sessions` **9 SQL langsung** sebagai LOGIN aktual maaher_api; semua privilege sensitif ditolak. `test_m4_forged_gucs_*` memastikan pemalsuan GUC tidak memberikan identitas/admin asing. **FIXED lokal, menunggu re-review**. Auth credential tetap tepercaya; bukan klaim aman terhadap RCE/SQL injection di verifier auth. |
| M6 — owner definer superuser | 9 fungsi dimiliki `maaher_definer` NOLOGIN/NOSUPERUSER/NOCREATEROLE, BYPASSRLS dengan grant minimum eksplisit; tidak owner tabel. search_path pg_catalog/public/pg_temp, PUBLIC EXECUTE dicabut. Role API/auth bukan anggota definer. Definer tidak SELECT hash/secret MFA, tidak INSERT session/CREATE schema. | `test_m6_definers_are_nonlogin_nonsuperuser_minimum_privilege`, metadata role/ACL/fungsi pada PostgreSQL nyata. **FIXED lokal, menunggu re-review**. Provision grup sebelum migrasi; jangan memberi membership definer ke service LOGIN. |
| M1 — respons mendahului COMMIT | Semua DB dependency memakai `scope='function'`; COMMIT di teardown selesai sebelum response start. DatabaseError dari query/commit menjadi **503 JSON terkontrol**, tanpa cookie sukses/detail SQL; status durable yang tidak diketahui tidak diklaim sukses. | `test_m1_real_uvicorn_does_not_send_headers_or_cookie_until_commit`: uvicorn nyata, COMMIT ditahan barrier, response hook belum menerima header/cookie, observer DB belum melihat session; setelah release 200+cookie langsung dapat dipakai. Failure login/logout: 503/no cookie, observer membuktikan rollback, cookie logout lama tetap berlaku. **FIXED**. Commit gagal disuntikkan, bukan klaim mereproduksi deadlock alami. |
| M2 — pertumbuhan anonim/retensi | `traffic.py`, auth_support counter fixed keyspace, pre-hash budget global 120/min dan network 30/min, empat concurrent password slots lintas worker. Unknown login tidak menulis auth event per request; tabel login_attempts lama tidak ditambah. Pool terbatas 100 password-only/20 MFA. `maintenance.py` + fungsi dedicated retention dan outbox PII scrub. | `test_m2_random_anonymous_inputs_*` mengulang 40+40 input acak: bounded Argon calls/bucket rows dan tanpa pertumbuhan NULL audit/login_attempts. Password slots dan retensi diuji; live identity/membership/session dipertahankan. **CODE_FIXED / POLICY_DEPLOY_PENDING**: hanya kebijakan sintetis dijalankan; horizon, scheduler, edge/IP trust dan monitoring produksi belum disetujui/dikonfigurasi. |
| M3 — korban dikunci throttle | Password benar tetap diperiksa di bawah resource budget dan tidak diveto failure counter; sukses mereset counter. Failure key email+network, bukan account global. Kuota OTP user+network bertahan lintas login; proof recovery punya budget terpisah. Pool password-only tidak mengusir session MFA atau recovery terotorisasi, tidak memveto semua login ketika credential holder memenuhi pool. Login/reset/recovery diserialisasi. | Reproduksi 10 salah → password benar **200**, salah berikutnya 401; attacker network tidak mengunci owner network. Regresi kuota OTP lintas login + OTP sah network owner; capacity exhaustion test mempertahankan MFA dan recovery pinned. **FIXED lokal**. Shared NAT/global capacity/DDoS tetap perlu edge/tuning; tidak mengklaim availability absolut. |
| M5 — poison outbox | `deliver_one` menangkap InvalidToken/format per baris, mencatat dead_at/error_code tetap/attempt dan menghapus token/alamat, lalu loop lanjut. Tiap message transaction commit terpisah. Tidak menyimpan exception/secret. | `test_m5_corrupt_outbox_is_quarantined_and_valid_message_still_sends`: cipher kunci lain dan token berformat salah → quarantine sekali, pesan valid berikutnya terkirim via callback, PII hilang. **FIXED lokal**; SMTP sungguhan belum diuji. |
| L1 — stale cookie | `session_user(optional=True)` pada accept hanya mengabaikan cookie invalid/expired. Akun lama tetap memerlukan session cocok dan MFA bila diwajibkan; fungsi SQL memeriksa capability, bukan userid dari caller. | `test_l1_stale_cookie_does_not_block_new_invitation_or_authorize_existing`: akun baru 200 dengan cookie basi; akun existing tidak mendapat authority. **FIXED**. |
| L2 — key rotation | Versioned `KeyRing`/MultiFernet; key aktif berbeda dari retained keys. `key_rotation.py` re-enkripsi factor/pending/outbox dalam satu transaksi, tidak mengubah trust/counter. Prosedur di ADR-002. | `test_l2_multifernet_rotation_*`: legacy→v2, decrypt dengan key baru saja, OTP recovery/mail token tetap valid; poison row membatalkan seluruh rotasi. **FIXED sintetis**; operasi key produksi masih di bawah gate operator/backup. |
| L3 — retry 4 bukan 5 | Interval 10 menit, max 5, TTL tetap satu jam: jadwal 0/10/20/30/40. Tidak memperpanjang token; scheduler terlambat bisa mengurangi jumlah aktual. Attempts exhausted dipurge/dead-letter. | `test_l3_five_smtp_attempts_fit_token_lifetime_*`: lima callback gagal, interval/schedule di dalam TTL, attempt ke-6 tidak dikirim dan PII scrub. **FIXED**. |
| L4 — CI privileges/pins/coverage | contents:read eksplisit; checkout/setup-python/setup-node dipin SHA dari ref resmi GitHub API. CI menyediakan PostgreSQL nyata dan credential terpisah, API/browser suites serta audit PyPI/npm. | Pemeriksaan policy lokal PASS: seluruh actions 40-hex SHA, read-only token, browser/audit jobs hadir. Semua command inti diuji lokal. **CONFIG_FIXED / GITHUB_RUN_PENDING**; tidak mengklaim workflow remote telah lulus. |
| L5 — headers/CSP | `proxy.ts` membuat nonce tiap response, overwrite CSP/nonce input client; pages dinamis, script policy produksi tanpa unsafe-inline/eval, styling CSS. Headers frame/referrer/nosniff/HSTS berlaku semua route termasuk BFF. | Browser menguji header/nonce berbeda tiap request, hydration normal, script tanpa nonce disisipkan ke HTML parser tetap ditolak (violation **dan** non-execution wajib). **FIXED lokal**. HSTS pada HTTP loopback bukan verifikasi TLS publik. |
| L6 — discover anggota/ubah role | Endpoint tenant-members dipaginasi, data terbatas tenant admin MFA. UI menampilkan email/peran dengan kontrol update/revoke, tidak meminta UUID manual. Fungsi change_member memvalidasi session/admin dan menserialisasi perubahan; self-demotion/revoke ditolak. | `test_l6_member_discovery_*`, pagination 102 anggota tanpa gap/duplikasi/record asing; role promotion menuntut MFA segera; revoke satu tenant tidak menghapus tenant lain. Browser discovery/change/revoke lulus. **FIXED**. |
| L7 — metadata/logout password-only | Session admin atau user dengan faktor confirmed memerlukan elevasi untuk memberships, security-events, acceptance akun existing dan logout. Exception sempit hanya login/reset serta request/enrollment/recovery proof/OTP yang tidak memberi authority sendiri. | `test_l7_password_only_session_*`: seluruh metadata/logout/accept ditolak 403 setelah login baru; request recovery memberi ID saja. **FIXED lokal**; tidak mengklaim perlindungan absolut terhadap pencurian session yang sudah ter-MFA. |

## Hasil nyata dan perubahan assertion

- API macOS/Python 3.13.5, PostgreSQL 16.15, DB
  `maaher_test_security_final_3`: **67 passed, 1 warning in 71.12s**.
- Linux/Python 3.12, DB `maaher_test_security_linux_3`, user nonroot,
  root filesystem read-only, no host mount/socket Docker:
  **67 passed, 2 warnings in 56.46s**.
- Chrome headless profil sementara, Next production + API nyata, DB
  `maaher_test_security_browser_4`: **5 passed (43.1s)**.
- Typecheck dan build Next PASS; image runtime/test Linux BUILD PASS.
- Fixture migrasi: 0001→head; head→0002→head; head→0001→head; base→head,
  preservasi legacy identity dan 15 tabel aplikasi hilang setelah base PASS.
- Compileall/pip check/verify-starter/Compose config PASS; audit runtime PyPI
  34 pin: 0 findings/errors; npm produksi: 0 vulnerabilities. Snapshot ini
  bukan audit OS/OpenSSL atau bukti runtime deployment aman.

Assertion tidak dilonggarkan untuk mengejar hijau:

1. Tes lama yang dapat membaca faktor melalui runtime kini menuntut permission
   denied; RLS auth connection diuji terpisah. Helper enrollment lama sekarang
   memperoleh proof operator sintetis melalui LOGIN lain; route password-only
   tanpa proof diuji ditolak secara eksplisit.
2. Kontrak throttle sengaja diperbaiki: assertion lama password benar→429
   diganti oleh reproduksi serangan yang menuntut password benar→200 dan counter
   direset. OTP tetap dibatasi lintas login pada network penyerang.
3. Run Linux awal 64 PASS/1 FAIL karena response COMMIT error 500 yang belum
   ditangani menutup keepalive sebelum GET berikutnya. **Kode aplikasi** diubah
   menjadi 503 terkontrol, bukan mengulang request atau menerima exception
   transport. Assertion exact 503/message/no-cookie/rollback/GET berikutnya
   tetap wajib pada client yang sama; run final dua platform PASS.
4. Percobaan CSP lewat `page.evaluate` tidak memberikan event yang diharapkan.
   Injeksi dipindah ke HTML parser dengan CSP response asli tidak diubah;
   assertion event pelanggaran dan non-execution **keduanya** tetap wajib.
   Tidak menambah unsafe-inline/eval atau mengecualikan test.
5. Tidak ada SKIP/xfail pada hasil final. Warning hanya deprecation httpx
   Starlette TestClient, cache pytest read-only di Linux dan warna log browser.

Tes dipecah menjadi `tests/conftest.py`, `auth_helpers.py`, identity suite dan
`test_review_regressions.py` agar regresi review dapat dibaca terpisah. Probe
server commit hanya berada di `tests/commit_probe_app.py`, bukan fitur/env hook
HTTP aplikasi produksi. Proses test mengeksekusi aplikasi sendiri, bukan kode
siswa. Tidak ada SMTP nyata atau probe pihak ketiga.

## Yang sengaja belum diaktifkan

- Batas H1: recovery faktor yang diuji memerlukan session password-valid.
  Kehilangan password **dan** email sekaligus memerlukan full account recovery
  dari root/provider independen yang sudah terdaftar; adapter itu belum ada.
  Karena itu H1 bukan CLOSED end-to-end: takeover password/email-only diblokir,
  recovery skenario P6 diuji, tetapi produksi dan total credential loss tetap
  membutuhkan keputusan/integrasi yang direview. Tidak merekomendasikan SQL
  manual atau email yang sudah dikompromikan untuk melewati batas ini.
- Provider bootstrap/recovery dan MFA operator produksi: perlu keputusan root
  independen dari email/password, verifikasi perangkat/identitas, host/IdP/secret
  store bermfa, audit dan emergency/revocation. Adapter saat ini menolak produksi
  dan DB non-test; mengganti boolean atau nama DB bukan penyelesaiannya. Pilihan
  belum dianggap disetujui tanpa jawaban pemilik. Perlu integrasi yang direview
  terpisah sebelum gate bisa dibuka, bukan sekadar SMTP/env flag.
- Retensi produksi: horizon sintetis perlu kebijakan/approval, scheduler,
  monitoring dan backup/hold. Tidak ada data pengguna yang dibersihkan.
- Edge identity/rate limit, TLS publik, email provider/inbox UAT, backup/restore,
  GitHub workflow nyata serta review ulang independen masih terbuka.

Migration 0003 menurunkan trust/elevasi MFA lama secara sengaja tetapi tidak
menghapus identity/ciphertext. Jangan menerapkannya ke layanan nyata sebelum
recovery/provider siap dan maintenance/backup disetujui. Downgrade mengembalikan
privilege/fungsi 0002 yang lebih lemah; bukan rollback aman produksi. Seluruh
migrasi/retensi/rotasi dalam sesi ini hanya pada database baru sintetis.

## Artefak re-review

- Full patch terbaru: `reviews/LMS-01-author.patch` terhadap GitHub baseline.
- Diff pasca-Claude: `reviews/LMS-01-post-claude.patch` terhadap snapshot yang
  direview; snapshot manifest/patch lama dipertahankan dalam `reviews/`.
- `LMS-01-review-manifest.json`: hash baseline/source/full dan incremental patch,
  serta fingerprint laporan Claude asli. Response ini masuk diff; patch/manifest
  dan report reviewer tidak direkursikan ke dalam patch.
- Jangan apply patch ke workspace aktif. Claude perlu memeriksa source terbaru,
  khususnya boundary auth credential, trusted bootstrap adapter, function owner,
  pool/rate/retention, barrier commit, CSP dan rollback 0003. Hasil ini bukan
  pengganti penilaian independen; tidak ada commit, merge atau deploy.
