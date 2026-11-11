# LMS-04 — menjalankan completion dan perbaikan performa di Mac

Branch feat/LMS-04-student-learning, base4870287; root aplikasi GitHub
maaher-lms-starter/. Checkout Mac terakhir dapat bernama maaher-lms-auth0;
periksa Git root/status dan runtime aktif, jangan menebak atau menimpa folder.

1. Ambil branch baru dengan checkout/worktree terpisah jika perubahan lokal
   bertabrakan. Pertahankan semua laporan Claude/catatan Mac yang untracked.
   Tidak reset, stash otomatis atau menerapkan patch berulang.
2. Pertahankan .env, keyring, DB role terpisah, Auth0/dev-TOTP, Action/binding dan
   volume yang sudah berhasil. Tidak ada secret/variable/dependency baru.
   Parser memakai proses Python library terpercaya, bukan runner learner.
3. Identifikasi dan backup **DB development sintetis** existing head0008.
   Credential migrasi/DBA yang sudah terpisah perlu membuat/own role baru
   maaher_access_reader NOLOGIN/NOBYPASS/NOINHERIT, tanpa grant membership ke
   runtime/auth atau role lain. Migration menolak konfigurasi role tidak aman.
   Jangan memberi API CREATEROLE/superuser untuk meloloskan upgrade.
4. Dari root aplikasi, konfigurasi URL migrasi lokal tanpa mencetak secret,
   jalankan `python -m alembic -c apps/api/alembic.ini upgrade head` ke
   **0010_learning_progress**, melewati0009. Data lama dipertahankan, lesson
   revision dimulai1 dan progress kosong. Tidak perlu reset/downgrade.
5. Rebuild/restart API/web development dengan workflow sebelumnya dan lockfile
   existing. Checker mengenali head0009/0010. Buka /learn dengan siswa sintetis
   yang telah di-enroll; login admin existing dilakukan sendiri oleh pemilik.

## UAT

- Course terbit dengan minimal dua lesson: Lanjutkan belajar → Tandai selesai /
  Selesai & lanjutkan → previous/next. Reload kursus dan pastikan count/status
  tersimpan. Tandai belum selesai harus mengurangi count.
- Admin edit **isi/resources** lesson yang sudah selesai, publish. Siswa reload:
  completion lama tidak dihitung, ada notifikasi materi diperbarui, kemudian
  tandai ulang. Title/reorder saja mempertahankan status selesai.
- Revoke/draft/archive menutup read/write. Reaktivasi enrollment eksplisit tetap
  diperlukan sesuai LMS-03; progress revisi yang masih valid boleh muncul lagi
  setelah regrant. Tenant disable tetap pause seperti parent.
- Akun peer/teacher/admin tidak mendapat mutasi progress siswa. Logout dan periksa
  akses ditolak. Catat real Auth0 vs provider sintetis, manual vs otomatis.
- Input Markdown terlalu kompleks dapat ditolak422 dengan pesan menyederhanakan;
  save lain saat parser sibuk mendapat429 Retry-After1 tanpa membuang editor.
  Jangan membanjiri DB UAT untuk benchmark. CPU/memory limit Mac perlu diuji
  lokal; child wall timeout tetap fail-closed. Learning read/write120/min dan
  course writes60/min tetap diberlakukan.

Semua pytest/benchmark harus memakai **DB kosong baru terpisah**. Fixture
melakukan rollback destruktif ber-ack pada DB disposable. F1 benchmark mengubah
policy sementara lalu mengembalikannya; jangan arahkan ke DB UAT/DB lama.
Data completion baru tidak boleh dihapus untuk sekadar menjalankan aplikasi.
Rollback0010 memerlukan backup/operator ack jika progress berisi.

```text
Lanjutkan setup/UAT LMS-04 branch feat/LMS-04-student-learning di
mashudizaini/maaher-lms. Baca AGENTS.md, docs/LMS-04-HANDOFF.md dan
LMS-04-MAC-SETUP.md. Periksa Git status/checkout aktif; ambil source tanpa
menimpa perubahan lokal dan laporan saya. Pertahankan .env/keyring/Auth0/binding,
semua DB dan volume lama. Backup DB development yang dipastikan sintetis head0008,
upgrade maju ke0010 dengan credential migrasi/DBA terpisah, lalu rebuild API/web.
Jangan memberi API privilege owner/CREATEROLE/BYPASSRLS atau mencetak secret.
Jangan reset/downgrade; suite/benchmark hanya di DB kosong baru sendiri.
Gunakan siswa sintetis yang di-enroll dan dua sesi terpisah; saya login admin
sendiri. Uji completion→next/previous→reload→uncomplete, edit materi/publish→
status perlu konfirmasi ulang, serta revoke/reaktivasi/role sesuai akses.
Reproduksi F1/F2 dengan metode benchmark yang aman pada DB disposable bila mampu;
catat hasil aktual, provider, source/schema, FAIL/SKIP/NOT TESTED tanpa token/PII.
Simpan reviews/LMS-04-mac-validation-20261111.md. Jangan ubah MFA, merge/deploy.
```
