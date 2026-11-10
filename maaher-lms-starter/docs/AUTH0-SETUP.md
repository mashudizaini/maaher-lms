# Setup Auth0 development untuk Maaher LMS

Tujuan tahap ini: login admin/operator lewat identity yang diikat sebelumnya,
tanpa membuka akses produksi. Tenant/aplikasi development sudah dibuat; nilai
publiknya ada pada AUTH0-TENANT-LOCAL.md. Gunakan user dan database sintetis. Panduan tidak
membutuhkan password, client secret, security key PIN atau recovery code di chat.

**Pilihan terbaru pemilik: autentikator HP untuk development.** Ikuti
[AUTH0-DEV-TOTP](AUTH0-DEV-TOTP.md) untuk profile dev-totp, migration 0005,
Action OTP dan pemindaian QR. Bagian security key di bawah tetap berlaku untuk
profile default fido2/produksi, bukan langkah wajib onboarding HP development.

## 1. Tenant dan aplikasi

1. Buat akun Auth0 melalui situs resminya, lalu tenant **Development**. Pilih
   region sesuai kebutuhan lokasi data organisasi. Amankan login **console
   Auth0** dengan MFA pada identity/provider console dan siapkan recovery-nya;
   MFA pada user aplikasi bukan pengganti perlindungan console.
2. Periksa paket/entitlement: WebAuthn roaming/security keys, required user
   verification, Actions challenge API serta kebutuhan backup/recovery harus
   tersedia. Jangan mengaktifkan metode lebih lemah untuk melewati blocker paket.
   Tidak ada harga/subscription diasumsikan atau dibeli oleh kode ini.
3. Applications → Applications → Create Application. Nama usulan
   **Maaher LMS Development**; pilih **Regular Web Applications**.
4. Gunakan domain canonical tenant, misalnya `nama-tenant.us.auth0.com`, tanpa
   scheme/path. Custom domain belum didukung implementasi tahap pertama.
5. Dengan `APP_ORIGIN=http://127.0.0.1:3000`, daftarkan **Allowed Callback URLs**:

```text
http://127.0.0.1:3000/api/auth/oidc/callback
```

   Gunakan origin yang sama saat membuka browser. localhost dan 127.0.0.1 adalah
   origin berbeda. Hindari wildcard. Untuk UAT HTTPS, tambahkan URL callback exact
   pada origin UAT yang benar; HTTP hanya diizinkan pada local loopback eksplisit.
6. Aktifkan OIDC conformant, signing algorithm **RS256**, grant
   **Authorization Code**, token-endpoint authentication **Basic**. Jangan
   aktifkan implicit/password/client-credentials sebagai jalur login staff ini.
   Tidak meminta refresh token/offline_access. Tidak perlu membuat API audience:
   ID token diverifikasi terhadap Client ID aplikasi.
7. Catat **Domain** dan **Client ID**. Keduanya nonsecret. **Client Secret** hanya
   disimpan di konfigurasi API yang aman, tidak dikirim ke chat atau browser.

Nama menu Auth0 dapat berubah; pastikan nilai konfigurasinya sesuai, bukan
sekadar mengikuti nama menu. Kehadiran konfigurasi bukan bukti flow live lulus.

## 2. Security keys, first enrollment dan Action

1. Security → Multi-factor Authentication: aktifkan WebAuthn **security keys /
   roaming**, set **User Verification = Required**, dan wajibkan MFA untuk
   aplikasi staff. Periksa fitur aktual tenant/plan sebelum melanjutkan.
2. Buat user staff sintetis. Siapkan enrollment resmi Auth0 dalam proses yang
   diawasi pemilik pada perangkat yang diketahui. **Jangan** memberi binding
   admin/operator Maaher hanya karena user bisa membuka email atau login password.
   Periksa enrollment/factor yang ada dan cabut yang tidak dikenal sebelum
   memberi wewenang. Verifikasi kunci cadangan atau prosedur recovery yang sesuai
   benar-benar didukung tenant/paket; jangan menganggapnya sudah tersedia.
3. Implementasi ini tidak menyediakan onboarding root otomatis. Action di bawah
   sengaja menolak user tanpa roaming factor yang sudah terdaftar. Jika belum
   ada jalur enrollment independen yang dapat diverifikasi, catat sebagai blocker
   root trust; jangan mengubah Action menjadi auto-enroll password/email-only.
4. Pada **app_metadata**, setelah verifikasi identitas/perangkat dan key selesai,
   set `maaher_staff_approved` ke boolean `true`. Jangan memakai user_metadata.
5. Actions → Login/Post Login: buat custom Action dengan source
   `infra/auth0/staff-post-login.cjs`. Tambahkan Action secret
   `MAAHER_CLIENT_ID` dengan **Client ID** aplikasi staff tadi (bukan Client Secret).
   Deploy Action dan hubungkan ke Login flow aplikasi/tenant.
6. Action meminta `challengeWith({type: 'webauthn-roaming'})` tanpa fallback;
   ID token tidak diterbitkan jika challenge tidak terpenuhi. Ia menambahkan
   claim `https://maaherlms.aimz.my.id/assurance = maaher-fido2-uv-v1`.
   Guardian UV=required tetap merupakan konfigurasi wajib yang harus diverifikasi.
