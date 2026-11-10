# LMS-01 — handoff 2026-11-09

## Tahap Auth0/OIDC disetujui — 10 November 2026 WIB

Implementasi development terbaru memakai migration **0004_auth0_oidc**.
Lihat [handoff Auth0](LMS-01-AUTH0-HANDOFF.md) dan
[setup tenant/aplikasi](AUTH0-SETUP.md) untuk status/test terbaru.
Tenant Auth0 nyata belum dibuat, H1 produksi tetap terbuka, tidak ada merge/deploy.
Bagian 0003 dan 71/67 tes di bawah adalah catatan historis.

## Tambahan cloud — 10 November 2026 WIB

Arsip pemilik dan patch terhadap baseline GitHub berhasil diverifikasi; 75
berkas cocok dengan manifest setelah lima file tersembunyi yang tidak masuk
ZIP dipulihkan dari patch. Suite awal cloud: 67 PASS. Dua masalah kedaluwarsa
MFA direproduksi dan diperbaiki; suite setelah perbaikan: **71 PASS tanpa
SKIP**, PostgreSQL 16.15/Python 3.12.14. Browser Chromium aktual: **5 PASS**.
Build/typecheck dan audit dependensi juga lulus. Rincian, batas verifikasi dan
cara menerapkan perubahan lokal ada pada
[validasi cloud](../reviews/LMS-01-cloud-validation.md) dan
[panduan patch](LMS-01-CLOUD-APPLY.md).

Ini validasi/perbaikan AUTHOR tambahan, bukan persetujuan Claude. H1 produksi,
full account recovery, SMTP/inbox nyata dan gate operasional tetap terbuka.
Data dan kode Mac tidak diubah oleh sesi cloud. Catatan historis di bawah
dipertahankan sebagai bukti run sebelumnya.

Status: inti auth lokal terimplementasi dan teruji, **LMS-01 BELUM SELESAI**
karena acceptance eksternal/operasional belum terpenuhi. Belum untuk data siswa
nyata. Tidak ada commit, merge, push, deploy, atau perubahan Timedoor.


## Hasil terbaru — perbaikan review Claude, siap re-review

**Status tetap BELUM SELESAI/siap produksi.** Seluruh temuan kode H1/M1–M6 dan
L1–L7 ditangani dan diregresikan; trust operator/bootstrap/recovery produksi
sengaja ditolak sampai keputusan serta integrasi independen tersedia. Tidak
ada persetujuan yang disimpulkan dari pertanyaan pemilik yang belum dijawab.
Laporan Claude asli tetap utuh, CHANGES_REQUESTED; belum ada re-review/signoff.
Bagian Riwayat di bawah merekam hasil/status pada waktu itu, bukan perintah
atau keputusan release untuk source terbaru.

Dokumen terkini: [checklist](LMS-01-CHECKLIST.md),
[ADR-002](adr/002-auth-security-review.md), dan
[respons per temuan](../reviews/LMS-01-author-response.md).

### Perubahan penting

- Bootstrap MFA tidak lagi mungkin dengan password/email saja. Grant operator
  sekali pakai terikat user/session/purpose; pending tidak mengganti faktor lama
  sebelum OTP baru benar. Recovery mengganti password, revoke seluruh session/
  reset token dan mencatat audit operator yang tetap ada setelah session hilang.
  Faktor warisan 0002 tidak otomatis trusted; elevasi session lama dibatalkan
  tanpa menghapus identity/ciphertext. Adapter hanya local/test dan DB sintetis.
- DATABASE_URL role tenant tidak membaca hash/users/session/factor atau membuat
  session true/false. AUTH_DATABASE_URL terpisah untuk verifier tepercaya;
  RLS runtime memakai capability session tervalidasi, bukan GUC userid yang
  bisa dipalsukan. Definer NOLOGIN/non-superuser, pg_temp terakhir, no PUBLIC
  execute dan grant minimum (bahkan tidak membaca hash/secret MFA atau INSERT
  session). Daftar/ubah anggota memvalidasi session admin MFA secara langsung.
- Semua dependency DB scope=function: COMMIT mendahului response/cookie.
  DatabaseError menjadi 503 terkontrol, tanpa cookie sukses; hasil commit yang
  belum dapat dipastikan tidak dilaporkan sukses atau otomatis diulang.
- Anggaran sebelum Argon2, empat concurrent password slots, fixed keyspace,
  tanpa auth row anonim per email acak. Password benar tidak ditolak akibat
  failure counter; OTP user+network tidak reset lewat login ulang. Budget proof
  recovery terpisah. Pool password-only/MFA terpisah dan recovery berotorisasi
  dilindungi dari eviksi; login/reset/recovery diserialisasi.
- Retensi lewat role maintenance terbatas dan kebijakan sintetis; identitas/live
  state dipertahankan. Worker quarantine payload rusak lalu melanjutkan pesan
  valid, scrub token/recipient, maksimal lima retry tiap 10 menit dalam TTL.
- MultiFernet/versioned keyring + prosedur rotasi atomik, stale cookie fix,
  protected metadata/logout, daftar anggota/pagination/role/revoke di UI,
  CSP nonce/dynamic rendering/CSS serta security headers seluruh route.
- CI read-only permissions, action SHA resmi, credential terpisah, browser dan
  audit jobs. Workflow GitHub belum dijalankan; konfigurasi/policy dan command
  inti diuji lokal. Tidak ada SMTP nyata, ingress/host MFA atau TLS publik diuji.

### Hasil nyata final

| Pemeriksaan | Hasil |
|---|---|
| API macOS/Python 3.13.5, DB maaher_test_security_final_3 | **67 passed, 1 warning in 71.12s**, tanpa SKIP |
| API Linux/Python 3.12, DB maaher_test_security_linux_3 | **67 passed, 2 warnings in 56.46s**, tanpa SKIP |
| Chrome lokal headless + Next production + API nyata, DB maaher_test_security_browser_4 | **5 passed (43.1s)** |
| Upgrade 0001→0003, rollback 0002/0001/base dan upgrade lagi | PASS di fixture bersama kedua platform; identity lama dipertahankan, 15 tabel aplikasi hilang setelah base |
| SQL privilege LOGIN runtime aktual maaher_api | 9 operasi hash/session/fungsi auth sensitif ditolak; forged GUC dan metadata/ACL definer PASS |
| Uvicorn nyata: COMMIT ditahan dan COMMIT gagal pada login/logout | Tidak ada header/cookie sebelum release; injected failure wajib 503, tanpa cookie sukses, rollback DB dan request lanjutan pada client sama PASS |
| npm typecheck dan production build Next 16.4.5 | PASS; dijalankan berurutan |
| Dockerfile runtime/test Linux | BUILD PASS pada image validasi baru; tidak deploy |
| Compileall, pip check, verify-starter, Compose config sintetis | PASS |
| PyPI runtime advisory snapshot / npm production audit | 34 pin, 0 findings/errors / 0 vulnerabilities |
| Policy CI lokal | contents:read, seluruh actions 40-hex SHA, browser/audit jobs hadir: PASS; bukan remote CI run |

