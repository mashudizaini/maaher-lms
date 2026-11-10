# Login development dengan autentikator HP

Pemilik memilih opsi ini pada 10 November 2026 karena belum mempunyai security
key. Gunakan hanya akun dan database sintetis di Mac. Tidak perlu membeli key
untuk langkah development ini. TOTP adalah kode enam digit dari aplikasi HP;
ia bukan security key FIDO2 dan tidak menutup gate H1 produksi.

## 1. Persiapan source di Mac — Codex lokal

Ambil perubahan terbaru branch `feat/LMS-01-auth0-development` dari repository
`mashudizaini/maaher-lms`. Root GitHub berisi subfolder `maaher-lms-starter`.
Periksa Git status terlebih dahulu: jangan reset, overwrite, atau stash otomatis
perubahan pemilik. Jika folder Mac bukan checkout Git atau memiliki perubahan
yang bertabrakan, buat clone baru dengan nama unik, kemudian baca konfigurasi
LMS dari `.env` lama melalui parser dotenv tanpa mencetak atau mengeksekusinya.
Lihat [MAC-SOURCE-SYNC](MAC-SOURCE-SYNC.md). Folder lama yang benar adalah:

```text
/Users/mashudi/Downloads/AiMZ-Corp Project/maaher-lms-starter
```

File baru yang harus ada: `apps/api/migrations/versions/0005_dev_totp.py`,
`apps/api/app/oidc_policy.py`, dan `infra/auth0/development-totp-post-login.cjs`.
Ubah hanya field lokal berikut, pertahankan semua secret/field lain:

```dotenv
APP_ENV=local
APP_ORIGIN=http://127.0.0.1:3000
LOCAL_INSECURE_COOKIES=true
AUTH0_ASSURANCE_PROFILE=dev-totp
```

Domain/Client ID tetap milik aplikasi **Maaher LMS Development**:
`dev-hl2un81cojtbhbv4.us.auth0.com` /
`FjD4enWFIU9PNdnLjGwc1M1x4p8xsdW3`. Client Secret tetap di `.env` Mac,
tidak dipindahkan ke chat, web, Git, atau Action.

Periksa nama database aktual melalui koneksi, bukan hanya teks pada dotenv.
Migration/auth/runtime harus menuju DB sintetis development yang sama dengan
nama `maaher_test_*` dan role terpisah. DB development Auth0 0004 yang sudah
dibuat boleh di-upgrade jika terkonfirmasi hanya berisi data sintetis; simpan
backup dahulu. Jangan menjalankan migrasi pada data pengguna/hasil tes lama.
Gunakan credential migrasi lokal untuk `alembic -c apps/api/alembic.ini upgrade
head` dengan dotenv dimuat sebagai data. Head baru adalah **0005_dev_totp**.
Restart API/web development melalui workflow yang sudah digunakan; pertahankan
volume DB. Default profile tanpa pilihan eksplisit tetap `fido2`.

## 2. Persiapan HP — pemilik

1. Instal **Google Authenticator** atau **Microsoft Authenticator** dari App
   Store/Google Play resmi. Pilih aplikasi dari penerbit Google/Microsoft.
   Tidak perlu berlangganan aplikasi berbayar untuk kode TOTP ini.
2. Aktifkan kunci layar HP dan waktu otomatis. Waktu yang salah dapat membuat
   kode ditolak. Enrollment QR akan muncul di browser Mac pada langkah 4.
3. QR, setup key TOTP, password, kode enam digit dan recovery code hanya Anda
   yang memegangnya. Jangan mengirimnya ke Codex, Claude, chat atau screenshot.

## 3. Atur Auth0 Development — pemilik di Dashboard

Pastikan tenant/app yang dipilih khusus Development. Jangan terapkan perubahan
ini ke aplikasi produksi atau tenant lain. Amankan akun console Auth0 dengan
MFA juga; MFA user LMS tidak melindungi login console.

