# Menjalankan manajemen kursus di Mac

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
   Dengan credential migrasi, upgrade dari **0005_dev_totp ke 0006_courses**.
   Jangan menargetkan DB pengguna, DB tes lama, atau mengubah role menjadi owner.
   Tidak perlu downgrade/reset. Upgrade ini tidak mengubah akun/binding auth.
4. Install dependency sesuai lockfile, termasuk `npm ci` pada apps/web. Rebuild/
   restart hanya layanan API/web development sesuai workflow yang sudah digunakan;
   pertahankan volume dan database. Jangan memakai service lama dengan schema
   baru atau web lama tanpa route /api/courses. Checker Auth0 kini mengenali
   schema 0005 maupun 0006.
5. Login Auth0 → pilih organisasi yang sah → **Kelola kursus**, atau buka
   `http://127.0.0.1:3000/courses`. Halaman memuat membership session, tidak
   menggunakan role/tenant dari query sebagai authority.

## UAT yang perlu dilakukan

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

## Prompt Codex CLI

```text
Lanjutkan UAT LMS-02 dari branch feat/LMS-02-course-management di
mashudizaini/maaher-lms. Root aplikasi GitHub: maaher-lms-starter/.
Baca AGENTS.md dan docs/LMS-02-MAC-SETUP.md. Periksa Git status; ambil source
ke checkout/worktree baru jika perlu tanpa menimpa perubahan lokal saya.
Pertahankan konfigurasi Auth0 dev-TOTP, binding, .env, keyring dan seluruh DB
lama yang sudah berhasil. Jangan mencetak nilai secret atau membuat ulang IdP.
Pastikan flag diagnosis lokal sudah false. Backup lalu upgrade hanya DB Auth0
development yang sudah terbukti sintetis dari 0005 ke 0006_courses memakai
credential migrasi terpisah; jangan reset/downgrade/migrasi database lain.
Install lockfile dan rebuild/restart API/web development sesuai workflow lokal.
Jalankan checker Auth0 dan buka /courses. Saya menyelesaikan login Auth0 sendiri.
Verifikasi admin tenant existing, lalu uji create course→module→lesson→save→
reload→publish→edit kembali draft→archive/restore→logout pada data sintetis.
Catat hasil nyata, code/schema SHA dan FAIL/SKIP, serta bukti tanpa PII/secret.
Jangan menambah role dari email atau menonaktifkan MFA/RLS. Jangan merge/deploy.
```

Review read-only Claude atas auth terbaru dan delta LMS-02 tetap diperlukan.
Panduan bukti/perintah/rollback ada pada LMS-02-HANDOFF.md.