67 kasus = 2 unit, 1 health, 64 integrasi PostgreSQL; 31 kasus regresi baru pada
`apps/api/tests/test_review_regressions.py`. Fixture/helper dipisah agar review
lebih mudah. Browser mencakup full lifecycle, legitimate-owner MFA recovery,
member discovery/change/revoke dan parser-level CSP rejection. Password-only
bootstrap helper lama sekarang memakai otorisasi sintetis lewat LOGIN operator
lain; tidak ada backdoor HTTP untuk test. Probe COMMIT hanya test uvicorn target
`tests/commit_probe_app.py`, bukan env fitur aplikasi produksi.

Kegagalan selama perbaikan dan perbaikannya (bukan assertion yang dilonggarkan):

- Roundtrip 0003→0002→0003 pertama gagal karena constraint audit belum kembali;
  DROP IF EXISTS/recreate allowlist diperbaiki. Run berikutnya lulus semua jalur.
- Linux awal 64 PASS/1 FAIL: setelah COMMIT error 500 tak tertangani, koneksi
  keepalive ditutup sehingga GET selanjutnya reset. Kode kini menangani error
  DB sebagai 503 sebelum response, bukan mengabaikan error/retry test. Assertion
  no-cookie/rollback/GET client sama tetap berlaku; final 67 PASS.
- Browser awal 3 PASS/1 FAIL pada event CSP dari injeksi DevTools evaluate.
  Metode diganti parser-delivered HTML, CSP response asli dipertahankan;
  violation dan non-execution keduanya wajib. Tidak menambah unsafe-inline/eval.
- Kuota OTP lintas login dan kapasitas session ditambah sebagai regresi supaya
  solusi lockout tidak memberi jalur baru brute-force atau penguncian korban.

Warning final: deprecation Starlette TestClient httpx; Linux cache pytest tidak
writable karena filesystem read-only; log warna NO_COLOR/FORCE_COLOR browser.
Tidak mempengaruhi assertion. Audit advisori bukan audit OS/OpenSSL atau bukti
aman terhadap RCE/verifier compromise/serangan kapasitas atau deployment nyata.

### Lingkungan yang dipertahankan

Container baru PostgreSQL: `maaher-lms01-security-review-fixes-20261109`, PG
**16.15**, port saat pengujian **127.0.0.1:53980**, trust auth **khusus sintetis**.
14 database baru hasil semua run tetap ada: security_1..4, security_final/
_final_2/_final_3, security_browser/_2/_3/_4, security_linux/_2/_3 (semuanya
berprefix `maaher_test_`). Final revision `0003_security_review`.

Container Linux test baru juga dipertahankan untuk docker logs/inspeksi:
`maaher-lms01-security-review-linux-20261109` (run awal exit 1),
`...-linux-2-20261109` dan `...-linux-3-20261109` (exit 0).
Mereka nonroot, root filesystem read-only, tmpfs, cap-drop ALL, no-new-privileges,
1 GiB/2 CPU, tanpa host mount/socket Docker. Image:
`maaher-lms01-security-review-test:20261109` dan
`maaher-lms01-security-review-api:20261109`.

PostgreSQL baru dihentikan setelah seluruh tes/inspeksi; tidak dihapus.
Container/database author sebelumnya dan `claude-review-pg16-lms01` tidak
pernah dinyalakan, dihentikan, dihapus atau dimigrasi pada pekerjaan ini.
Tidak ada rm/down/prune/reset, tidak ada cleanup user data. Data sintetis yang
sengaja expired/poison pada DB baru hanya diproses untuk regresi retensi/rotasi.
Snapshot sebelum perbaikan ada di
`/private/tmp/maaher-lms01-before-claude-fixes-20261109`.

### Perintah reproduksi dari root

Jangan mengulang pada DB hasil: fixture mensyaratkan database kosong. Untuk
review ulang, mulai container baru ini, baca port aktual, buat DB kosong baru
lalu isi keenam URL ke DB tersebut. LOGIN test di cluster baru ini:
maaher_api/runtime, maaher_auth_login/auth, maaher_operator_login/mfa_operator,
maaher_mail_login/mailer, maaher_maintenance_login/maintenance. Semua terpisah,
NOBYPASSRLS/nonowner; hanya role NOLOGIN definer yang memerlukan BYPASSRLS.

```sh
docker start maaher-lms01-security-review-fixes-20261109
docker port maaher-lms01-security-review-fixes-20261109 5432
docker exec maaher-lms01-security-review-fixes-20261109 createdb -U postgres maaher_test_security_rereview
# Ganti 53980 bila docker port berubah setelah restart.
export TEST_MIGRATION_DATABASE_URL=postgresql://postgres@127.0.0.1:53980/maaher_test_security_rereview
export TEST_DATABASE_URL=postgresql://maaher_api@127.0.0.1:53980/maaher_test_security_rereview
export TEST_AUTH_DATABASE_URL=postgresql://maaher_auth_login@127.0.0.1:53980/maaher_test_security_rereview
export TEST_OPERATOR_DATABASE_URL=postgresql://maaher_operator_login@127.0.0.1:53980/maaher_test_security_rereview
export TEST_MAIL_DATABASE_URL=postgresql://maaher_mail_login@127.0.0.1:53980/maaher_test_security_rereview
export TEST_MAINTENANCE_DATABASE_URL=postgresql://maaher_maintenance_login@127.0.0.1:53980/maaher_test_security_rereview
PYTHONPATH=apps/api .venv/bin/python -m pytest -q -ra --tb=short apps/api/tests
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
.venv/bin/python -m compileall -q apps/api/app apps/api/migrations apps/api/tests scripts
.venv/bin/python scripts/verify-starter.py
.venv/bin/python scripts/audit-api-dependencies.py
npm --prefix apps/web audit --omit=dev
```

Untuk browser: buat DB kosong **lain**, ubah TEST_MIGRATION/DATABASE/AUTH/
OPERATOR URLs ke DB browser itu, lalu:

```sh
PLAYWRIGHT_CHANNEL=chrome .venv/bin/python scripts/test-lms01-browser.py
```

Pada Linux CI dengan Chromium terpasang, tidak perlu channel chrome. Wrapper
memakai cookie HTTP insecure hanya pada local loopback eksplisit; API suite
terpisah tetap memverifikasi Secure cookie pada HTTPS TestClient. Ini bukan
bukti TLS publik. Image Linux test dibangun dengan:

```sh
docker build --file infra/Dockerfile.lms01-test --tag maaher-lms01-security-review-test:20261109 apps/api
```

