# LMS-05 — hasil Mac yang dilaporkan pemilik

11 November 2026, Asia/Jakarta. Catatan AUTHOR berdasarkan ringkasan Codex CLI
yang dikirim pemilik melalui chat. Pengujian Mac tidak dijalankan ulang dari
cloud dan laporan asli belum tersedia di checkout cloud. Pertahankan laporan
asli `reviews/LMS-05-mac-validation-20261111.md` di Mac tanpa ditimpa.

## Hasil yang dilaporkan

| Pemeriksaan | Hasil menurut ringkasan pemilik |
|---|---|
| Tes API/parser | **38 lulus**; subset, bukan bukti seluruh suite API |
| Tes browser | **2 lulus**, menggunakan provider sintetis |
| Alur fungsional | Draf/reload, versi baru, submission immutable, batas percobaan, deadline, revoke, dan logout teruji |
| Preflight Auth0 | **13 PASS**; bukan bukti login/MFA Auth0 nyata end-to-end |
| Memory cap native macOS | **Tidak tersedia**, bukan PASS untuk pembatasan memori |
| Assertion khusus Linux | Satu assertion dikecualikan secara eksplisit; node ID, cara pengecualian dan jumlah SKIP/deselected tidak dirinci dalam ringkasan |
| UAT manual dengan Auth0 nyata | **Belum dilakukan** |
| Reset/downgrade/merge/deploy | Tidak dilakukan menurut laporan |
| Durasi yang dicantumkan CLI | 16 menit 21 detik |

Jangan menjumlahkan 38 tes Mac dengan 325 API cloud sebagai tes unik. Suite,
platform, waktu dan pengecualiannya berbeda. Angka 325 API/17 browser cloud
berlaku untuk implementasi `4a450d5`; itu tidak membuktikan seluruh suite Mac lulus.

## Batas bukti dan pemeriksaan berikutnya

SHA source/checkout Mac, schema aktif, command tes lengkap, daftar kasus,
perubahan lokal dan cara pengecualian assertion tidak disebut pada ringkasan.
Jangan mengasumsikan semuanya identik dengan `4a450d5`/`0012_assignments`.
Reviewer harus membaca laporan asli dan memeriksa Git/schema aktual secara
read-only. Jika ada perubahan source/test lokal, sertakan dalam review dan
bedakan dari source yang sudah didorong ke GitHub. Jangan menyatakan nol SKIP
atau tidak ada perubahan source berdasarkan ringkasan ini saja.

Ketiadaan RLIMIT_AS pada Mac sesuai batas platform yang sudah didokumentasikan.
Perilaku WARN local/test dan penolakan saat cap tidak tersedia di luar local/test
harus tetap berlaku. Pengecualian boleh menjelaskan assertion kemampuan OS;
jangan menjadikannya bukti cap aktif atau melemahkan pemeriksaan timeout, CPU,
HTTP 422/429, maupun penolakan produksi. Linux/container dengan cap aktif tetap
perlu diuji terpisah oleh reviewer untuk menilai F7. Laporan ini belum membuktikan
image Docker atau konfigurasi container tertentu telah diuji.

Langkah berikutnya adalah review independen F5/F6/F7 dan delta LMS-05 melalui
`reviews/LMS-05-review-request.md`, serta UAT manual pemilik dengan Auth0 nyata
dan data sintetis. Tidak perlu mengulang migrasi/setup Auth0 untuk memulai review.
Semua tes otomatis/benchmark memakai DB kosong baru milik reviewer; jangan memakai
DB UAT atau database lama yang berisi. Full auth parent `8941a79..4733526` tetap
terpisah dan belum memperoleh review penuh. F3/N2/N3/N4 dan tenant pause tidak
dinyatakan CLOSED oleh laporan ini.

## Snapshot artefak

`reviews/LMS-05-author.patch` dan `reviews/LMS-05-manifest.json` tetap snapshot
historis implementasi `4a450d5`, base `54543a8`. Pembaruan ini hanya dokumentasi;
artefak historis tidak diregenerasi. Verifikasi hash snapshot terhadap blob pada
`4a450d5`, lalu tinjau diff dokumentasi setelahnya secara terpisah. Perubahan
handoff/checklist setelah snapshot bukan perubahan implementasi yang tersembunyi.
