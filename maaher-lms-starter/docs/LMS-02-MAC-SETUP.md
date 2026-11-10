# Menjalankan manajemen kursus di Mac

**Status terbaru:** UAT utama f38c231 berhasil menurut pemilik; review Claude
kemudian melaporkan tujuh LOW tanpa BLOCKER/HIGH/MEDIUM. Delta perbaikannya
menambah **0007_course_review**. Simpan data UAT, backup lalu upgrade maju;
tidak perlu setup ulang Auth0. UAT delta dan re-review masih pending. Lihat
[respons author](../reviews/LMS-02-author-response.md) dan
[hasil UAT sebelumnya](LMS-02-DEV-UAT-20261110.md).

Branch: `feat/LMS-02-course-management`. Root aplikasi pada repository GitHub
adalah `maaher-lms-starter/`. Branch bertumpu pada source Auth0 yang sama dengan
UAT sebelumnya. Tidak perlu membuat ulang tenant/user/Action/binding Auth0.

1. Periksa status source lokal dan ambil branch ke checkout/worktree baru bila
   ada perubahan yang bertabrakan atau folder lama bukan repo Git. Pertahankan
   folder lama `/Users/mashudi/Downloads/AiMZ-Corp Project/maaher-lms-starter`.
   Tidak reset/overwrite/stash otomatis. Gunakan parser dotenv untuk konfigurasi
   LMS lokal tanpa mencetak atau mengeksekusi secret; jangan commit `.env`.
2. Pertahankan profile dev-totp, domain/client ID, binding, keyring dan credential
   yang sudah berhasil. Periksa API `/api/auth/oidc/config` tetap enabled=true dan
   assurance=maaher-dev-totp-v1. Sesudah diagnosis login selesai, set
   AUTH0_LOCAL_DIAGNOSTICS=false pada development dan restart API.
3. Backup DB Auth0 development yang sudah dipastikan sintetis maaher_test_*.
   Periksa migration/auth/runtime menuju DB yang benar dan role terpisah.
   Dengan credential migrasi, upgrade dari **0006_courses ke 0007_course_review**
   (`python -m alembic -c apps/api/alembic.ini upgrade head` dari root aplikasi,
   konfigurasi credential migrasi tetap lokal). Checkout baru dari 0005 melewati
   0006 lalu 0007 pada perintah yang sama.
   Jangan menargetkan DB pengguna, DB tes lama, atau mengubah role menjadi owner.
   Tidak perlu downgrade/reset. Upgrade ini tidak mengubah akun/binding auth.
4. Install dependency sesuai lockfile, termasuk `npm ci` pada apps/web. Rebuild/
   restart hanya layanan API/web development sesuai workflow yang sudah digunakan;
   pertahankan volume dan database. Jangan memakai service lama dengan schema
   baru atau web lama tanpa route /api/courses. Checker Auth0 kini mengenali
   schema 0005, 0006 maupun 0007. Lock Python kini mencakup parser Markdown server;
   rebuild API diperlukan, selain web. Jangan hanya memperbarui frontend.
5. Login Auth0 → pilih organisasi yang sah → **Kelola kursus**, atau buka
   `http://127.0.0.1:3000/courses`. Halaman memuat membership session, tidak
   menggunakan role/tenant dari query sebagai authority.

## UAT yang perlu dilakukan

- Regresi baru: pada kursus Terbit, tugaskan/cabut guru; status harus tetap
  Terbit. Dengan guru sintetis yang sudah diotorisasi, role teacher→student→
  teacher tidak mengembalikan kursus lama; admin harus menugaskan ulang.
- Guru tidak melihat/membaca kursus arsip. Admin tetap dapat memulihkannya.
  Assignment yang valid tetap ada saat archive/restore; perubahan role/status
  membership atau user mencabut assignment secara permanen.
- Tautan aktif Markdown HTTP/relative/tersembunyi harus ditolak saat simpan;
  contoh URL di inline/blok kode tetap dapat disimpan. Data legacy dipertahankan
  saat upgrade; perbaiki link yang ditolak sebelum simpan/publish. Tidak ada
  publikasi ulang otomatis untuk draft yang dibuat perilaku lama.
- Limit mutation adalah 60/menit per admin/guru per tenant. 429 meminta menunggu
  dan mempertahankan editor. Tidak perlu membanjiri DB UAT untuk mengujinya;
  bukti concurrency dan 429 tersedia pada tes DB/browser sintetis terpisah.