Run Linux memakai `--network container:maaher-lms01-security-review-fixes-20261109`
dan keenam TEST_* URLs ke loopback **5432** di container, database baru lainnya,
serta image tersebut. Jangan gunakan `--rm` pada container yang ingin dipertahankan;
semua run dalam pekerjaan ini diberi nama unik dan disimpan. Detail hardening
run ada pada hasil inspeksi/command sesi dan ADR; tidak ada host mount/runner.

### Baseline dan artefak review

Laporan `reviews/LMS-01-claude.md` asli SHA-256
`004a19183409b152d0947ab6f5b99af2000d9dd3324c9a2c77ea66a4106032ce`
tetap utuh. `reviews/LMS-01-author-response.md` mencakup setiap H/M/L, tes,
batas klaim dan status eksternal. Source serta response disiapkan untuk review
ulang independen; jangan mengganti laporan lama dengan laporan approval.

Full patch tetap terhadap GitHub `8941a79dcf611df66c4ee43e78b902b62ddbfce2`
(25 blob diverifikasi terhadap snapshot tree/payload yang tersimpan). Tidak ada
Git head baru/root Git diinisialisasi, metadata `maaher-lms/.git` tidak diubah.
`reviews/LMS-01-post-claude.patch` memberi diff incremental terhadap source yang
direview; patch dan manifest yang direview disimpan sebagai
`LMS-01-author-before-claude-fixes.patch` dan `LMS-01-reviewed-manifest.json`.
Manifest baru memuat hash kedua diff, source dan fingerprint laporan asli.
Tidak ada patch/manifest recursive, cache, env aktif atau secrets pada diff.

```sh
.venv/bin/python scripts/build-lms01-review.py --baseline-payload /private/tmp/maaher-lms-baseline-payload-20261109.json --baseline-tree /private/tmp/maaher-lms-tree-20261109.json --reviewed-snapshot /private/tmp/maaher-lms01-before-claude-fixes-20261109
```

Generator memverifikasi snapshot/file hashes; `git apply --check -p2` dijalankan
terpisah terhadap baseline standalone dan snapshot sebelum perbaikan, tanpa
meng-apply patch. Untuk root repo GitHub gunakan strip 1/default; root starter
standalone strip 2. Jangan apply patch lama atau baru ke workspace aktif.

### Gate yang tetap terbuka dan risiko rollback

- Root operator MFA independen/production bootstrap-recovery provider belum
  dipilih atau diintegrasikan. Tidak cukup menguasai email atau mengisi boolean;
  adapter test menolak produksi/non-test DB. Butuh identitas terdaftar/perangkat
  yang diverifikasi, host/IdP/secret-store bermfa, revocation/emergency/audit dan
  integrasi yang direview. Jangan mengganti nama DB nyata untuk melewati gate.
- Recovery faktor yang diuji mengasumsikan pemilik masih dapat login password.
  Full account recovery bila password dan email sama-sama hilang belum ada;
  perlu root/provider independen yang dapat membuktikan perangkat/identitas
  terdaftar tanpa keduanya. H1 tidak diklaim CLOSED end-to-end atau diselesaikan
  oleh email/SQL manual. Takeover password/email-only sudah diblokir lokal dan
  recovery skenario P6 diuji; penggunaan nyata tetap ditolak.
- Retensi produksi: horizon 1/30/365/7 hari sintetis memerlukan keputusan
  kebijakan, scheduler/monitoring, hold dan backup/restore. Tidak ada job yang
  diaktifkan pada data pengguna.
- SMTP/inbox nyata, konfigurasi IP tepercaya/edge secret, TLS, load test,
  backup/restore drill, remote GitHub CI dan re-review Claude/human approval
  belum selesai. Karena itu LMS-01 tidak dinyatakan selesai/untuk siswa nyata.
- 0003 menambah trust/policy/grant dan membatalkan elevasi MFA lama. Downgrade
  0003 menghapus struktur/kolom baru dan mengembalikan privilege 0002 yang lebih
  lemah; bukan rollback keamanan produksi. Identity/ciphertext lama tidak
  dihapus saat upgrade. Roles tetap ada; downgrade base tetap destruktif seperti
  didokumentasikan sebelumnya. Semua roundtrip hanya pada DB baru sintetis.
- Tidak ada commit, push, merge, deploy atau perubahan Timedoor.

## Riwayat sebelum perbaikan Claude — invitation/reset/MFA dan validasi lokal

Bagian ini beserta [checklist acceptance](LMS-01-CHECKLIST.md) menggantikan
status/sisa pekerjaan yang sudah kedaluwarsa pada riwayat tahap 1 di bawah.
Keputusan dan konfigurasi konkret ada pada [ADR-001](adr/001-auth-lifecycle.md).
Permintaan pemilik memperluas tahap 1 ke acceptance LMS-01 lengkap; ticket
`docs/tickets/LMS-01.md` mencatat batas baru. Semua perubahan pengguna tetap
dipertahankan; patch tidak pernah di-apply ke workspace aktif.

Implementasi baru:

- Invitation admin bertenant/role/email, token SHA-256 satu jam dan sekali pakai.
  Existing account harus login sendiri; password/role lama tidak ditimpa.
  Resend membatalkan token lama; admin revoked/tenant disabled membatalkan
  otoritas invitation. Penerimaan bersamaan hanya satu yang berhasil.
- Reset password dengan respons request generik, throttling PostgreSQL,
  token satu jam/sekali pakai. Konfirmasi atomik mengganti hash Argon2,
  mencabut semua session/reset token, tanpa menghapus MFA.
- MFA TOTP PyOTP, secret Fernet, pending enrollment sepuluh menit, batas
  percobaan lintas session, anti-replay atomik, token session dirotasi setelah
  verify. Admin tidak dapat memakai fungsi tenant tanpa MFA pada session
  tersebut; promosi role pada session yang sama langsung terkena gate.
- Audit lifecycle login/logout/reset/MFA bersifat global per-user dengan RLS;
  audit tenant mencatat actor/action/target/waktu untuk invitation/revoke.
  Role runtime tidak dapat UPDATE/DELETE kedua audit. Secret tidak dicatat.
- Route revoke membership berscope tenant dan mempertahankan tenant lain.
  Undangan tidak dapat memulihkan membership revoked atau mengubah role lama.
- Outbox token terenkripsi, worker email terpisah dengan role mail-only,
  SMTP_SSL terverifikasi, retry tertunda 15 menit/max 5, payload dihapus saat
  terkirim/kedaluwarsa. Tes memakai callback pengiriman tiruan.
- UI `/auth` berbahasa Indonesia, BFF allowlist, cookie HttpOnly, tautan email
  melalui fragmen URL, referrer-policy no-referrer. Tautan juga terbaca jika
  halaman auth sudah terbuka di tab yang sama. Label peran diperbaiki berdasarkan
  kegagalan browser; role/action ditampilkan dalam bahasa Indonesia.
- Compose memakai credential API terbatas, origin/key eksplisit, dan job
  migrasi/mail terpisah. Owner tidak otomatis diberikan ke API. Tidak ada
  `compose up` atau deployment yang dijalankan. CI dikonfigurasi PostgreSQL
  disposable supaya integrasi tidak SKIP, tetapi GitHub workflow belum dijalankan.