1. **Security → Multi-factor Auth**: aktifkan **One-time Password / OTP** untuk
   aplikasi autentikator. Aktifkan kebijakan MFA wajib pada tenant development.
   Gunakan Universal Login dan pastikan entitlement tenant mendukung
   `api.authentication.enrollWith` serta `challengeWith`. Jika tidak tersedia,
   laporkan blocker paket; jangan menghapus pemeriksaan MFA/assurance di API.
2. **User Management → Users**: buat/pilih akun uji milik Anda sendiri. Pastikan
   akun ini hanya digunakan untuk data sintetis. Pada **app_metadata**, tambahkan
   boolean berikut sambil mempertahankan field lain:

   ```json
   { "maaher_dev_totp_approved": true }
   ```

   Ini persetujuan pemilik untuk mencoba enrollment **development**, belum
   merupakan binding admin LMS atau verifikasi FIDO2. Jangan memakai
   `user_metadata` atau mengubah `maaher_staff_approved` menjadi bukti produksi.
3. **Actions → Library → Create Action → Login/Post Login**: buat Action bernama
   **Maaher Development TOTP**, lalu salin seluruh source dari
   [development-totp-post-login.cjs](../infra/auth0/development-totp-post-login.cjs).
   Tambahkan Action secret bernama `MAAHER_DEV_CLIENT_ID`, nilainya **Client ID**
   aplikasi Development di atas, bukan Client Secret. Deploy versi Action ini.
4. Di **Actions → Flows → Login**, pasang Action tersebut dan Apply perubahan.
   Jika Action `staff-post-login.cjs` lama saat ini menargetkan Client ID
   Development yang sama, lepaskan Action lama **dari flow development ini**:
   jika keduanya berjalan untuk aplikasi yang sama, policy security key akan
   tetap menolak OTP. Pertahankan source dan policy FIDO2 untuk produksi, dan
   jangan mengubah Action milik aplikasi lain.
5. Pastikan **Allowed Callback URLs** aplikasi exact:
   `http://127.0.0.1:3000/api/auth/oidc/callback`.

Nama menu bisa berbeda antar versi Dashboard. Action meminta **otp** saja,
tanpa faktor alternatif. Claim yang diterbitkan adalah
`https://maaherlms.aimz.my.id/assurance = maaher-dev-totp-v1`.

## 4. Daftarkan HP, kemudian binding — pemilik + Codex lokal

1. Buka `http://127.0.0.1:3000/auth` di browser Mac lalu **Masuk dengan Auth0**.
   Login memakai akun uji. Untuk akun tanpa OTP, Action meminta enrollment dan
   Auth0 menampilkan QR. Di Google Authenticator pilih **+ → Scan a QR code**;
   di Microsoft Authenticator pilih **+ → Other account → Scan QR code**.
   Pindai QR pada Mac dan ketik kode dari HP ke halaman Auth0.
2. Simpan recovery code yang diberikan Auth0 secara pribadi di penyimpanan aman.
   QR/setup key harus tetap rahasia. Setelah enrollment, callback LMS pertama
   **dapat ditolak** karena binding belum dibuat; penolakan ini memang diperlukan.
   Pesan umum di `/auth?oidc=failed` bukan alasan melewati binding.
3. Pemilik memeriksa pada Auth0 bahwa akun uji yang benar sudah mempunyai OTP
   dan enrollment pada HP miliknya selesai. Jika menemukan faktor asing, hentikan
   binding dan periksa akun. Catat referensi non-PII, misalnya
   `dev-totp-owner-verified-20261110`, **hanya setelah benar-benar diperiksa**.
4. Di **User Management → Users → akun uji**, salin **User ID** (`sub`), umumnya
   berbentuk `auth0|...`. Ini berbeda dari Client ID aplikasi. Berikan sub dan
   referensi verifikasi itu kepada **Codex lokal** untuk binding ke UUID admin
   sintetis yang sudah ada. Jangan memberikan kode OTP/password/recovery code.
   Codex memakai CLI `app.oidc_provision`, bukan email auto-link atau SQL untuk
   memaksa `mfa_verified`. Jangan membuat binding sebelum langkah 3.