7. Uji bahwa token live mengandung `amr` dengan `mfa`, `auth_time` yang baru,
   nonce/audience/issuer yang benar serta claim assurance tersebut. Jangan
   menghapus pemeriksaan claim pada API bila tenant tidak mengeluarkannya;
   perbaiki konfigurasi dan catat hasil Auth0 yang sebenarnya.

Kontrak Action diperiksa dari paket resmi `@auth0/actions` 0.36.0,
Post Login v3. Subsequent Actions tidak berjalan sebelum challenge selesai;
jika factor tidak enabled/enrolled dan tidak ada factor valid, transaksi gagal.
Unit tests Action bukan bukti tenant live sudah menerapkan kebijakan ini.

Sumber:
- https://github.com/auth0/auth0-actions
- https://github.com/auth0/terraform-provider-auth0/blob/main/docs/resources/guardian.md

## 3. Konfigurasi lokal

Perbarui file `.env` lokal yang sudah ada secara hati-hati. Pertahankan semua
nilai/secret lama dan jangan menyalin secret ke repository. Contoh **nama** nilai:

```dotenv
APP_ENV=local
APP_ORIGIN=http://127.0.0.1:3000
LOCAL_INSECURE_COOKIES=true
AUTH0_DOMAIN=
AUTH0_CLIENT_ID=
AUTH0_CLIENT_SECRET=
```

Isi tiga nilai Auth0 dari tenant development. `AUTH_ENCRYPTION_KEY`/keyring dan
credential DB terpisah yang sudah digunakan LMS-01 tetap diperlukan. Secret
Auth0 hanya diteruskan Compose ke API, tidak ke service web. Jangan memakai
prefix NEXT_PUBLIC untuk secret. File dotenv adalah data; jangan mengeksekusinya
sebagai script shell. Untuk cloud, exact hostname tenant juga harus diizinkan
network policy sebelum token/JWKS exchange; tidak perlu wildcard *.auth0.com.

## 4. Database dan binding development

Minta Codex lokal memeriksa cluster Docker yang ada dan membuat **database
development kosong baru** berprefix `maaher_test_`, misalnya
`maaher_test_auth0_dev`. Gunakan role migration/auth/runtime yang sudah terpisah;
periksa port aktual Docker. Jangan menunjuk DB hasil tes lama atau data pengguna.
Jalankan migrasi sampai **0004_auth0_oidc** menggunakan credential migration.

Buat user/tenant sintetis lewat CLI provisioning existing pada DB tersebut.
Setelah User ID Auth0 dan key-nya diverifikasi, ikat `(issuer, subject)` ke
UUID user aplikasi dengan CLI baru dari root starter:

```sh
PYTHONPATH=apps/api .venv/bin/python -c 'from dotenv import load_dotenv; load_dotenv(".env"); from app.oidc_provision import main; main()'
```

CLI meminta UUID user aplikasi, issuer `https://DOMAIN/`, Auth0 User ID (`sub`),
apakah operator, serta referensi verifikasi non-PII. CLI memakai migration URL,
menolak non-test DB, tidak membuat user/role dari email dan tidak menimpa binding
yang sudah ada. Binding mencabut session/reset lama. `is_operator` bukan
keanggotaan admin tenant; untuk admin harus ada membership admin yang benar.

Jalankan aplikasi menurut workflow lokal/Compose setelah nilai konfigurasi
lengkap, buka `/auth`, lalu **Masuk dengan Auth0**. Akun staff yang telah diikat
harus memakai Auth0; password, reset dan TOTP lokal tidak menjadi fallback.

## 5. UAT live yang perlu dicatat

- User bound + security key yang benar dapat login dan memilih tenant yang sah.
- Subject berbeda dengan email sama ditolak; tidak ada auto-signup/link.
- Akun belum disetujui, factor email/OTP/recovery-code saja, atau key yang belum
  diverifikasi tidak mendapat login staff. Perubahan kebijakan/fallback IdP harus
  ditinjau bersama Action; konfigurasi provider adalah bagian dari trust boundary.
- Callback salah/replay/expired, MFA dibatalkan dan IdP outage ditolak dengan
  error terkendali. Token/code tidak disalin ke screenshot, log atau chat.
- Cabut binding/user/membership dan pastikan akses yang terkait berhenti.
  Provider-only revocation belum otomatis logout session aplikasi: cabut session/
  binding Maaher juga. Session staff maksimal 30 menit.
- Hilang password/email LMS tetapi masih mempunyai identity/key Auth0 yang
  terdaftar: login OIDC tetap dapat dilakukan tanpa password/email LMS. Hilang
  seluruh faktor Auth0 memerlukan recovery IdP/console yang terpisah dan diuji.
- Catat pengujian kunci cadangan dan pemulihan console. Status H1 produksi belum
  ditutup oleh sekadar berhasil login dev.

Endpoint metadata `/auth/oidc/session` hanya menunjukkan konteks session sendiri.
Tahap ini tidak membuka API global atau approval recovery user lain. Integrasi
operator approval harus mengikat proof fresh ke target yang identitasnya juga
diverifikasi; mengetahui request UUID tidak cukup. Full recovery siswa tanpa
binding independen, SMTP/inbox, ingress/TLS, backup/restore, remote CI serta
review ulang Claude tetap pekerjaan/gate terpisah.

Setelah aplikasi Auth0 dibuat, yang dapat dibagikan di chat hanya **Domain dan
Client ID**. Client Secret diisi lewat konfigurasi lokal/secret store.