- Dengan admin tenant yang sudah ada: buat kursus, tambah modul/pelajaran,
  simpan Markdown + link HTTPS, reload dan pastikan data tetap ada.
- Kursus kosong tidak dapat diterbitkan. Isi seluruh modul/pelajaran lalu
  terbitkan; edit materi harus kembali draft. Ubah urutan, tarik publikasi,
  arsip/pulihkan, dan pastikan materi tetap ada setelah pemulihan.
- Assignment guru memakai anggota tenant dengan role teacher yang aktif. Admin
  dapat memuat daftar anggota/pagination dan assign/revoke; guru hanya melihat
  kursus tugasnya. Teacher memakai alur identitas yang memang sudah disiapkan
  untuknya; jangan menambahkan is_operator atau auto-link email untuk login.
- Akun operator tanpa membership admin tenant tidak mendapat hak membuat kursus.
  Bila role bukan admin/teacher, jangan promosi otomatis berdasar email/Auth0
  metadata; periksa provisioning sintetis dan membership yang telah diotorisasi.
- Konflik dua tab mendapat pesan muat ulang, tidak menimpa perubahan. Simpan
  perubahan sebelum berpindah kursus/organisasi. Hapus modul/pelajaran adalah
  permanen dan memerlukan konfirmasi; gunakan data uji.
- Logout mencabut session; request kursus setelah logout ditolak. Jangan
  membagikan password/OTP, raw token, cookie, callback URL atau `.env`.

Ini pengelolaan materi. Enrollment/cohort LMS-03 dan tampilan belajar siswa
LMS-04 belum tersedia; status Terbit tidak membuka katalog anonim. Asset berupa
tautan HTTPS, belum upload file/video. Eksekusi kode learner tetap dinonaktifkan.

0007 membersihkan assignment yang **saat upgrade** tidak valid. Schema lama
tidak merekam kapan penugasan dibuat; bila pernah terjadi siklus role sebelum
upgrade, tinjau assignment guru saat ini dan cabut yang tidak lagi disetujui.
Jangan menganggap migrasi dapat menyimpulkan riwayat tersebut. Downgrade bukan
langkah UAT: 0007→0006 menghilangkan guard baru tanpa mengembalikan assignment;
0006→0005 menghapus materi dan kini menuntut ack eksplisit bila course berisi.

## Prompt Codex CLI

```text
Lanjutkan perbaikan review/UAT LMS-02 dari branch feat/LMS-02-course-management di
mashudizaini/maaher-lms. Root aplikasi GitHub: maaher-lms-starter/.
Baca AGENTS.md, docs/LMS-02-MAC-SETUP.md dan reviews/LMS-02-author-response.md.
Periksa Git status; ambil source
ke checkout/worktree baru jika perlu tanpa menimpa perubahan lokal saya.
Pertahankan konfigurasi Auth0 dev-TOTP, binding, .env, keyring dan seluruh DB
lama yang sudah berhasil. Jangan mencetak nilai secret atau membuat ulang IdP.
Pastikan flag diagnosis lokal sudah false. Backup lalu upgrade hanya DB Auth0
development yang sudah terbukti sintetis dari 0006 ke 0007_course_review memakai
credential migrasi terpisah; jangan reset/downgrade/migrasi database lain.
Install lockfile dan rebuild/restart API/web development sesuai workflow lokal.
Jalankan checker Auth0 dan buka /courses. Saya menyelesaikan login Auth0 sendiri.
Verifikasi admin tenant existing; uji assign/cabut pada course Terbit tetap
Terbit, siklus role tidak mengembalikan assignment, guru tidak membaca arsip,
validasi link Markdown, serta create→save→reload→publish→edit draft→restore→logout.
Jangan menyimpulkan UAT baru lulus dari catatan f38c231; catat hasil aktual.
Catat hasil nyata, code/schema SHA dan FAIL/SKIP, serta bukti tanpa PII/secret.
Jangan menambah role dari email atau menonaktifkan MFA/RLS. Jangan merge/deploy.
```

Review read-only Claude atas auth terbaru dan delta LMS-02 tetap diperlukan.
Panduan bukti/perintah/rollback ada pada LMS-02-HANDOFF.md.