Hasil nyata final (tanpa SKIP):

| Validasi | Hasil |
|---|---|
| macOS 13 / Python 3.13.5, PostgreSQL 16.15, database `maaher_test_lms01_final_mac` | **36 passed, 1 warning in 21.65s** |
| Linux / Python 3.12, user container nonroot, PostgreSQL 16.15, database `maaher_test_lms01_final_linux` | **36 passed, 2 warnings in 32.91s** |
| Chrome lokal headless + Next production + API nyata, database `maaher_test_lms01_browser_3` | **2 passed (9.9s)** |
| Upgrade data 0001 → 0002; downgrade 0001 → upgrade; downgrade base → upgrade head | PASS dalam fixture kedua suite API; data tahap 1 diperiksa setelah upgrade dan rollback parsial; 11 tabel diperiksa hilang setelah base |
| npm typecheck (`next typegen` lalu `tsc`) dan production build Next 16.4.5 | PASS |
| Dockerfile runtime API + lock, image `maaher-lms01-api-validation:20261109` | BUILD PASS; tidak dideploy |
| Import aplikasi dalam image runtime, `--network none`, tanpa credential | PASS: Python 3.12.16, Maaher LMS API |
| `pip check`, compileall API/migrations/tests/scripts, verify-starter | PASS |
| PyPI runtime advisory snapshot, 34 pin final | **0 findings/errors** |
| `npm audit --omit=dev --json` | **0 vulnerabilities** |
| `docker compose config --quiet` dengan nilai sintetis | PASS; bukan uji startup/deploy/SMTP |

Suite terdiri dari 2 unit, 1 health, 33 integrasi PostgreSQL. Dua tes browser
terpisah mencakup login admin→MFA→invitation→accept→logout→reset dan penolakan
BFF untuk Origin/path/body tidak valid. Browser memakai Chrome terpasang
dengan profil sementara, tidak menyentuh profil pengguna. Playwright Chromium
bundled terbaru tidak dapat diinstal karena macOS 13 tidak didukung; fallback
channel Chrome benar-benar dijalankan dan lulus. Tes browser memakai HTTP
loopback dengan cookie insecure khusus `APP_ENV=local` eksplisit; Secure cookie
tetap diverifikasi oleh tes API dengan HTTPS TestClient. Bukan uji TLS browser
deployment, aksesibilitas menyeluruh atau inbox email nyata.

Catatan kegagalan/perbaikan selama sesi:

- Suite awal lifecycle: 33 PASS, bertambah menjadi 36 setelah tes konkurensi
  reset/MFA dan penolakan credential worker ditambahkan.
- Browser run 1: 1 gagal/1 lulus karena label Peran mencakup teks opsi; label
  diperbaiki. Run 2: 1 gagal/1 lulus karena navigasi fragmen pada tab yang sama
  tidak memicu pembacaan token; listener hashchange diperbaiki. Run 3: 2 PASS.
- Satu typecheck bertabrakan dengan build yang meregenerasi `.next/types` dan
  melaporkan file generated tidak ada. Dijalankan ulang berurutan: PASS.
  `typecheck` kini menjalankan `next typegen` agar dapat dipakai pada checkout baru.
- Audit awal menemukan 27 entri advisori (termasuk alias ganda) pada
  cryptography 46.0.3 dan Starlette 0.46.2. Final memakai FastAPI 0.162.2,
  Starlette 1.10.0, cryptography 50.0.2 dan PyOTP 2.9.0. Cryptography dibangun
  dari source di Mac; Linux memakai wheel. Audit final nol advisori yang
  dilaporkan PyPI, bukan jaminan bebas kerentanan/penilaian OpenSSL sistem.
- Warning final Mac: Starlette TestClient masih menerima httpx 0.28.1 dengan
  deprecation (httpx2 disarankan upstream). Linux menambah warning cache pytest
  karena `/app` tidak writable bagi user tester. Browser memberi warning
  NO_COLOR/FORCE_COLOR. Tidak memengaruhi assertion dan tidak dibypass.

Dependency snapshot tersedia pada `apps/api/requirements.lock` (34 runtime),
`requirements-dev.lock` (42 development), serta `apps/web/package-lock.json`.
Linux benar-benar menginstal snapshot dan menjalankan suite. Dockerfile API
memakai runtime lock; web dan CI memakai npm ci. Base image/tag serta library
OS tetap perlu kebijakan update/security scanning menjelang release.

Perintah utama final dari root workspace (port aktual sesi ini 50686):
Perintah npm di bawah ditulis dengan `--prefix` agar dapat disalin dari root;
sesi menjalankannya secara ekuivalen dengan working directory `apps/web`.

```sh
.venv/bin/python -m pip install --disable-pip-version-check --timeout 120 --retries 2 -r apps/api/requirements-dev.txt
env TEST_MIGRATION_DATABASE_URL=postgresql://postgres@127.0.0.1:50686/maaher_test_lms01_final_mac TEST_DATABASE_URL=postgresql://maaher_api@127.0.0.1:50686/maaher_test_lms01_final_mac PYTHONPATH=apps/api .venv/bin/python -m pytest -v -ra --tb=short apps/api/tests
docker build --file infra/Dockerfile.lms01-test --tag maaher-lms01-test:20261109 apps/api
docker run --rm --network container:maaher-lms01-validation-20261109 --env TEST_MIGRATION_DATABASE_URL=postgresql://postgres@127.0.0.1:5432/maaher_test_lms01_final_linux --env TEST_DATABASE_URL=postgresql://maaher_api@127.0.0.1:5432/maaher_test_lms01_final_linux maaher-lms01-test:20261109
env TEST_MIGRATION_DATABASE_URL=postgresql://postgres@127.0.0.1:50686/maaher_test_lms01_browser_3 TEST_DATABASE_URL=postgresql://maaher_api@127.0.0.1:50686/maaher_test_lms01_browser_3 PLAYWRIGHT_CHANNEL=chrome .venv/bin/python scripts/test-lms01-browser.py
docker build --tag maaher-lms01-api-validation:20261109 apps/api
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
npm --prefix apps/web audit --omit=dev --json
.venv/bin/python scripts/audit-api-dependencies.py
.venv/bin/python -m pip check
.venv/bin/python -m compileall -q apps/api/app apps/api/migrations apps/api/tests scripts
.venv/bin/python scripts/verify-starter.py
```

