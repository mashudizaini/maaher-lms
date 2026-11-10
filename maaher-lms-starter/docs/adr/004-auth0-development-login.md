# ADR-004 — Auth0/OIDC login staff tahap pertama

Tambahan 10 November 2026: [ADR-005](005-development-phone-totp.md) menambah
profile TOTP HP yang dibatasi local/synthetic. Assurance FIDO2 di ADR ini tetap
default dan wajib untuk gate produksi. Head migrasi terbaru 0005.

Status: implementasi development setelah pemilik menyetujui Auth0/OIDC pada
10 November 2026. Belum diuji dengan tenant Auth0 nyata; tidak membuka gate H1
produksi. Lihat `docs/tickets/LMS-01-OIDC.md` dan `docs/AUTH0-SETUP.md`.

## Boundary dan protokol

- Authlib 1.9.5 menangani Authorization Code + PKCE S256 dan validasi ID token
  melalui joserfc/JWKS. Issuer serta endpoint Auth0 canonical dibentuk dari
  konfigurasi server; algoritma dipin RS256. Tidak menerima bearer ID token atau
  URL discovery/JWK dari browser/token. HTTP client mempertahankan TLS/proxy.
- State, nonce, verifier PKCE dan redirect_uri disimpan dalam ciphertext
  `oidc_login_flows`. Browser hanya mendapat cookie korelasi acak HttpOnly,
  Secure, Lax. State dan cookie harus cocok; TTL lima menit. Konsumsi state
  di-COMMIT sebelum token exchange, sehingga kegagalan exchange/commit akhir
  tetap membutuhkan flow baru dan tidak membuka replay.
- ID token harus valid untuk issuer, client audience, nonce, expiry/iat/azp;
  auth_time wajib dan maksimal lima menit; amr mengandung mfa. Claim assurance
  namespaced wajib `maaher-fido2-uv-v1`, diterbitkan Action staff yang meminta
  challenge WebAuthn roaming tanpa fallback. Guardian harus mewajibkan user
  verification. amr=mfa saja tidak cukup.
- Setelah token diverifikasi, `(issuer, subject)` harus terikat ke user aktif
  melalui provisioning offline. Tidak ada pembuatan user, binding atau kenaikan
  role lewat email, claim role/domain, ID token saja atau input browser.
- Session aplikasi tetap opak dan dirotasi. Tidak ada access/ID/refresh token
  disimpan di cookie, database, URL UI atau audit. Session staff maksimal 30 menit.
  Konteks provider menyimpan hanya binding, auth_time dan assurance; IdP harus
  menjalankan challenge lagi pada login baru (`prompt=login`, `max_age=0`).

## Database dan penutupan fallback

Migration **0004_auth0_oidc** menambah tiga tabel global privat. Role auth boleh
membaca binding, tidak membuat/mengubahnya. Role tenant tidak bisa membaca atau
membuat identity/flow/provider session. Definer resolver dapat membaca konteks
minimal, dan retensi hanya SELECT kolom expires_at + DELETE pada flow.

Begitu user pernah memiliki binding, session lokal tidak menjadi authority lagi,
termasuk setelah binding dicabut. Password login/reset dan perubahan TOTP lokal
ditolak untuk akun tersebut. Reset yang diterbitkan sebelum binding juga tidak
dapat mengubah password atau mencabut session OIDC. CLI development binding
mencabut session/reset lama. Tidak ada implicit unlink/fallback karena IdP mati.

Resolver session memeriksa binding aktif dan user aktif pada setiap request.
`tenant_admin`, RLS dan membership aktif tetap menentukan izin tenant. Marker
`is_operator` privat tidak memberi hak tenant admin atau akses global.
Pencabutan binding atau user langsung menghentikan akses; pencabutan membership
menghentikan akses tenant tersebut. Pencabutan **hanya di Auth0** belum disinkronkan
otomatis ke session aplikasi: cabut binding/session aplikasi juga. Back-channel
revocation/log-out integration dan incident runbook adalah pekerjaan berikutnya.

Provisioning CLI dibatasi local + maaher_test_*; produksi memerlukan ceremony
root/operator terverifikasi dan runbook yang direview. Tidak ada endpoint publik
untuk menghubungkan akun atau menyetujui recovery orang lain. Adapter MFA
sintetis lama tetap test-only; ia tidak dipakai sebagai proof OIDC produksi.

## Dampak migrasi dan rollback

Migration 0001–0003 tidak ditulis ulang. Fixture menambahkan jalur head→0003→head
dan membuktikan session OIDC dicabut pada downgrade, sementara identity/password
lama dipertahankan. Setelah base, 18 tabel aplikasi harus hilang. Tidak ada
migrasi yang dijalankan pada DB Mac/pengguna dalam sesi cloud.

Downgrade menghapus binding/konteks OIDC dan mengembalikan perilaku auth lokal
0003 yang lebih lemah. Ini **bukan rollback produksi yang aman** tanpa maintenance,
backup dan penonaktifan akun terkait; session OIDC tidak dikonversi menjadi local
trusted session. Retensi/rotasi kunci mencakup encrypted OIDC flow yang baru.

## Batas tahap ini

Kode login, binding, guard dan provider session tersedia untuk development.
Tidak ada akun/tenant Auth0, enrollment hardware nyata, recovery console IdP,
approval operator untuk target lain, full recovery siswa, SMTP/inbox, remote CI,
TLS/ingress atau deploy yang dianggap terverifikasi. H1 tetap terbuka.

Eksperimen provider memakai HTTP transport HTTPS sintetis dan JWT RSA yang
benar-benar ditandatangani, melewati client/token validator Authlib sebenarnya;
ini berbeda dari menjalankan Auth0 nyata. Hasil akhir ada di handoff OIDC.
