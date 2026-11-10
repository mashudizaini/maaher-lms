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