Perintah browser di atas dijalankan setelah `npm ci/build`; dependensi Playwright
terpin pada package-lock. **Jangan rerun suite ke database hasil ini**: buat
database kosong `maaher_test_*` baru dengan `docker exec ... createdb -U postgres
NAMA_BARU`, lalu ubah kedua URL ke nama tersebut. API suite/browser wrapper
menolak DB bukan test atau DB nonkosong. Role maaher_runtime/API sudah ada
dari validasi sebelumnya; sesi ini menambah grup `maaher_mailer` NOLOGIN pada
cluster disposable sebelum migrasi. Semua URL yang ditampilkan tanpa password
hanya berlaku untuk cluster trust berisi data sintetis ini, bukan konfigurasi
deployment. Port berubah setelah restart; baca `docker port ... 5432`.

Data dan lingkungan:

- Container PostgreSQL yang dipakai hanya `maaher-lms01-validation-20261109`.
  Database lama `maaher_test_lms01`/`_fixed` tetap ada, begitu pula seluruh
  percobaan `_lifecycle_1` s.d. `_4`, `_browser_1` s.d. `_3`, `_linux_1` dan
  `_final_mac`/`_final_linux`. Tidak ada database pengguna yang disentuh.
- Dua proses API pada tes restart, API/Next pada tes browser dan container tes
  Linux berhenti otomatis. Container PostgreSQL dihentikan setelah inspeksi,
  tanpa menghapus container/database/volume. Image validasi tetap ada lokal.
- Snapshot sebelum pekerjaan ini ada di
  `/private/tmp/maaher-lms01-before-completion-20261109`; tidak dipakai untuk
  overwrite source. Root tetap bukan repo Git; `maaher-lms/.git` tidak diubah.

Berkas berubah mencakup API auth/support/lifecycle/MFA/mail, migrasi baru,
tes PostgreSQL dan browser/harness, dependencies/lock/Dockerfile/.dockerignore,
halaman auth/BFF/config web, Compose, role SQL, CI, ADR/checklist/ticket/setup/
arsitektur/handoff, serta alat audit/review. File generated Next env/types config
yang dibutuhkan typegen ikut diff; cache, node_modules, `.venv`, active `.env`
dan artefak browser tidak masuk patch.

Review dan baseline:

- Baseline tetap GitHub `8941a79dcf611df66c4ee43e78b902b62ddbfce2`, seluruh source
  berada di `maaher-lms-starter/`. Payload/tree baseline lokal berisi 25 blob;
  generator memverifikasi hash blob terhadap tree sebelum membuat diff.
- `reviews/LMS-01-author.patch` diperbarui dari baseline tersebut ke source
  workspace terbaru, termasuk rollback 0001, tes tahap sebelumnya dan semua
  perubahan baru. Ini full diff, termasuk berkas lokal yang sudah ada sebelum
  sesi ini; tidak semua baris baru terhadap remote adalah karya sesi terbaru.
- Patch lama dipertahankan sebagai `reviews/LMS-01-author-before-completion.patch`.
  `reviews/LMS-01-review-manifest.json` merekam baseline, hash patch dan hash
  source per berkas. Isi direktori reviews tidak masuk patch untuk menghindari
  self-reference. Generator: `scripts/build-lms01-review.py`.
- Verifikasi nyata: **25 blob baseline cocok**, **59 berkas berubah** pada full
  diff, seluruh hash source dan patch cocok dengan manifest, dan
  `git apply --check -p2` terhadap `/private/tmp/maaher-lms-baseline-20261109`
  PASS. Patch mencakup `DROP POLICY member_tenants ON tenants` pada rollback
  0001. Pemeriksaan ini tidak meng-apply patch atau mengubah baseline/workspace.
- Jalankan generator menggunakan payload/tree baseline yang diverifikasi:

```sh
.venv/bin/python scripts/build-lms01-review.py --baseline-payload /private/tmp/maaher-lms-baseline-payload-20261109.json --baseline-tree /private/tmp/maaher-lms-tree-20261109.json
```

Patch hanya untuk checkout review terpisah. Pada root repo GitHub gunakan
strip 1 (default git apply); pada folder starter standalone gunakan `-p2`.
Jangan apply ke workspace aktif atau memindah/reset Git metadata pengguna.
Claude Code wajib review terpisah, terutama fungsi SECURITY DEFINER, RLS,
MFA/secret lifecycle, worker permission, BFF dan rollback. Review harus memakai
source terbaru, bukan patch historis. Belum ada review Claude/signoff manusia.

Belum selesai dan ketergantungan eksternal:

- Invitation/reset sampai inbox: SMTP account/domain, SPF/DKIM/DMARC, TLS
  egress, role LOGIN mail-only, key stabil, scheduler/monitoring dan UAT email.
  Adapter dan antrean diuji; **pengiriman SMTP nyata belum diuji/dijalankan**.
- **MFA operator arsitektur belum terpenuhi end-to-end**: tidak ada operator
  API/global role; CLI development bukan bukti MFA host/identity/secret-store.
  Perlu audit server, pilihan kontrol MFA operator, least privilege dan audit.
- Pemulihan faktor MFA memerlukan verifikasi identitas/operator bermfa,
  persetujuan dan uji recovery; tidak tersedia bypass via password/email.
- TLS publik, edge rate limit global, retensi, backup/restore drill, audit
  library OS/deployment dan review independen belum selesai. Lihat ADR untuk
  konfigurasi konkret. Tidak ada klaim LMS-01 selesai atau siap siswa nyata.

Migrasi hanya dilakukan pada DB pengujian. `0002` menambah data/kolom tanpa
hapus identity lama; downgrade 0002 menghapus data MFA/invite/reset/auth-audit/
outbox dan kolom baru, tetapi identity tahap 1 tetap ada. Downgrade base
menghapus seluruh identity. Role grup tidak dihapus. Rollback real memerlukan
backup/restore dan keputusan manusia; kode lama tanpa MFA bukan rollback aman
admin produksi. Perbaikan dependency policy pada downgrade 0001 tetap ada.

## Riwayat — validasi PostgreSQL tahap 1

**Bagian ini menggantikan status BLOCKED dan klaim belum diuji pada catatan
historis di bawah.** Validasi runtime tahap 1 PASS; LMS-01 keseluruhan tetap
parsial dan memerlukan review independen Claude serta pekerjaan auth tersisa.
Patch historis tidak di-apply ulang. Data dan perubahan pengguna dipertahankan.

Kebijakan sesi ini mengizinkan `require_escalated` untuk perintah spesifik.
Pip dalam sandbox gagal menemukan distribusi dan Docker ditolak pada socket;
setelah permintaan eskalasi, keduanya dapat diakses. Docker server 28.2.2,
Desktop 4.42.1. Instalasi pip pertama mengalami timeout unduhan cmake;
percobaan dengan timeout 120 detik berhasil, TLS tetap aktif.

Lingkungan: Python 3.13.5, pytest 8.4.2, PostgreSQL 16.15. Container baru
`maaher-lms01-validation-20261109`, tanpa mount data pengguna, image
`postgres:16` digest
`sha256:f9a7b9ebf6f56201f949db745e47bc423c0f0f8294bafe991cc10bf74b029657`.
Port pengujian `127.0.0.1:50312`. Autentikasi trust hanya untuk cluster
disposable berisi data sintetis ini. Container sudah **dihentikan**, tidak
dihapus; kedua database tetap tersimpan. Tidak ada database/layanan lama yang
dimigrasi, dihentikan, dihapus, atau di-reset.

