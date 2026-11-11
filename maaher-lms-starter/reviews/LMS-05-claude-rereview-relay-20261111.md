# LMS-05 re-review — catatan relay AUTHOR

11 November 2026, Asia/Jakarta. Sumber: ringkasan Claude CLI yang dikirim pemilik
di chat. Ini catatan AUTHOR, bukan laporan Claude asli atau pengujian ulangnya.
Laporan asli `reviews/LMS-05-claude-rereview.md` berada di Mac; jangan ditimpa.

## Keputusan dan cakupan yang dilaporkan

**APPROVED_WITH_NOTES**, hanya dev/UAT dengan data sintetis. F9 dan F11 CLOSED;
F10 CLOSED_WITH_NOTES. Bukan persetujuan produksi atau auth parent. Reviewer
meninjau HEAD5131f2c, delta84dd193..5131f2c,28 berkas, schema0012; tidak mengubah
source tracked, konfigurasi atau DB lama. Commit dokumentasi13408bb tidak termasuk
delta runtime yang direview. Semua tes menggunakan kontainer baru
`claude-review-pg16-lms05b` dan DB kosong milik reviewer.

## Rekonsiliasi jumlah tes: selesai

- macOS:346 PASS,1 SKIP. Linux/container terpisah:347 PASS,0 SKIP.
- Node ID kedua run identik:347. Angka author sebelumnya344 adalah347 dikurangi
  tiga kasus modul rollback: `test_assignments_migration`,
  `test_enrollment_migration`, `test_learning_migration`.
- Hanya `test_linux_memory_capability_only` memakai skipif(non-Linux).
  Tidak ada `--deselect` atau `-k`. Jadi bukan tiga kegagalan runtime.

## Bukti yang dilaporkan

- F9: dokumen padat valid lolos3/3 dengan CPU262/256/374ms pada budget1000ms,
  margin2,7–3,9×. Dokumen patologis valid dipotong timer nyata pada1007–1012ms,
  respons422, tanpa restart worker. Proofv3 menerima v2 sah, menolak policy
  kosong/tidak dikenal/v1 dan perubahan isi/objek/revisi.
- F10: HTTP/TCP, session dan RLS nyata; enam simpanan normal dan enam draf siswa
  per episode, seluruh penekan aktif. Pada2/4/8 akun, tenant sama/berbeda, normal
  tanpa429/503; draf selalu200, maksimum0,53s. Health p956–13ms, seluruhnya200
  bahkan pada20 akun. Budget tidak dinaikkan.
- F11: surrogate pada12 posisi menghasilkan422 tanpa input/ctx/sentinel;
  empat tanggal ekstrem422 tanpa versi baru. Emoji/CJK tetap diterima.
  Kredensial salah401, tipe salah422 tanpa echo password;500 lama tidak muncul.
- Lima probe regresi lama lulus: proof, SQL/isolation/authority, deadline,
  immutability dan race.

## Catatan kapasitas re-review yang tetap berlaku

Nama berikut khusus **re-review LMS-05**, berbeda dari nomor N pada parent:

- N1: Markdown valid patologis masih0,7–0,9s pada Mac dan lebih dari1s di Linux
  lambat. Kalibrasi hardware target tetap diperlukan.
- N2: waktu antre naik terhadap jumlah tenant penekan; median3,5s pada8 akun,
  6,5s pada12. Tenant baru tidak melompati antrean. Pada16/20 tenant penekan,
  penulis dapat menerima503 secara gagal-aman; ketersediaan authoring masih terbatas.
- N3: batas10 prinsipal/tenant dapat membuat staf lain di tenant yang sama429
  pada10–12 akun penekan; tenant lain tidak ikut terdampak oleh batas tenant ini.

Tidak diuji reviewer: Auth0/FIDO2 nyata, browser, CI remote, image aplikasi,
multi-worker, UAT pemilik atau `--calibrate`. Linux berupa Docker Desktop VM pada
i5-7360U. F12, F3, parent N2/N3/N4, tenant pause dan review penuh auth
8941a79..4733526 tetap terbuka/terpisah. Counter GET grading di LMS-06 nantinya
tidak menutup seluruh catatan GET staf F12.

API pemilik di8000 tidak disentuh. Kontainer reviewer dihentikan, tidak dihapus.
Perintah penghapusan opsional dalam ringkasan tidak dijalankan oleh AUTHOR cloud.
Tidak ada merge/deploy. Kelanjutan LMS-06 memiliki review dan UAT sendiri.
