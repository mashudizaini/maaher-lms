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
4. Pasang Action ke trigger **post-login**. Cari **Actions → Triggers →
   post-login (Login/Post Login)** jika Dashboard tidak menampilkan Flows.
   Pada tampilan yang memakai label lama, jalurnya **Actions → Flows → Login**.
   Pada editor trigger, pilih Action **Maaher Development TOTP** dari bagian
   **Custom**, tambahkan di antara Start dan Complete, kemudian **Apply/Save**.
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

### Audit konfigurasi ketika Action sudah dibuat tetapi QR belum muncul

Object Action di Library, versi yang sudah Deploy, dan pemasangan pada trigger
adalah tiga pemeriksaan terpisah. Target stabilnya **post-login**, bukan sekadar
nama menu Dashboard. Jika Triggers/Flows tidak terlihat, kirim hanya tangkapan
layar sidebar Actions; samarkan data akun dan jangan sertakan secret, QR atau
token. Nama menu tidak membuktikan fitur tidak tersedia atau perlu upgrade paket.

| Pemeriksaan | Nilai/bukti yang diperlukan |
|---|---|
| API lokal | Buka `http://127.0.0.1:3000/api/auth/oidc/config`: enabled=true dan assurance=maaher-dev-totp-v1 |
| Aplikasi Auth0 | Regular Web Application, OIDC/RS256, Authorization Code, token authentication Basic |
| Callback aplikasi | `http://127.0.0.1:3000/api/auth/oidc/callback`, tanpa wildcard |
| Login email | Database connection diaktifkan untuk aplikasi Development; gunakan user dari connection tersebut |
| User approval | app_metadata.maaher_dev_totp_approved adalah boolean true pada profil yang dipakai login |
| Faktor | OTP enabled; pengalaman Universal Login mendukung enrollment/challenge yang diminta |
| Action | Source development-totp-post-login.cjs yang benar pada versi yang sudah Deploy |
| Action secret | Nama MAAHER_DEV_CLIENT_ID ada; pemilik mengisi Client ID Development yang benar, bukan Client Secret |
| Trigger binding | Maaher Development TOTP terpasang dan Apply/Save pada post-login |
| Policy lain | Action FIDO2 lama tidak menargetkan aplikasi Development yang sama |
| Database lokal | Head 0005_dev_totp pada DB sintetis maaher_test_*, role terpisah |
| Identity binding | Tetap menunggu enrollment milik pemilik yang sudah diverifikasi |

Response /config hanya membuktikan profile/config API tersedia. Ia tidak
mengakses Management API atau membuktikan Action aktif, OTP enabled, nilai
secret benar pada token exchange, enrollment, maupun binding. Preflight lokal
juga belum memeriksa deployed Action/trigger/Guardian. Hindari menandai seluruh
Auth0 PASS berdasarkan response itu.

Untuk audit di Mac, Codex lokal boleh menjalankan checker existing dan membaca
setting tenant melalui koneksi Auth0 terautentikasi yang memang sudah tersedia.
Periksa tenant/app target sebelum request, gunakan operasi read-only dan output
ringkasan allowlist. Jangan membaca config credential CLI atau mencetak response
API lengkap/token/secrets. Jika akses Management API atau izin baca tidak
tersedia, tandai item tersebut SKIP/belum diverifikasi dan gunakan pemeriksaan
Dashboard pemilik; jangan mengisi PASS dari asumsi/source test. Pemeriksaan
secret yang hanya dapat melihat namanya tidak membuktikan nilainya benar.

Prompt audit tambahan untuk Codex lokal:

```text
Audit read-only setup Auth0 Development dan LMS yang sedang berjalan.
Gunakan docs/AUTH0-DEV-TOTP.md bagian audit konfigurasi sebagai daftar bukti.
Jalankan checker existing; muat .env sebagai data, jangan cetak nilainya.
Periksa deployed Action, binding trigger post-login, OTP, app settings/callback,
database connection dan app_metadata user uji hanya jika akses baca tenant yang
benar memang tersedia. Ringkas PASS/FAIL/SKIP tanpa response/token/secret/PII.
Jika tidak ada akses baca Auth0, tandai SKIP dan sebutkan halaman Dashboard yang
perlu diperiksa pemilik. Jangan menganggap nama secret membuktikan nilai benar.
Jangan mengubah tenant/Action/DB, membuat binding, reset faktor, merge atau deploy
pada audit ini. Laporkan enrollment/login nyata terpisah dari preflight.
```

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