Kegagalan nyata yang diperbaiki:

- Run pertama: `3 passed, 3 warnings, 9 errors in 16.57s`. Upgrade berhasil,
  tetapi downgrade gagal `DependentObjectsStillExist`: policy `member_tenants`
  pada `tenants` bergantung pada `memberships`. Sembilan error berasal dari
  fixture migrasi yang sama, bukan sembilan kegagalan assertion API.
- `apps/api/migrations/versions/0001_identity.py`: hapus policy tersebut
  secara eksplisit sebelum menghapus tabel; tidak memakai `CASCADE`.
- `apps/api/tests/test_identity_postgres.py`: assertion keenam tabel tidak
  ada setelah downgrade dan revisi kembali `0001_identity` setelah upgrade.
- Run ulang memakai database kosong baru `maaher_test_lms01_fixed`;
  database run pertama `maaher_test_lms01` tetap dipertahankan.

Perintah utama yang benar-benar dijalankan dari root workspace:

```sh
.venv/bin/python -m pip install --disable-pip-version-check --timeout 120 --retries 2 -r apps/api/requirements-dev.txt
docker run --detach --name maaher-lms01-validation-20261109 --label maaher.purpose=lms01-validation -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=maaher_test_lms01 -p 127.0.0.1::5432 postgres:16
docker exec maaher-lms01-validation-20261109 psql -U postgres -d maaher_test_lms01 -v ON_ERROR_STOP=1 -c 'CREATE ROLE maaher_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS; REVOKE CREATE ON SCHEMA public FROM PUBLIC; CREATE ROLE maaher_api LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS IN ROLE maaher_runtime;' -c 'SELECT version();'
docker exec maaher-lms01-validation-20261109 createdb -U postgres maaher_test_lms01_fixed
env TEST_MIGRATION_DATABASE_URL=postgresql://postgres@127.0.0.1:50312/maaher_test_lms01_fixed TEST_DATABASE_URL=postgresql://maaher_api@127.0.0.1:50312/maaher_test_lms01_fixed PYTHONPATH=apps/api .venv/bin/python -m pytest -v -ra --tb=short apps/api/tests
.venv/bin/python -m pip check
.venv/bin/python -m compileall -q apps/api/app apps/api/migrations apps/api/tests
.venv/bin/python scripts/verify-starter.py
docker stop maaher-lms01-validation-20261109
```

Hasil final: **`12 passed, 4 warnings in 9.39s`**, tanpa SKIP. Terdiri dari
1 health, 2 unit, 9 integrasi PostgreSQL. Upgrade → downgrade → upgrade PASS,
termasuk assertion penghapusan tabel. Cookie/Origin, logout, expiry, throttle,
revocation, disabled user/tenant, role berubah pada session aktif, penolakan
owner, FORCE RLS dan role runtime, read/write lintas tenant, audit immutable,
objek audit asing berdasarkan ID, konteks transaksi tidak bocor, dan session/
audit setelah dua proses API restart semuanya PASS. Tes restart memakai
proses aplikasi sintetis, bukan eksekusi kode siswa.

`pip check`: `No broken requirements found` (warning cache sandbox tidak
writable). Compileall dan verify-starter PASS setelah perbaikan. Empat warning
pytest: satu deprecation alias BlockingPortal dari Starlette/AnyIO dan tiga
warning Alembic `path_separator`; tidak memblokir tes. Lock transitif dan audit
dependensi belum selesai; pip check bukan pemeriksaan kerentanan.

Inspeksi setelah suite: revisi `0001_identity`, 18 users sintetis, 18 tenants
sintetis, 4 audit_events pada database fixed. Untuk inspeksi manual:

```sh
docker start maaher-lms01-validation-20261109
docker exec maaher-lms01-validation-20261109 psql -U postgres -d maaher_test_lms01_fixed -c 'SELECT version_num FROM alembic_version;'
docker stop maaher-lms01-validation-20261109
```

Harapkan `0001_identity`. Jangan menjalankan ulang suite pada database ini:
fixture mensyaratkan kosong; buat database `maaher_test_*` baru dan gunakan
port aktual dari `docker port maaher-lms01-validation-20261109 5432`.
Rollback menghapus tabel identity/session/audit dan seluruh isinya; roundtrip
hanya dilakukan sebelum fixture data pada database disposable. Tidak ada
rollback terhadap data pengguna. Role tetap ada setelah downgrade.

Berkas berubah sesi ini: migration `0001_identity.py`,
`test_identity_postgres.py`, dan handoff ini; `.venv` terisi dependensi.
Tidak ada perbaikan runtime API lain yang diperlukan oleh hasil suite ini.
Artefak `reviews/LMS-01-author.patch` tetap historis dan belum diperbarui;
Claude harus membaca berkas workspace terbaru, termasuk perbaikan rollback.
Tidak ada commit, merge atau deploy. PASS suite tahap 1 bukan persetujuan
release: invite, reset password/email, MFA admin, UI/BFF, audit lifecycle auth,
retensi, lock/audit dependensi dan review independen tetap terbuka.

## Riwayat — lanjutan validasi runtime 2026-11-09 20:01 WIB

**Status saat itu: BLOCKED oleh akses lingkungan. Validasi runtime belum selesai.**
Perubahan lama tetap dipertahankan; patch tidak di-apply ulang. Root masih bukan
repository Git; `maaher-lms/.git` tetap tanpa commit. Tidak ada database pengguna
yang dipakai, dihapus, atau dimigrasi. Tidak ada container pengujian dibuat
karena koneksi daemon belum diizinkan.

Diagnosis aktual pada sesi lanjutan:

