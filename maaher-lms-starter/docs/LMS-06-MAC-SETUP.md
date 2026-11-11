# LMS-06 — Mac setup dan UAT penilaian

11 November 2026, Asia/Jakarta. Branch **feat/LMS-06-teacher-grading**, base13408bb,
schema **0013_grading**. Panduan ini belum dijalankan pada Mac pemilik oleh AUTHOR
cloud. [Handoff](LMS-06-HANDOFF.md) menjelaskan tes dan batas bukti cloud.

## Pembaruan lokal

1. Di Codex CLI, pastikan Git root dan app root yang benar. Folder awal pemilik:
   `/Users/mashudi/Downloads/AiMZ-Corp Project/maaher-lms-starter`; checkout kemudian
   mungkin bernama `maaher-lms-auth0/maaher-lms-starter`. Temukan layanan yang aktif
   dari konfigurasi lokal; jangan memakai path govriskid yang sebelumnya keliru.
2. Baca `git status`, HEAD, branch dan schema secara read-only. Fetch branch baru
   secara normal. Jika ada source lokal yang bertabrakan, gunakan worktree baru;
   pertahankan seluruh laporan untracked Claude/Mac, .env, keyring, binding,
   volume dan DB lama. Jangan reset/clean, menerapkan patch lama, atau menimpa
   checkout aktif. Jangan mengganti project Compose/volume tanpa memetakan data.
3. Pertahankan URL DB API/auth/migration yang terpisah, Auth0 dev-TOTP dan keys.
   Tidak ada secret, dependency, role global atau Action Auth0 baru. Nilai secret
   tidak perlu ditampilkan. Pakai workflow pemuatan konfigurasi aman yang sudah
   berfungsi, bukan menyalin nilai konfigurasi ke chat/repo/laporan.
4. Pastikan target benar-benar **DB development berisi data sintetis** pada0012.
   Buat backup dengan workflow lokal yang sudah aman; catat lokasi non-rahasia
   dan keberhasilannya. Pakai credential migrasi pemilik objek, lalu dari app root:

   ```bash
   python -m alembic -c apps/api/alembic.ini current
   python -m alembic -c apps/api/alembic.ini upgrade head
   python -m alembic -c apps/api/alembic.ini current
   ```

   Head harus0013_grading. Upgrade menambah tabel penilaian kosong dan constraint/
   trigger/index, mempertahankan submission/auth/course/enrollment/progress lama.
   Jika head sudah0013, jangan downgrade lalu upgrade ulang. Jika target bukan
   sintetis, siapkan DB development terpisah; jangan memigrasi data nyata otomatis.
   Jangan menjadikan credential API owner/superuser untuk mengatasi error.
5. Rebuild/restart API dan Next dengan workflow lokal yang sudah berjalan.
   Verifier Auth0 kini mengenali0013; jalankan preflight yang sama tanpa mengubah
   assurance/binding. Catat hasil aktual, jangan mengasumsikan13 PASS dari run lama.
   Jalankan parser-preflight dan bila diperlukan `--calibrate` pada hardware target;
   native Mac dapat WARN_MEMORY_UNAVAILABLE. Itu bukan memory cap aktif dan tidak
   boleh disamarkan menjadi PASS. Profil production tetap membutuhkan cap Linux.
6. Buka `/grading` sebagai admin atau teacher yang ditugaskan. Siapkan student
   sintetis enrolled dalam course published, memakai browser profile berbeda.
   Pemilik melakukan login Auth0 sendiri. Jangan menangkap password/OTP/token.

## UAT manual dua peran

- Student membuat jawaban lalu submit di `/work`. Staff membuka `/grading`,
  memilih course dan submission. Pastikan sumber/instruksi/rubrik milik versi
  yang benar; publikasi tugas versi baru tidak mengubah rubrik submission lama.
- Beri skor per kriteria dan feedback, klik **Simpan draf nilai**. Reload staff:
  draf tetap ada. Student reload nilai: belum ada nilai dibagikan. Coba total0
  pada submission uji;0 harus diterima dan ditampilkan setelah dibagikan.
- Klik **Bagikan nilai** dan konfirmasi. Student memuat ulang nilai dan melihat
  skor/komentar/feedback yang benar. Alasan privat dan identitas reviewer tidak
  tampil sebagai bagian payload nilai siswa. Source submission tidak berubah.
- Staff mengubah skor dan mengisi alasan privat, menyimpan koreksi sebagai draf.
  Student masih melihat nilai lama. Bagikan koreksi: student baru melihat nilai
  baru. Tarik nilai dengan alasan: student melihat status ditarik tanpa skor lama.
  History staff mempertahankan revisi dan urutan peristiwa.
- Dua tab staff dengan version lama: satu save/release sukses, yang lain409;
  editor tidak kehilangan isi. Retry setelah reload keputusan manusia, jangan
  menimpa konflik diam-diam.429 juga mempertahankan editor; jangan sengaja
  membanjiri DB UAT untuk menguji batas, gunakan tes otomatis pada DB baru.
