# LMS-03 — setup dan UAT development Mac

**Status 11 November:** validasi CLI Mac pada 110c9be/0008 kini dilaporkan lulus
dengan dua sesi dan provider sintetis; [hasil dan batas](LMS-03-DEV-UAT-20261111.md).
Panduan setup di bawah tetap untuk checkout baru. Lingkungan yang sudah aktif
tidak perlu migrasi atau setup Auth0 ulang untuk langkah berikutnya, yaitu
[review independen Claude](../reviews/LMS-03-review-request.md). Pertahankan
catatan lokal reviews/LMS-03-mac-validation-20261111.md untuk reviewer.

Branch `feat/LMS-03-enrollment`, base fe54142. Root GitHub memuat subfolder
maaher-lms-starter/. Workspace lama bisa berbeda; periksa Git status dan root.
Folder LMS Mac yang diberikan pemilik:
`/Users/mashudi/Downloads/AiMZ-Corp Project/maaher-lms-starter`.
Catatan terakhir memakai checkout maaher-lms-auth0; pilih checkout yang sedang
menjalankan UAT, jangan menebak dari nama folder atau menimpa folder lama.

1. Ambil branch baru pada checkout/worktree terpisah bila ada perubahan yang
   bertabrakan. Pertahankan laporan Claude, catatan Mac dan source lokal yang
   untracked; jangan reset, stash otomatis atau menghapus berkasnya. Snapshot
   fe54142 tetap tersedia pada branch LMS-02.
2. Pertahankan konfigurasi LMS yang sudah berhasil: .env, keyring, credential
   role terpisah, Auth0 dev-TOTP, Action, binding dan volume. Jangan mencetak
   secret/token atau mengubah aplikasi IdP. File .env hanya lokal, tidak di Git.
3. Identifikasi **DB UAT development sintetis** yang benar, backup dengan tool
   lokal dan pastikan backup selesai. Dengan credential migrasi terpisah:
   `python -m alembic -c apps/api/alembic.ini upgrade head` dari root aplikasi,
   menargetkan **0007_course_review→0008_enrollment**. URL/credential dari config
   lokal yang diizinkan; jangan isi di chat/shell history. Tidak perlu downgrade,
   reset DB atau menerapkan patch dua kali.
4. Install lockfile/rebuild/restart API dan web dengan workflow development yang
   sudah dipakai. Tidak ada pin dependency baru dari fe54142. Checker Auth0
   mengenali head 0008; jangan menyimpulkan setting provider penuh terverifikasi
   dari preflight. Login admin existing sendiri, pilih organisasi tes yang benar.
5. Buka /enrollments untuk admin dan /learn untuk siswa. Gunakan dropdown
   organisasi yang benar pada tiap halaman; tenant selector hanya pilihan,
   authorization tetap session/membership/RLS. Course archived dipulihkan dulu
   melalui /courses bila hendak mengelola enrollment baru.

## UAT minimum

- Course berisi materi terbit: buat cohort A/B. Buat siswa **sintetis baru** lewat
  alur undangan existing pada tenant tes. Bila SMTP/inbox belum tersedia, Codex
  dapat memakai jalur fixture lokal yang diizinkan hanya pada DB maaher_test_*,
  tanpa mengubah akun/binding lama atau mempromosikan role admin. Simpan detail
  akun uji di berkas lokal terlindungi, bukan chat/log/commit.
- Muat daftar siswa → pilih siswa aktif/cohort A → daftarkan. Duplikat ditolak.
  Buka jendela/profile browser terpisah untuk login siswa lokal, pilih organisasi
  yang sama lalu **Kursus saya**. Materi course Terbit terbuka; draft tidak muncul.
  Login siswa lokal ini memakai alur existing, bukan melonggarkan MFA staff.
- Pindah cohort A→B, reload dan periksa data bertahan. Revoke → siswa reload/list
  kosong/lesson ditolak. Aktifkan ulang secara eksplisit → akses kembali.
- Archive cohort → enrollment dicabut. Restore cohort → enrollment **tetap
  dicabut** sampai admin reactivate. Archive/restore course punya aturan sama.
  Edit course menjadi draft hanya menjeda akses sampai publish kembali.
- Siswa tidak dapat mengelola roster/kursus atau membaca peer cohort/enrollment.
  Guru yang ditugaskan hanya membaca roster aktif, tanpa mutasi; jika akun guru
  Auth0 nyata belum disiapkan, laporkan NOT TESTED, jangan buat binding otomatis.
- Logout siswa/admin dan pastikan request sesudahnya ditolak. Catat source SHA,
  schema dan FAIL/SKIP/NOT TESTED dengan provenance, tanpa PII atau secret.

Tes API/browser otomatis harus memakai DB **kosong baru** terpisah dari DB UAT.
Jangan jalankan pytest menggunakan DB UAT yang sudah berisi, atau memberi ack
rollback untuk sekadar menjalankan aplikasi. Downgrade 8→7 menghapus seluruh
cohort/enrollment dan menuntut flag data-loss bila berisi; bukan prosedur UAT.

## Prompt Codex CLI

```text
Lanjutkan setup/UAT LMS-03 dari branch feat/LMS-03-enrollment di
mashudizaini/maaher-lms. Baca AGENTS.md, docs/LMS-03-HANDOFF.md dan
LMS-03-MAC-SETUP.md. Periksa checkout aktif dan Git status; ambil source tanpa
menimpa perubahan lokal, laporan Claude atau catatan validasi saya.
Pertahankan .env, keyring, binding, Auth0 dan seluruh DB/container lama.
Backup hanya DB development yang telah dipastikan sintetis, upgrade 0007→0008
menggunakan role migrasi terpisah, lalu rebuild/restart API/web development.
Jangan reset/downgrade DB; suite otomatis hanya pada DB kosong baru sendiri.
Jangan mencetak secret/token/kredensial. Saya menyelesaikan login admin sendiri.
Siapkan siswa sintetis baru pada tenant tes melalui alur existing yang diizinkan;
simpan detail login lokal terlindungi. Uji cohort→enroll→student read→move→
revoke→reactivate→archive/restore tetap revoked→logout dengan dua sesi browser.
Catat hasil aktual dan hal yang tidak diuji. Jangan auto-link email, mengubah
MFA/Auth0, merge atau deploy. Simpan reviews/LMS-03-mac-validation-20261111.md.
```