| Pemeriksaan/perintah | Hasil nyata | Kesimpulan terbatas |
|---|---|---|
| `socket.getaddrinfo` untuk pypi.org, files.pythonhosted.org, github.com | Ketiganya gagal `gaierror [Errno 8]` | Resolusi DNS tidak tersedia bagi proses sesi ini; kondisi resolver host di luar sandbox belum diketahui |
| `curl --head --connect-timeout 5 --max-time 10 https://pypi.org/simple/pip/` | Exit 6, `Could not resolve host` | Gagal sebelum TLS; bukan bukti sertifikat TLS bermasalah |
| `.venv/bin/python -m pip config debug` | Tidak ada pip.conf global/user/venv yang ditemukan | Tidak ditemukan konfigurasi pip lokal yang menjelaskan DNS gagal |
| Pemeriksaan nama variabel proxy/pip/TLS | HTTP_PROXY, HTTPS_PROXY, ALL_PROXY, PIP_INDEX_URL, PIP_EXTRA_INDEX_URL, PIP_TRUSTED_HOST, SSL_CERT_FILE, REQUESTS_CA_BUNDLE unset | Tidak ditemukan override tersebut; tidak mencetak credential |
| `.venv/bin/python -m pip install --disable-pip-version-check --no-cache-dir --retries 0 --timeout 5 -r apps/api/requirements-dev.txt` | Exit 1, `No matching distribution found for fastapi==0.115.12` | Dependensi belum terpasang; dengan DNS gagal, pesan ini tidak membuktikan versi paket tidak ada |
| `docker context show` dan `docker version` | Context desktop-linux; client 28.2.2; server gagal `connect: operation not permitted` | Akses socket ditolak; daemon host sehat/mati belum bisa dipastikan |
| `stat` socket dan UID proses | UID proses 501, owner socket 501, mode 0755; socket ada; Docker.app ada | Penolakan konsisten dengan sandbox, bukan alasan membuka permission socket |
| Koneksi AF_UNIX langsung ke socket Docker | `PermissionError(1, 'Operation not permitted')` | Penolakan terjadi sebelum protokol Docker |
| `initdb -D /private/tmp/maaher-lms-validation.2NHAfa -A trust --no-locale -E UTF8` (PostgreSQL lokal 14, probe saja) | Exit 1 pada `shmget(key=10469184,size=56,03600): Operation not permitted` | Bootstrap PostgreSQL lokal juga diblokir; bukan validasi PostgreSQL 16 |
| `ipcs -m` | `sysctlbyname: Operation not permitted` | Inventaris shared memory host tidak dapat diperiksa dari sesi ini |

TLS tetap aktif; tidak menggunakan `--trusted-host`, HTTP index, atau
penonaktifan verifikasi sertifikat. Permission Docker socket tidak diubah.
Probe SysV tambahan dengan IPC_PRIVATE melaporkan pembuatan berhasil, tetapi
`shmctl` untuk penghapusan mengembalikan -1; ID tidak tercatat. Karena inventaris
IPC juga dibatasi, kemungkinan segmen probe satu byte yang tersisa tidak dapat
diverifikasi/dibersihkan di sesi ini. Jangan menghapus segmen IPC pengguna lain.
`initdb` membersihkan isinya sendiri setelah gagal; direktori sementara kosong
dapat tersisa. Tidak ada layanan PostgreSQL yang berhasil dimulai.

Kebijakan sesi saat ini menetapkan `sandbox_approval=false`; permintaan
`require_escalated` tidak tersedia sebagai jalur izin yang diperbolehkan.
Karena itu tidak ada perintah di luar sandbox yang dijalankan atau prompt izin
eskalasi yang berhasil diajukan. Ini batas kebijakan sesi, bukan penolakan pemilik.
Untuk melanjutkan diperlukan sesi yang mengizinkan HTTPS PyPI dan akses Docker
Desktop lokal, atau menjalankan validasi dari Terminal host dengan hak akun
pemilik socket. Perintah diagnosis spesifik: `docker version` dan
`curl --head https://pypi.org/simple/pip/`; setelah keduanya berhasil lanjutkan
pip dan database disposable PostgreSQL 16 seperti panduan di bawah.

Perubahan pada lanjutan ini hanya `apps/api/tests/test_identity_postgres.py`
dan handoff ini. Empat tes tambahan, **belum dijalankan**:

- Semua route privat menolak pengguna tanpa autentikasi, termasuk mutation
  dengan Origin yang valid.
- Role aplikasi diperiksa langsung: bukan superuser/BYPASSRLS/pemilik tabel;
  tenants, memberships, audit_events memiliki ENABLE dan FORCE RLS.
- Objek audit tenant lain benar-benar dibuat sebelum pengujian query ID
  langsung; teacher/student ditolak membaca audit, perubahan role admin dan
  penurunan role berlaku pada session yang sama.
- Dua proses Uvicorn terpisah dimulai dan dihentikan oleh tes. Session dan
  audit yang dibuat sebelum restart harus terbaca melalui API setelah restart;
  logout setelah restart harus membuat session lama ditolak. Ini tes aplikasi
  server, tidak mengeksekusi kode siswa. Cookie Secure dikirim eksplisit melalui
  transport loopback pengujian; tes ini tidak mengklaim kebijakan browser HTTP.

Perintah verifikasi yang benar-benar diulang:

```sh
PYTHONPATH=apps/api .venv/bin/python -m unittest discover -s apps/api/tests -p test_security_unit.py -v
.venv/bin/python -m compileall -q apps/api/app apps/api/migrations apps/api/tests
.venv/bin/python scripts/verify-starter.py
.venv/bin/python -m pytest -q apps/api/tests
```

Hasil: **2 unit test PASS**, compileall PASS, verifikasi starter PASS.
Pytest gagal sebelum collection: `No module named pytest`.
Inventaris AST menemukan 12 fungsi tes: 2 unit, 1 health, 9 integrasi.
Angka 12 bukan hasil collection pytest atau jumlah tes lulus. Health dan
9 integrasi belum dijalankan; migrasi upgrade/downgrade/upgrade dan persistensi
setelah restart belum terverifikasi. Tidak ada hasil runtime yang boleh
dinyatakan PASS dari pemeriksaan sintaks ini.

`reviews/LMS-01-author.patch` tetap artefak historis tahap sebelumnya dan belum
memuat empat tes tambahan/perubahan handoff ini. Jangan apply patch tersebut
ke workspace aktif. Review harus membaca berkas workspace terbaru. Belum ada
perbaikan kode runtime berdasarkan hasil integrasi karena integrasi belum bisa
dijalankan; tidak ada migrasi atau rollback yang perlu dilakukan pada sesi ini.

## Pemeriksaan lokal dan GitHub

- Root workspace tidak memiliki `.git`. Folder `maaher-lms/.git` adalah repo
  kosong dengan remote yang benar, belum ada commit maupun origin/main lokal.
  Metadata tersebut tidak dipindah atau di-reset.
- GitHub `main` pada pemeriksaan: `8941a79dcf611df66c4ee43e78b902b62ddbfce2`.
  Semua source berada di bawah `maaher-lms-starter/`. Jangan menyalin workspace
  sebagai satu folder tambahan ke dalam folder tersebut.
- File tersembunyi lokal meliputi `.agents`, `.claude`, `.github`, `.gitignore`,
  `.env.example`, `.DS_Store`; tidak ditemukan `.env` aktif di root.
  Tree GitHub yang diperiksa tidak berisi folder tersembunyi tersebut.
- Fetch CLI gagal: DNS `github.com` tidak tersedia di sandbox. Inspeksi remote
  berhasil melalui konektor GitHub, hanya baca.
- Node `v24.13.0`, npm `11.6.2`, Python `3.13.5`, Docker client `28.2.2`
  darwin/amd64. Docker socket ditolak sandbox (`operation not permitted`).
  Ini tidak membuktikan daemon Docker mati.