- Teacher courseA tidak membaca courseB; teacher yang assignment/membership-nya
  dicabut tidak menilai lagi. Student lain tidak membaca nilai peer. Revoke
  enrollment/unpublish course menutup student grade read. Course archive menutup
  grading write; admin masih dapat membaca history. Restore tidak otomatis enroll.
- Keluar pada kedua sesi. Catat source/schema/provider, langkah yang sungguh
  dilakukan, hasil aktual dan pesan error tersamarkan.

Label tombol dapat diperiksa pada source UI bila berbeda sedikit dari panduan.
Tidak ada perhitungan nilai akhir course/otomatisasi completion atau eksekusi kode.
Teacher harus assigned aktif; akses admin saja tidak membuktikan jalur teacher.

## Tes otomatis dan preservasi

Jalankan pytest/benchmark/browser hanya terhadap **DB kosong baru** berawalan
`maaher_test_`, semua URL role terpisah menunjuk DB uji yang sama. Fixture memuat
rollback ber-ack dan rekonstruksi RLS parent; jangan pernah arahkan ke DB UAT/DB
lama. Pertahankan seluruh DB/container uji lama; pembuatan DB baru tidak butuh
penghapusan DB lain. Jangan menjalankan perintah rm dari laporan Claude lama.

```bash
python -m pytest --collect-only -q apps/api/tests
python -m pytest -q apps/api/tests
python -m pytest -q scripts/tests
node --test infra/auth0/*.test.cjs
python scripts/test-lms01-browser.py --oidc --dev-totp --grading
```

Koleksi final saat author:380 kasus. Perkiraan native Mac379 PASS+1 platform SKIP,
Linux380 PASS; ini **perkiraan, bukan hasil Mac/CI yang sudah terjadi**. Catat hasil
aktual. Jangan menghilangkan modul rollback assignments/enrollment/learning/grading
untuk mengejar angka; rekonsiliasi node ID bila berbeda. Jangan gunakan `--deselect`
untuk menutupi kegagalan. Memory capability saja skipif(non-Linux); valid-content
CPU, kontrol/frame dan timer tetap berjalan. Browser memakai provider sintetis,
bukan bukti login Auth0 nyata. Full cloud run378 PASS lalu4 targeted (2 baru);
penjelasan jumlah di handoff, tidak ada klaim satu run380.

Staff grading GET180/menit; mutasi grading berbagi course60/menit; student grade
GET berbagi work120/menit. Counter expired dapat dibersihkan maintenance role tanpa
akses nilai. Scheduler retensi produksi masih belum disetujui; jangan menjalankan
maintenance test-only pada data nyata atau melonggarkan pembatasannya.

Rollback0013 menghapus penilaian/history dan bukan langkah setup. Guard populated
membutuhkan tepat `-x allow_grading_data_loss=yes`; hanya uji di DB disposable.
Backup tetap diperlukan; upgrade ulang tidak memulihkan nilai yang dihapus.

## Prompt Codex CLI

```text
Lanjutkan validasi Mac LMS-06 dari branch feat/LMS-06-teacher-grading pada repo
mashudizaini/maaher-lms. Baca AGENTS.md, docs/LMS-06-HANDOFF.md,
docs/LMS-06-MAC-SETUP.md dan ADR-011. Periksa Git/app root, source aktif, perubahan
lokal dan schema; fetch source tanpa menimpa source/laporan Claude/Mac saya.
Pertahankan .env/keyring/Auth0 dev-TOTP/binding, seluruh DB/volume/container lama.
Backup DB development yang dipastikan sintetis head0012, upgrade maju ke0013
dengan credential migrasi terpisah, lalu rebuild/restart API/web. Jika sudah0013
jangan ulang downgrade. Jangan cetak secret, ubah MFA/Action, beri privilege API,
reset/clean/downgrade, hapus container lama, merge atau deploy.
Jalankan preflight Auth0 dan parser, catat PASS/WARN aktual; cap memori native Mac
tidak tersedia bukan berarti cap aktif. Seluruh pytest/benchmark/browser harus
memakai DB kosong baru sendiri, termasuk semua modul rollback. Koleksi author380;
laporkan node ID/count aktual dan platform SKIP tanpa deselect kegagalan.
Uji grading teacher assigned dan student dalam dua sesi: submission versi asli,
draf privat/reload, nilai0, release, koreksi draf tetap tersembunyi sampai release,
withdraw dengan alasan/history, stale409/429 editor, peer/tenant/revoke/archive,
source immutable dan logout. Provider sintetis bukan UAT Auth0; saya login nyata
sendiri bila dibutuhkan. Simpan laporan BARU reviews/LMS-06-mac-validation-20261111.md
dengan command, source/schema, provider, counts, FAIL/SKIP/NOT TESTED yang nyata.
Pertahankan semua bukti/data; LMS-06 masih perlu review independen Claude.
```