## Membuat akun email/password saat belum pernah mendaftar

Akun aplikasi Auth0 dapat dibuat oleh pemilik Dashboard; tidak perlu menunggu
tautan Sign up pada halaman login. Login Google mempunyai profil/sub sendiri
dan tidak otomatis menyediakan password untuk login email.

1. Pilih tenant Development Maaher pada Dashboard. Buka **Authentication →
   Database**, pilih connection database yang digunakan (default biasanya
   **Username-Password-Authentication**), lalu tab **Applications** dan aktifkan
   **Maaher LMS Development**. Pada beberapa tampilan, connection juga dapat
   diaktifkan dari tab Connections aplikasi. Jika belum ada database connection,
   buat connection jenis Database untuk aplikasi Development ini.
2. Buka **User Management → Users → Create User**. Pilih database connection
   tadi, isi email akun uji milik sendiri dan password yang kuat, lalu Create.
   Pemilik mengisi password sendiri; tidak mengirimkannya ke agent/chat.
3. Buka user yang baru dibuat dan tambahkan boolean
   `"maaher_dev_totp_approved": true` pada **app_metadata**, pertahankan field
   lain, lalu Save. User ID database biasanya berawalan `auth0|`.
4. Pastikan OTP enabled serta Action **Maaher Development TOTP** yang sudah
   Deploy dipasang pada Login flow dengan Client ID Development yang benar,
   sebagaimana bagian 3 di atas. Akun email tetap memerlukan policy tersebut
   agar QR/enrollment dapat diminta.
5. Buka LMS `/auth` → **Masuk dengan Auth0**. Pada halaman Auth0, isi email dan
   password akun yang baru dibuat, lalu Continue/Login. Gunakan form pada
   halaman Auth0; form email/password lokal LMS memakai sistem identitas lain.
   Lanjutkan QR/OTP sesuai bagian 4, kemudian binding setelah pemilik memverifikasi
   enrollment. Callback pertama tanpa binding tetap dapat ditolak.

Email Gmail yang sama dapat digunakan untuk akun database, tetapi sub profilnya
dapat berbeda dari login Google. Persetujuan dan binding harus merujuk ke user
yang benar-benar digunakan; jangan auto-link berdasarkan kesamaan email.
Nama menu dapat berbeda antar tampilan/peran Dashboard. Jika Create User tidak
tersedia, periksa akses pengelola tenant; public Sign up hanya dapat digunakan
jika database connection memang mengizinkannya. Jangan mengaktifkan signup
publik atau melonggarkan policy demi melewati masalah konfigurasi.

## Jika login Google kembali ke LMS tanpa QR

Persetujuan **Authorize** Google adalah tahap login/consent identitas; enrollment
OTP Auth0 merupakan langkah berikutnya. Login Google didukung Action Post Login.
QR yang tidak tampil belum menunjukkan bug API atau bahwa login MFA berhasil.
Binding kosong memang menolak callback akhir, tetapi tidak mencegah Auth0
menampilkan enrollment QR sebelumnya. Jangan membuat binding untuk mengatasi
enrollment yang belum pernah diselesaikan.

1. Buka Dashboard Auth0 dan pilih tenant
   `dev-hl2un81cojtbhbv4.us.auth0.com`. Di **User Management → Users**, buka
   profil yang baru dipakai **login Google ke LMS**; User ID biasanya berawalan
   `google-oauth2|`. Cocokkan connection dan waktu login. Profil email/password
   dengan email yang sama dapat mempunyai User ID berbeda; approval tidak
   otomatis dibagikan dan akun tidak boleh di-auto-link berdasarkan email.
2. Pada **app_metadata** profil Google sintetis milik Anda itu, tambahkan
   `"maaher_dev_totp_approved": true` sebagai boolean. Pertahankan field lain dan
   Save. Nilai string `"true"` atau flag di user_metadata tidak diterima.
3. Periksa versi **Maaher Development TOTP** sudah Deploy, dipasang pada
   **Actions → Flows → Login** dan perubahan flow sudah Apply. Secret Action
   **MAAHER_DEV_CLIENT_ID** harus sama dengan Client ID aplikasi Development.
   Periksa OTP aktif. Bila Action FIDO2 lama masih menargetkan aplikasi
   Development yang sama, ikuti langkah 3.4 di atas; produksi tetap terpisah.
