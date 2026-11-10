# Tenant Auth0 development yang diberikan pemilik

Domain: `dev-hl2un81cojtbhbv4.us.auth0.com`.
Client ID: `FjD4enWFIU9PNdnLjGwc1M1x4p8xsdW3`.
Issuer yang digunakan API:
`https://dev-hl2un81cojtbhbv4.us.auth0.com/`.
Domain dan Client ID bukan secret. Client Secret belum diberikan dan tidak
dibuat-buat oleh sesi ini. Link HTTP dari pesan pemilik dinormalisasi menjadi
HTTPS untuk endpoint IdP; konfigurasi AUTH0_DOMAIN tidak memakai scheme/path.

## Konfigurasi Mac

Pastikan source/migration Auth0 terbaru sudah diterapkan menurut handoff OIDC.
Buka `.env` development yang sudah ada memakai editor lokal, lalu tambahkan
atau perbarui hanya ketiga field berikut. Pertahankan database URL, encryption
key dan semua nilai lain; jangan menimpa `.env` dengan `.env.example`.

```dotenv
AUTH0_DOMAIN=dev-hl2un81cojtbhbv4.us.auth0.com
AUTH0_CLIENT_ID=FjD4enWFIU9PNdnLjGwc1M1x4p8xsdW3
AUTH0_CLIENT_SECRET=
```

Isi Client Secret dari **Application Settings → Client Secret** langsung ke
file lokal yang di-ignore/secret store, tidak melalui chat atau prompt agent.
Client Secret hanya diperlukan API; jangan menaruhnya di NEXT_PUBLIC, web env,
kode Action, URL, log atau repository.

Untuk contoh lokal gunakan origin yang konsisten:

```dotenv
APP_ENV=local
APP_ORIGIN=http://127.0.0.1:3000
LOCAL_INSECURE_COOKIES=true
```

Flag cookie tersebut hanya untuk development loopback HTTP. Di Auth0, pastikan
aplikasi bertipe **Regular Web Application** dan Allowed Callback URLs memuat:

```text
http://127.0.0.1:3000/api/auth/oidc/callback
```

API menggunakan Authorization Code + PKCE, signing RS256 dan token endpoint
authentication Basic. Buka browser dengan 127.0.0.1, bukan localhost, bila
APP_ORIGIN diatur seperti di atas. Restart service development API/web melalui
workflow lokal setelah konfigurasi berubah; source tidak otomatis masuk Mac.

## Prasyarat login nyata

Kehadiran Domain/Client ID/Secret belum berarti akun mendapat izin admin.
Lanjutkan bagian 2 dan 4 pada `AUTH0-SETUP.md`: enrollment security key yang
diverifikasi independen, Guardian UV=required, staff Post Login Action,
app_metadata yang disetujui, serta binding issuer/subject pada database sintetis
baru. User tidak dihubungkan otomatis berdasarkan email. Tidak ada H1/gate
produksi yang dibuka hanya dengan mengisi konfigurasi.

Action secret **MAAHER_CLIENT_ID** di Auth0 berisi Client ID di atas, bukan
Client Secret. Source Action: `infra/auth0/staff-post-login.cjs`.
Verifikasi first-root/enrollment dan claim live sesuai panduan; jangan mengganti
security key dengan email/OTP atau menghapus pemeriksaan assurance agar lolos.

## Hasil pemeriksaan cloud — 10 November 2026 WIB

- Tidak ada AUTH0_DOMAIN/CLIENT_ID/CLIENT_SECRET terinjeksi sebelum konfigurasi
  ini dibuat; tidak ada secret atau runtime binding terkait pada status cloud.
- Read-only GET ke discovery HTTPS dicoba. Proxy menjawab
  `CONNECT tunnel failed, response 403`; tidak ada HTTP response dari Auth0
  (curl HTTP 000). Metadata issuer/JWKS dan aplikasi belum diverifikasi live.
- Network cloud masih restricted; hostname tenant tidak ada pada allowlist.
  Jika pengujian akan dijalankan di cloud, tambahkan exact hostname
  `dev-hl2un81cojtbhbv4.us.auth0.com` pada environment settings sambil
  mempertahankan rule lain. Draft konfigurasi cloud gagal diverifikasi saat
  dibaca dua kali; tidak ada penggantian allowlist atau klaim penyimpanan draft.
- Konfigurasi lokal nonsecret disiapkan. Client Secret tetap kosong; UI login
  staff harus tetap belum aktif sampai konfigurasi API lengkap.

Di Terminal Mac, endpoint publik dapat diperiksa tanpa Client Secret:

```sh
curl --fail --silent --show-error --max-time 20 https://dev-hl2un81cojtbhbv4.us.auth0.com/.well-known/openid-configuration
```

Discovery yang sukses hanya membuktikan endpoint tenant dapat dibaca; tidak
membuktikan konfigurasi callback, Client ID, MFA, binding atau login end-to-end.