5. Klik **Masuk dengan Auth0** lagi. Login berikutnya harus meminta kode OTP
   HP yang benar. Sesudah callback berhasil, pilih organisasi sintetis dan
   periksa akses; logout harus mencabut session. Coba pembatalan login dan
   subject yang tidak terikat: keduanya harus ditolak. Jangan mengekspor ID token
   untuk dibagikan; API memverifikasi signature, issuer/audience/nonce,
   auth_time yang fresh, `amr=mfa` dan assurance development sendiri.

## 5. Verifikasi teknis dan hasil nyata

Jalankan checker dari folder source terbaru:

```sh
.venv/bin/python scripts/verify-auth0-local.py --project-root . --start-flow
```

Checker membandingkan profil `.env` dengan profil API yang sedang berjalan dan
head 0005 pada DB sintetis. Sebelum binding, FAIL `identity binding` memang masih
ada. PASS preflight tidak membuktikan token exchange/login nyata atau perangkat
HP yang benar. Catat preflight, enrollment dan login kedua secara terpisah.
Jika Auth0 tidak mengeluarkan `amr=mfa`, auth_time atau claim yang diwajibkan,
catat kegagalan live dan perbaiki konfigurasi provider; jangan menghapus validasi.

Kode membatasi dev-totp pada APP_ENV=local, origin loopback dan **nama database
aktual** maaher_test_*. Resolver memeriksa assurance pada setiap request,
termasuk session lama; profile produksi/default menolak session/token dev.
Nama DB adalah guard terhadap salah konfigurasi, bukan detektor data pribadi:
operator tetap bertanggung jawab memastikan dataset hanya sintetis. Untuk
produksi gunakan tenant/aplikasi terpisah, profile fido2, Action security key dan
enrollment/UV/recovery yang diverifikasi. Tidak ada konversi otomatis dev trust.

## Prompt siap tempel ke Codex CLI

```text
Saya memilih autentikator HP untuk development Maaher dengan data sintetis.
Ambil source terbaru branch feat/LMS-01-auth0-development dari GitHub
mashudizaini/maaher-lms. Root aplikasi GitHub adalah maaher-lms-starter/.
Periksa status Git dan source lokal dahulu; jangan reset/menimpa perubahan saya.
Jika perlu, gunakan clone baru dengan nama unik dan pertahankan folder lama:
/Users/mashudi/Downloads/AiMZ-Corp Project/maaher-lms-starter
Baca AGENTS.md dan docs/AUTH0-DEV-TOTP.md pada source terbaru.
Pertahankan .env/secrets/data. Muat dotenv sebagai data tanpa mencetak nilainya.
Siapkan AUTH0_ASSURANCE_PROFILE=dev-totp, APP_ENV=local dan origin loopback.
Backup dan upgrade hanya DB development Auth0 yang sudah dipastikan sintetis
maaher_test_* dari 0004 ke 0005_dev_totp memakai role migrasi terpisah.
Restart layanan dev dan jalankan checker; jangan menyentuh database lain.
Tunjukkan langkah Dashboard Auth0 dan buka /auth. Saya sendiri yang mengatur
Action/app_metadata dan memindai QR lalu memasukkan OTP. Jangan membuat binding
sebelum saya mengonfirmasi enrollment akun uji yang benar dan memberikan sub
serta referensi non-PII. Setelah itu pakai CLI provisioning existing, uji login
kedua, pemilihan tenant dan logout. Catat hasil nyata dan FAIL/SKIP; pertahankan
gate FIDO2 produksi. Jangan merge/deploy atau mencetak token/secret/QR.
```

Kontrak API Action mengacu ke paket resmi `@auth0/actions` 0.36.0, post-login/v3:
enrollment/challenge harus selesai sebelum login dapat lanjut. Unit/transport
test bukan bukti konfigurasi tenant live. Review independen Claude tetap perlu.

Sumber: https://github.com/auth0/auth0-actions
