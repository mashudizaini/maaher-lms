# Menjalankan verifikasi di Mac yang memiliki .env

Pilihan terbaru pemilik adalah autentikator HP untuk development sintetis.
Ikuti [AUTH0-DEV-TOTP](AUTH0-DEV-TOTP.md), gunakan checker dari source branch
terbaru dan migration **0005_dev_totp**. Paket checker lama yang hanya mengenali
0004 harus diganti. Instruksi security key historis di bawah hanya untuk profile
fido2. `--start-flow` tetap tidak melakukan enrollment/login/binding.

Penyesuaian `.env` di Mac tidak menyinkronkan credential ke cloud. Pada pemeriksaan
sesi ini, cloud tidak mempunyai `.env` utama, binding secret atau akses jaringan
ke tenant Auth0. Karena itu validasi live perlu dijalankan di Mac Anda.

Paket `maaher-auth0-live-check.zip` berisi checker dan unit tests, tanpa `.env`,
client secret atau perubahan kode aplikasi. Ekstrak ke Downloads, kemudian dari
Terminal host Mac:

```sh
cd "/Users/mashudi/Downloads/AiMZ-Corp Project/maaher-lms-starter"
.venv/bin/python "/Users/mashudi/Downloads/maaher-auth0-live-check/scripts/verify-auth0-local.py" --project-root . --start-flow
```

Gunakan Python virtual environment proyek yang sudah berisi dependency LMS-01.
Jika lokasi ekstrak berbeda, sesuaikan path script. Jangan menjalankannya di
sandbox lama yang menolak Docker/network; gunakan Terminal host atau Codex lokal
dengan izin perintah yang diperlukan. Jangan menonaktifkan TLS verification.

Checker membaca dotenv sebagai data (bukan shell), mempertahankan semua file,
dan tidak mencetak nilai secret/DB URL/cookie/state/nonce/response body. Ia:

1. Memeriksa source OIDC dan field lokal sesuai Domain/Client ID yang diberikan.
2. Membaca discovery dan public JWKS lewat HTTPS; hanya endpoint canonical
   tenant yang diikuti, bukan URL lain dari response yang tidak cocok.
3. Membaca migration/restricted role/binding pada DB sintetis memakai transaksi
   read-only. Tidak menjalankan migrasi, provisioning, cleanup, atau SQL write.
4. Memeriksa konfigurasi yang dimuat service API/web. Dengan `--start-flow`,
   membuat satu flow login diagnostik maksimal lima menit dan memeriksa cookie,
   callback, state/nonce serta PKCE. Flow itu tidak dibuka dan tidak login,
   mengirim email, atau mengubah session browser Anda.

Hasil PASS berarti langkah preflight tersebut berhasil, **bukan** login nyata,
validitas Client Secret terhadap token endpoint, policy/security-key yang aktif
di Auth0 atau izin produksi. Exit 1 = ada FAIL; exit 2 = ada langkah SKIP dan
tidak ada FAIL; exit 0 = seluruh langkah preflight yang dijalankan lulus.

Jika source/schema belum 0005, source Auth0 terbaru belum diterapkan/migrasi dev belum
aktif. Jika binding belum ada, lakukan verifikasi user/key dan provisioning
terkontrol pada runbook; jangan auto-link email atau mengubah MFA flags lewat SQL.
Jika DB URL memakai hostname internal Compose seperti `db`, koneksi dari Terminal
host bisa gagal sementara aplikasi dalam container tetap dapat mengaksesnya.
Minta Codex lokal memeriksa DB read-only dari konteks network container yang
sesuai tanpa mencetak credential; jangan membuka port database ke Internet.
Jika service belum memuat `.env`, restart API/web melalui workflow development
yang sudah digunakan sambil mempertahankan database dan nilai konfigurasi lain.

Setelah preflight lulus, buka halaman `/auth` pada origin yang dipakai dan klik
**Masuk dengan Auth0** di browser Mac. Pemilik menyelesaikan login/security-key
sendiri; tidak perlu memberikan password/PIN/recovery code kepada agent.
Pastikan callback kembali tanpa code/state pada URL, tenant yang sah bisa dipilih
dan logout mencabut akses. Catat kegagalan sebagai hasil nyata; jangan melemahkan
Action/assurance checks agar login berhasil. Lihat AUTH0-SETUP.md dan handoff.

Output checker aman untuk dibagikan sebagai status. Jangan membagikan `.env`,
raw token, cookie, authorization URL, isi database, atau log provider lengkap.

## Prompt untuk Codex CLI lokal

```text
.env sudah disesuaikan pada proyek Mac ini. Jalankan verify-auth0-local.py
dari paket checker dengan --project-root ke root proyek dan --start-flow.
Jangan mencetak file .env atau nilai secret. Periksa setiap FAIL/SKIP dan
selesaikan masalah source, service, network atau DB development yang dapat
ditangani tanpa menimpa perubahan/data pengguna. Pertahankan data DB/container.
Untuk binding/enrollment, gunakan verifikasi independen sesuai runbook;
jangan auto-link email atau membuka bypass produksi. Jika membutuhkan login
hardware key, buka halaman /auth dan minta saya menyelesaikannya sendiri.
Catat hasil preflight dan login nyata terpisah. Jangan merge/deploy.
```

Validasi checker di cloud: enam unit tests redaction/issuer/callback/read-only
guard lulus; script compile lulus. Login nyata Mac/Auth0 belum dijalankan oleh
sesi cloud ini. Suite aplikasi terakhir tetap 123 API, 8 browser dan 8 Action;
angka tersebut tidak dianggap sebagai bukti login terhadap tenant live.
