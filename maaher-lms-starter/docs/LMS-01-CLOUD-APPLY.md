# Membawa perbaikan cloud ke Mac

Arsip source cloud dan patch bersifat hasil review/implementasi tambahan.
Proyek aktif di Mac mungkin sudah berubah sejak ZIP dibuat. Periksa dahulu
dan gunakan diff yang cocok dengan versi saat ini.

1. Unduh ZIP source cloud dan ekstrak ke **folder baru**. Source tidak membawa
   .env, kredensial, database, dependency, cache atau hasil build.
2. Baca `reviews/LMS-01-cloud-validation.md` serta manifest cloud. Laporan
   independen Claude asli dan manifest/patch Mac historis tetap disertakan.
3. Minta Codex lokal memeriksa file saat ini terhadap before-hash di manifest
   dan patch `reviews/LMS-01-cloud-fixes.patch`. Ada dua perubahan source:
   expiry MFA dan opsi executable browser untuk tes, empat tes regresi baru,
   serta dokumentasi. Tidak ada perubahan skema/migrasi.
4. Di root **starter standalone**, check patch dengan:

```sh
git apply --check /path/ke/hasil-ekstrak/reviews/LMS-01-cloud-fixes.patch
```

   Jika root GitHub memuat subfolder `maaher-lms-starter`, gunakan dari root
   repo: `git apply --check --directory=maaher-lms-starter /path/ke/patch`.
   Jika check gagal, Codex perlu membaca diff dan mempertahankan perubahan
   lokal; tidak menjalankan reset atau memaksa patch. Check tidak menerapkan
   perubahan. Setelah source cocok, Codex dapat menerapkan patch dengan
   pilihan path yang sama dan menjalankan ulang tes terkait.
5. Set keenam URL test ke database PostgreSQL kosong baru. Jalankan suite API
   dan browser sesuai handoff. Jangan memakai DB hasil run lama karena fixture
   sengaja menolak database yang sudah berisi tabel aplikasi.
6. Claude melakukan review ulang atas source final, termasuk dua kasus expiry.
   H1 produksi dan gate eksternal tetap memiliki status terpisah.

## Prompt untuk Codex lokal

```text
Baca docs/LMS-01-CLOUD-APPLY.md dan reviews/LMS-01-cloud-validation.md
dari hasil ekstrak cloud. Bandingkan source aktif dengan before-hash pada
cloud manifest dan patch. Pertahankan perubahan lokal. Terapkan perbaikan
expiry MFA jika cocok; jika sudah ada, verifikasi ekuivalensinya. Tambahkan
keempat regresi dan konfigurasi browser opsional. Jalankan tes pada DB baru
terpisah, perbarui handoff/patch review lokal dan serahkan untuk review ulang
Claude. Jangan apply ulang full patch Mac historis atau mengubah laporan
Claude asli. Tidak ada merge/deploy atau pembukaan gate produksi.
```
