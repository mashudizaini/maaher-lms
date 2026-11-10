# REA + Codex — pemeriksaan 2026-11-09

Sumber resmi yang dibaca:
- https://github.com/morluto/rea/blob/main/docs/getting-started/installation.md
- https://github.com/morluto/rea/blob/main/package.json
- https://developers.openai.com/codex/mcp

`codex mcp list`: tidak ada server MCP terkonfigurasi. Tidak ada tool REA
di sesi ini. Konfigurasi global dibaca hanya untuk mencari entri REA/MCP,
tidak diubah. Skill REA lokal proyek hanya aturan observasi; itu bukan server.

Upstream package.json yang diperiksa menyatakan rea-agents 6.8.0 dengan Node
`^22.23.4 || ^24.22.1 || >=26.12.1`. Node lokal `24.13.0` tidak memenuhi.
Periksa ulang metadata versi yang akan dipasang; jangan melewati engine check.
`npx --offline rea-agents setup --help` gagal ENOTCACHED. DNS shell dibatasi;
paket tidak diunduh dan setup tidak dijalankan. Tidak ada registrasi duplikat
atau modifikasi konfigurasi lama.

Lanjutkan di Terminal lokal dengan jaringan dan Node yang kompatibel. Gunakan
direktori akuisisi tepercaya di luar proyek; jangan jalankan paket dari folder
target Timedoor. Periksa metadata npm (repository harus morluto/rea), pilih
versi eksplisit yang kompatibel, lalu jalankan help versi tersebut. Dokumentasi
upstream saat pemeriksaan mendukung alur berikut:

```sh
node --version
npm view rea-agents version engines repository --json
codex mcp list
# Contoh versi upstream yang diperiksa; verifikasi terhadap npm sebelum eksekusi.
npx rea-agents@6.8.0 setup --help
npx rea-agents@6.8.0 setup --client codex --dry-run
npx rea-agents@6.8.0 setup --client codex
codex mcp list
```

Jika sudah ada `rea` melalui MCP atau plugin, inspeksi entri itu dan jangan
menambahkan jalur instalasi kedua. Review preview setup; hanya pilih Codex.
Pertahankan setting lainnya dan backup yang dibuat installer; jangan install
Hopper atau provider native untuk pemetaan alur website. Config global berada
di luar writable roots sesi ini, sehingga perubahan global perlu dilakukan
melalui Terminal lokal. Tidak perlu mengirim credential apa pun ke chat.

Setelah setup berhasil, tutup dan buka kembali aplikasi Codex, buka workspace
yang sama dan lanjutkan percakapan ini. Untuk CLI, akhiri sesi lalu jalankan
`codex resume` dari folder proyek dan pilih sesi ini. Periksa ulang `codex mcp
list` dan ketersediaan tool REA setelah restart; registrasi saja belum membuktikan
server berjalan.

Instruksi melanjutkan: “Baca docs/LMS-01-HANDOFF.md dan REA-FINDINGS.md,
verifikasi REA, jalankan tes PostgreSQL, lanjutkan LMS-01. Untuk Timedoor saya
akan login sendiri di browser lokal.” Setelah tool browser REA tersedia,
minta pemilik login sendiri pada https://lms.timedooracademy.com/ dan konfirmasi
peran yang tersedia. Amati navigasi yang sah, jangan submit tugas, mengubah
nilai/data, membaca cookie/token, atau mengunduh materi vendor. Catat bukti
OBSERVED/INFERRED/UNKNOWN dengan PII disamarkan. Observasi belum dilakukan.
