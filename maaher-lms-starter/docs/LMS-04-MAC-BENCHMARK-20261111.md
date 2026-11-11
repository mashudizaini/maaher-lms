# LMS-04 — benchmark Mac yang dilaporkan pemilik

11 November 2026, Asia/Jakarta. Dicatat **author Codex di cloud** dari ringkasan
hasil Codex CLI yang disampaikan pemilik. Ini bukan berkas asli dari Mac,
bukan pengujian cloud baru, dan bukan review independen Claude.

| Pemeriksaan | Hasil yang dilaporkan |
|---|---|
| Database benchmark | Hanya DB baru |
| Query siswa, 1.500 pelajaran | **31.471,73 → 75,50 ms** |
| Health p95, delapan penyimpanan bersamaan | **13,41 ms** |
| Provider browser | Sintetis |
| Reset / downgrade / merge / deploy | Tidak dilakukan menurut laporan |

File lengkap disebut sebagai `reviews/LMS-04-mac-validation-20261111.md`.
Berkas aslinya belum tersedia di cloud; reviewer di Mac perlu membaca file
tersebut tanpa menimpa atau merekonstruksinya dari ringkasan ini.

Target yang diminta pada langkah sebelumnya adalah source **5b675e6**, schema
**0010_learning_progress**. Ringkasan terbaru tidak menyebut SHA/schema aktual;
reviewer harus memeriksanya dari Git dan catatan lokal, bukan menganggap target
tersebut otomatis terkonfirmasi.

Ringkasan tidak merinci command/data pembanding, baseline health, jumlah sampel,
status respons save, penggunaan budget asli, jumlah API worker atau suite/test
count. Ia juga tidak memberi hasil eksplisit untuk completion, previous/next,
reload, perubahan revision dan revoke. Karena itu tidak dicatat sebagai full
291 API/15 browser Mac atau UAT manual pemilik. Provider sintetis tidak
membuktikan login Auth0 nyata. Cloud sebelumnya memiliki hasil tersendiri pada
source 5b675e6; lihat [handoff](LMS-04-HANDOFF.md) dan performance.json historis.

Angka Mac mendukung perbaikan performa, tetapi status F1/F2 masih menunggu
re-review independen. Gunakan [review request](../reviews/LMS-04-review-request.md)
untuk memeriksa source **4870287..5b675e6**, memvalidasi metode benchmark dan
menguji completion/tenant access. Semua suite/probe harus memakai DB kosong
baru milik reviewer; benchmark F1 mengubah policy sementara, bukan pada DB UAT.

Tidak perlu migrasi atau setup Auth0 ulang untuk mencatat bukti dan meminta
review. Pertahankan laporan lokal, konfigurasi dan database yang ada. Review
auth parent, catatan N2/N3/N4 dan gate produksi tetap terpisah; tidak ada
verdict baru atau persetujuan merge/deploy dari dokumen ini.