4. Periksa apakah akun sudah memiliki faktor OTP. QR hanya untuk enrollment
   baru; akun yang sudah enrolled seharusnya diminta kode OTP. Bila faktor yang
   tercatat tidak Anda kenal, hentikan proses dan periksa kepemilikan akun;
   jangan menghapus faktor atau membuat binding hanya agar login lolos.
5. Setelah konfigurasi disimpan, mulai login baru lewat tombol LMS, bukan
   memakai URL callback/authorization lama. Gunakan akun Google yang sama.
   Selesaikan QR/OTP sendiri dan periksa enrollment sebelum binding offline.

Jika masih kembali tanpa QR maupun challenge OTP, **Monitoring → Logs** →
percobaan terakhir untuk aplikasi Development. Catat hanya Type dan
Description/pesan error Action yang telah disamarkan. Jangan membagikan JSON
log lengkap, email/nama, URL callback, token, QR atau kode OTP.

| Pesan yang ada pada source Action | Pemeriksaan yang sesuai |
|---|---|
| `Owner approval for synthetic development is required` | Flag app_metadata boolean pada **profil yang benar-benar login**, termasuk profil Google |
| `Development login policy is not configured` | Secret Action MAAHER_DEV_CLIENT_ID tersedia pada versi yang sudah Deploy |
| `Verified staff enrollment is required` | Action FIDO2 lama masih berjalan; periksa flow/Client ID Development |
| `Staff login policy is not configured` | Action FIDO2 lama berjalan dengan konfigurasinya belum lengkap |
| Pesan faktor/fitur tidak tersedia | OTP enabled dan entitlement Action enrollment/challenge; catat pesan sebenarnya |
| Log login sukses tetapi LMS menolak | Keberhasilan IdP belum membuktikan MFA/binding; periksa Action, klaim wajib dan callback lokal tanpa mencetak nilainya |

Tabel ini menghubungkan pesan dengan pemeriksaan, bukan bukti penyebab pada
tenant live. Jangan menghapus pemeriksaan MFA/assurance atau menyalin approval
ke akun lain tanpa verifikasi pemilik. Tes sintetis tidak menggantikan log dan
enrollment nyata ini.

## Pesan LMS generik: diagnosis satu percobaan login

Pesan `Login Auth0 gagal atau tidak diizinkan` tidak membedakan penolakan
provider, state/cookie, token/assurance dan identity binding. Jika QR/OTP belum
pernah diminta, jangan membuat binding untuk melewati kegagalan itu. Respons
`/api/auth/oidc/config` yang enabled dan dev-totp juga tidak membuktikan Action
sudah menjalankan enrollment.

Source terbaru menambahkan diagnosis API yang **default off**. Pada development
Mac saja, set `AUTH0_LOCAL_DIAGNOSTICS=true` di `.env` sambil mempertahankan field
dan secret lain. API hanya mencatat kode tetap bila APP_ENV=local dan origin
loopback; flag tidak mengaktifkan diagnostic di produksi/nonloopback. Rebuild/
restart hanya API development melalui workflow yang sedang digunakan agar source
dan flag termuat. Pertahankan database/container dan jangan source dotenv sebagai
shell. Untuk uvicorn, gunakan `--no-access-log`; jangan mengaktifkan debug/log
HTTP body atau membagikan request callback.

Pemilik melakukan **satu login baru** di browser Mac dan memasukkan password/OTP
sendiri. Codex lokal kemudian membaca kode melalui salah satu cara berikut:

```sh
# Jika API dijalankan melalui Compose proyek ini:
.venv/bin/python scripts/read-auth0-diagnostics.py --compose

# Jika API memakai proses lokal dengan file log yang sudah diketahui:
.venv/bin/python scripts/read-auth0-diagnostics.py --log-file /path/to/private-api.log
```

Reader hanya mencetak kode allowlist terbaru. Raw stdout/stderr Compose,
exception, path file dan isi log lain tidak ditampilkan. Tidak perlu mengunggah
log, `.env`, URL callback, cookie atau token. Reader read-only dan dibatasi 200
entri Compose/10 menit atau 1 MiB terakhir file. Jika service memakai project/file
Compose khusus, gunakan konteks proses yang benar melalui Codex lokal; jangan
mencoba project/container lain. Exit 0 = kode ditemukan, **bukan login lulus**;
exit 1 = gagal membaca log; exit 2 = belum ada kode, bukan bukti sukses.

