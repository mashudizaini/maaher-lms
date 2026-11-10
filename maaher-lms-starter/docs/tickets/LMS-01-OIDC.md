# LMS-01-OIDC — Auth0 staff login, tahap 1

Disetujui pemilik pada 10 November 2026: gunakan Auth0/OpenID Connect dan
lanjutkan implementasi. Tenant/aplikasi Auth0 belum dibuat; sertakan setup guide.

Lingkup: Authorization Code + PKCE/state/nonce menggunakan Authlib; state
terenkripsi server-side; binding `(issuer, subject)` yang diprovisi offline;
session opak staff dengan assurance security key; validasi membership/RLS tetap
berlaku. Operator ditandai dalam binding privat tetapi tidak diberi API global
atau kemampuan menyetujui recovery user lain pada tahap ini. Tidak auto-link email.

File: API oidc/provisioning, migrasi 0004, resolver session dan guard local auth,
BFF/UI login, dependencies/Compose/env example, Action Auth0, tes dan dokumentasi.

Acceptance: callback sekali pakai terikat browser dan config, PKCE S256,
RS256/JWKS issuer tetap, audience/nonce/auth_time/assurance diverifikasi; subject
asing dengan email sama ditolak; revoke binding/user/membership menghentikan
akses; akun staff yang sudah diikat tidak fallback ke password/TOTP/reset lokal.
Tidak ada token IdP disimpan pada browser/session aplikasi atau audit.

Tes: provider HTTPS sintetis lewat HTTP transport Authlib, token RSA bertanda
tangan, negative claims/replay/state/browser/config, SQL privilege/RLS dan
migrasi roundtrip pada DB baru; regresi lokal/browser/build yang relevan.
Live Auth0 dan security key asli menunggu setup pemilik. Tahap ini bukan klaim
seluruh H1 selesai atau operator approval/recovery produksi sudah aktif.

## Tambahan disetujui — autentikator HP development

10 November 2026: pemilik memilih autentikator HP untuk development sintetis
karena belum mempunyai security key fisik. Lingkup: profile dev-totp eksplisit,
Action enrollment/challenge OTP terpisah, migration 0005 dan guard session,
checker profil/schema, panduan Dashboard/HP/Mac dan tes regresi. Produksi tetap
profile fido2; H1/recovery tidak dianggap selesai.

Acceptance tambahan: start/callback hanya local loopback + DB aktual maaher_test_*,
claim development berbeda dan ditolak profile FIDO2, perpindahan profile/lingkungan
menolak session dev lama, state fingerprint mengikat profile, binding tetap
offline setelah verifikasi pemilik; tenant/RLS tetap terjaga. Migrasi roundtrip
0005→0004→0005 mencabut session dev dan mempertahankan user/binding/session FIDO2.
Tes Action mencakup enrollment awal, login kedua, metadata palsu dan client lain;
browser positif sintetis dijalankan untuk kedua profile. Tidak ada real Auth0
policy change, binding Mac, merge/deploy oleh sesi cloud ini.
