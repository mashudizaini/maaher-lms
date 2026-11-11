# LMS-05 fixes — hasil Mac yang dilaporkan pemilik

11 November 2026, Asia/Jakarta. Catatan AUTHOR berdasarkan ringkasan Codex CLI
yang dikirim pemilik; bukan review independen atau pengujian ulang di Mac.
Laporan asli `reviews/LMS-05-fixes-mac-validation-20261111.md` belum ada pada
checkout cloud. Pertahankan laporan asli di Mac tanpa ditimpa catatan ini.

## Hasil yang dilaporkan

| Pemeriksaan | Hasil menurut ringkasan pemilik |
|---|---|
| Source aktif | **5131f2c** |
| API/web | Dibangun dan direstart tanpa migrasi |
| Tes | **343 PASS, 1 SKIP**, khusus capability memori Linux; **0 deselected** |
| Browser | **2 PASS** |
| Fairness 2/4/8 akun | Seluruh penyimpanan normal dan draf siswa berhasil |
| Memory cap native macOS | **WARN_MEMORY_UNAVAILABLE**; bukan bukti cap aktif |
| Preservasi | .env, keyring, binding, laporan dan DB lama dipertahankan |
| Reset/downgrade/merge/deploy | Tidak dilakukan |
| Durasi CLI | 17 menit 31 detik |

Identitas provider browser, command lengkap, daftar kasus, nilai CPU/margin,
latensi/status per fase fairness dan schema DB aktual tidak disebut pada
ringkasan terbaru. Jangan menganggap login Auth0 nyata, manual UAT, CI remote,
image Docker, multi-worker atau active memory cap Linux sudah diuji di Mac.
Baca laporan asli untuk memperjelas batas-batas tersebut. Source5131f2c sendiri
tidak menambah migrasi; head schema yang didukung tetap0012_assignments.

## Rekonsiliasi cakupan tes

Cloud menjalankan347 API/parser PASS pada5131f2c, lalu5 kasus antrean diulang
setelah perluasan cakupan HTTP siswa, tanpa perubahan runtime. Pemeriksaan lokal
`python -m pytest --collect-only -q apps/api/tests` pada source itu kembali
menemukan **347 kasus**; ini pemeriksaan koleksi, bukan pengujian runtime baru.

Ringkasan Mac menjelaskan343+1=344 kasus. Ada **3 kasus yang belum terpetakan**
terhadap koleksi347. Jangan menyatakan full-suite Mac atau menyimpulkan3 kegagalan.
Nol deselected tidak dengan sendirinya membuktikan seluruh file/kasus dikoleksi.
Reviewer perlu mencocokkan command, file/marker/ignore/config, hasil koleksi dan
node ID dari laporan asli; catat alasan setiap perbedaan. Jangan mengubah kode,
menonaktifkan tes, atau menjalankan fixture pada DB lama untuk mengejar angka.

SKIP kemampuan Linux sesuai batas platform yang terdokumentasi. Verifikasi node
SKIP benar-benar capability-only, dan tes kontrol/frame/dense valid30k/CPU tetap
berjalan. Untuk F9, baca sampel kalibrasi CPU1000ms/wall3000ms dan margin di host
sebenarnya. Untuk F10, konfirmasi HTTP/sesi nyata serta penulis dan draf siswa
saat akun penekan aktif, bukan hanya model thread. F11 tetap perlu probe input
mentah tanggal/surrogate422 dan Unicode valid. Ringkasan sukses bukan verdict
independen CLOSED untuk F9/F10/F11.

## Langkah berikut dan artefak

Lakukan review ulang melalui `reviews/LMS-05-rereview-request.md`, memakai laporan
asli dan source aktual. Semua tes/benchmark reviewer harus memakai DB kosong
baru miliknya; jangan ulang setup/migrasi Auth0 atau menyentuh DB UAT/DB lama.
Simpan laporan baru `reviews/LMS-05-claude-rereview.md`, pertahankan laporan lama.

Patch/manifest fixes tetap snapshot **5131f2c**, base **84dd193**. Pembaruan ini
hanya dokumentasi; artefak historis tidak diregenerasi. Cek hash terhadap blob
5131f2c, kemudian tinjau diff dokumentasi berikutnya. Patch/manifest LMS-05 awal
tetap snapshot4a450d5. F12 dan temuan lama, full auth8941a79..4733526, serta
manual real-Auth0 UAT tetap terpisah/terbuka. Tidak ada persetujuan merge/deploy.