| Kode | Langkah pemeriksaan |
|---|---|
| OIDC_OWNER_APPROVAL_REQUIRED | app_metadata boolean true pada user yang benar-benar login, termasuk akun email baru |
| OIDC_DEV_POLICY_UNCONFIGURED | Nama secret Action MAAHER_DEV_CLIENT_ID pada versi yang sudah Deploy |
| OIDC_FIDO2_POLICY_ACTIVE / OIDC_STAFF_POLICY_UNCONFIGURED | Action FIDO2 lama ikut menargetkan aplikasi Development; periksa scope tanpa mengubah produksi |
| OIDC_PROVIDER_DENIED | Error provider belum dikenali; periksa Action/OTP/entitlement dan pesan error Auth0 yang disamarkan |
| OIDC_ASSURANCE_MISMATCH | Claim development tidak cocok/hilang; periksa deployed source, trigger binding dan Client ID pada secret Action |
| OIDC_MFA_MISSING | Token tidak membawa amr=mfa; periksa enrollment/challenge provider, pertahankan validasi MFA |
| OIDC_CLIENT_AUTH_FAILED | Client ID/Secret API serta Basic token-endpoint authentication pada aplikasi |
| OIDC_CODE_EXCHANGE_REJECTED | Code ditolak provider; mulai flow baru, periksa callback/PKCE dan konfigurasi aplikasi |
| OIDC_INVALID_CALLBACK / OIDC_FLOW_UNAVAILABLE | Cookie/origin, callback baru dan masa berlaku flow; gunakan 127.0.0.1 secara konsisten |
| OIDC_FLOW_CONFIG_CHANGED / OIDC_FLOW_PAYLOAD_INVALID | Flow dibuat sebelum perubahan config/key atau payload tidak dapat dibaca; mulai flow baru dengan konfigurasi konsisten |
| OIDC_PROVIDER_HTTP_FAILED / OIDC_PROVIDER_PROTOCOL_ERROR / OIDC_ID_TOKEN_INVALID / OIDC_TOKEN_RESPONSE_INVALID | Koneksi/protokol/validasi token; diagnosis lokal tanpa raw token/exception |
| OIDC_AUTH_TIME_INVALID / OIDC_SUBJECT_INVALID | Freshness/subject tidak memenuhi validasi; periksa provider dan waktu server |
| OIDC_IDENTITY_UNAVAILABLE | Identitas aktif yang terikat belum ditemukan; lanjut binding **hanya setelah** enrollment milik pemilik diverifikasi |

Kode dari `error_description` callback hanya memetakan **pesan exact** yang
dikenal ke kode tetap. Callback error itu belum terautentikasi; hasilnya petunjuk
untuk diperiksa, bukan bukti setting tenant atau proof yang mengizinkan binding.
Unknown message menjadi OIDC_PROVIDER_DENIED tanpa menyalin isinya. Respons/UI
tetap generik; tidak ada policy, session atau akses yang dilonggarkan.

Jika tidak ada kode, cek apakah API terbaru/flag sudah termuat dan callback
mencapai API. Error konfigurasi/DB sebelum handler callback dapat memerlukan
diagnosis service lokal tersendiri. Jangan menyimpulkan binding adalah penyebab
hanya karena DB menunjukkan nol binding. Sesudah diagnosis selesai, kembalikan
AUTH0_LOCAL_DIAGNOSTICS=false dan restart API development.

Prompt siap tempel untuk kasus pesan gagal generik:

```text
Login Auth0 masih gagal dan belum pernah meminta QR/OTP. Profile API sudah
enabled=true, assurance=maaher-dev-totp-v1. Ambil source terbaru branch
feat/LMS-01-auth0-development tanpa menimpa perubahan lokal atau konfigurasi saya.
Baca bagian diagnosis callback pada docs/AUTH0-DEV-TOTP.md. Pertahankan seluruh
data/secret. Aktifkan AUTH0_LOCAL_DIAGNOSTICS=true hanya pada API development
local/loopback, rebuild/restart proses yang benar sesuai workflow existing.
Matikan access log callback; jangan cetak raw log/URL/exception/token/secret.
Buka /auth dan beri saya waktu menyelesaikan satu login sendiri. Setelah itu
jalankan read-auth0-diagnostics.py --compose atau --log-file sesuai proses API
yang benar. Laporkan hanya kode allowlist terbaru dan langkah yang sesuai.
Jangan membuat binding sampai saya memverifikasi enrollment OTP milik saya.
Jika akses baca Auth0 tersedia, verifikasi setting relevan read-only; tandai
SKIP bila tidak tersedia. Jangan melemahkan MFA, merge atau deploy.
```

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