- `docker compose ps` juga menunjukkan variabel POSTGRES belum diatur.
- PostgreSQL lokal 14 tersedia, tetapi `initdb` disposable di `/private/tmp`
  gagal membuat shared memory karena sandbox. Tidak menyentuh database lama.

## File dan perilaku

- `apps/api/app/security.py`: opaque token dan matriks peran.
- `apps/api/app/database.py`: transaksi per request, konteks lokal, penolakan
  runtime role superuser/BYPASSRLS/pemilik tabel.
- `apps/api/app/auth.py`: login/logout, membership sendiri, tenant tervalidasi,
  audit pemilihan tenant dan pembacaan audit oleh admin tenant.
- `apps/api/app/main.py`: router auth dan respons no-store.
- `apps/api/app/provision.py`: pembuatan akun/tenant sintetis melalui terminal.
- `apps/api/alembic.ini`, `migrations/env.py`, `migrations/identity.sql`,
  `migrations/versions/0001_identity.py`: schema, grant minimum dan FORCE RLS.
- `apps/api/requirements*.txt`: pin dependensi langsung. Lock transitif belum
  bisa dibuat/divalidasi karena jaringan paket tidak tersedia.
- `apps/api/tests/test_security_unit.py`, `test_identity_postgres.py`: unit
  dan integrasi PostgreSQL nyata; `apps/api/pytest.ini` mengatur import API.
- `infra/development-roles.sql`, `docs/tickets/LMS-01.md`, dokumen ini,
  `docs/REA-SETUP-CODEX.md`, pembaruan register REA, dan patch review.

Membership sendiri dapat dibaca lintas tenant yang diikuti untuk pemilihan
organisasi. Audit membutuhkan konteks tenant dan membership aktif. Header
`X-Tenant-ID` hanya selector; server memvalidasi session, user, tenant dan
membership sebelum menggunakannya. Sesi tidak menyimpan role lama.
Kata sandi memakai pwdlib/Argon2; token acak 256 bit disimpan sebagai SHA-256,
berlaku delapan jam dan dihapus saat logout. Mutation membutuhkan Origin persis
`APP_ORIGIN`. Cookie Secure/HttpOnly/SameSite=Lax; pengecualian HTTP hanya bila
`APP_ENV=local` dan `LOCAL_INSECURE_COOKIES=true` diatur eksplisit.
Rate limit login per hash email: 10 percobaan dalam 15 menit, diserialisasi
dengan lock baris PostgreSQL. Gate jaringan/rate limit global masih diperlukan
sebelum exposure publik. Tidak ada eksekusi kode siswa.

## Verifikasi yang benar-benar dijalankan

```sh
PYTHONPATH=apps/api .venv/bin/python -m unittest discover -s apps/api/tests -p test_security_unit.py -v
.venv/bin/python -m compileall -q apps/api/app apps/api/migrations apps/api/tests
.venv/bin/python scripts/verify-starter.py
```

Hasil: 2 unit test PASS; compileall PASS; verifikasi starter PASS.
Integritas baseline: 25/25 blob cocok dengan SHA GitHub. Patch lolos
`git apply --check -p2` terhadap baseline lokal di `/private/tmp`.
Instalasi pip gagal resolusi DNS; percobaan `.venv/bin/python -m pytest -q
apps/api/tests` gagal `No module named pytest`. API/integrasi PostgreSQL dan roundtrip
migrasi BELUM dijalankan. Unit test tidak membuktikan RLS atau session API aman.
Percobaan `initdb` gagal dengan `shmget: Operation not permitted`.

## Menjalankan integrasi setelah akses lokal tersedia

Gunakan database kosong disposable bernama `maaher_test_*` di PostgreSQL 16.
Jalankan SQL role pengembangan sekali, lalu buat LOGIN role `maaher_api` yang
mewarisi `maaher_runtime` (tanpa superuser/BYPASSRLS/hak owner). Password dimasukkan
melalui prompt terminal, jangan dalam chat atau commit. URL owner test harus
memiliki hak DDL dan bypass RLS untuk fixture; runtime URL memakai role API.
Pastikan kedua URL menunjuk database test yang sama.

```sh
.venv/bin/python -m pip install -r apps/api/requirements-dev.txt
# Atur TEST_MIGRATION_DATABASE_URL dan TEST_DATABASE_URL melalui terminal lokal.
PYTHONPATH=apps/api .venv/bin/python -m pytest -q apps/api/tests
```

Suite menguji upgrade → downgrade → upgrade sebelum seed, cookie, Origin,
akses tenant palsu, peran, throttling, logout, expiry, membership dicabut,
user/tenant dinonaktifkan, RLS langsung, write lintas tenant, audit immutable,
dan penolakan role owner. Tanpa kedua URL suite integrasi SKIP. Setiap rerun
memerlukan database test kosong baru; database terakhir ditinggal untuk inspeksi.

## Migrasi dan rollback pengembangan

Jangan jalankan Compose starter dengan credential owner sebagai runtime auth.
Compose belum mengatur pemisahan credential ini dan UI belum terhubung.
Pada database dev baru, provision role terlebih dahulu, lalu:

```sh
# MIGRATION_DATABASE_URL: credential migrasi, bukan credential runtime API.
.venv/bin/alembic -c apps/api/alembic.ini upgrade head
# DATABASE_URL: credential runtime API; APP_ORIGIN: origin browser yang tepat.
PYTHONPATH=apps/api .venv/bin/python -m app.provision
PYTHONPATH=apps/api .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Provisioning hanya untuk APP_ENV=local dan membutuhkan koneksi administratif
dev dengan BYPASSRLS/superuser melalui MIGRATION_DATABASE_URL, karena FORCE RLS
tetap berlaku pada owner biasa. Jangan berikan credential tersebut ke API.
Rollback `alembic -c apps/api/alembic.ini downgrade base` menghapus seluruh tabel
identity/session/audit beserta datanya: hanya lakukan pada DB disposable atau
setelah backup dan keputusan manusia. Role database tidak dihapus oleh rollback.
Migrasi ini belum diterapkan pada database apa pun dalam sesi ini.

## Sisa pekerjaan dan review

LMS-01 belum lengkap: invite, reset password/email, MFA admin, audit lifecycle
auth lengkap, UI/BFF, retensi session/login-attempt, dependency lock/audit dan
validasi integrasi. Course, materi, enrollment, tugas, grading dan progress
tetap backlog berikutnya. Belum ada klaim aplikasi end-to-end berfungsi.

Claude Code harus melakukan review independen sesuai AGENTS.md. Patch lokal
`reviews/LMS-01-author.patch` disiapkan terhadap snapshot GitHub di atas;
review juga file tersembunyi lokal yang tidak ada pada remote. Setelah jaringan
tersedia, clone ke folder baru, cek baseline SHA, bawa perubahan ke path
`maaher-lms-starter/` pada branch `feat/LMS-01-auth-foundation`, lalu review
diff yang benar. Jangan merge atau deploy otomatis.
