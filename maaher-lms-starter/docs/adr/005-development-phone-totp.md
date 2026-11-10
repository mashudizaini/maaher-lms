# ADR-005 — TOTP HP khusus development sintetis

Status: dipilih pemilik pada 10 November 2026. Pemilik belum memiliki security
key fisik. Auth0/OIDC tetap dipakai; kebijakan produksi tetap FIDO2 roaming
dengan UV required. TOTP lebih rentan phishing dan tidak menjadi bukti FIDO2.

Profile server `AUTH0_ASSURANCE_PROFILE` default `fido2`. Pilihan `dev-totp`
hanya valid dengan APP_ENV=local dan origin loopback yang exact. Settings yang
invalid menolak start/callback; auth/runtime transaction memakai assurance
`disabled` sehingga session OIDC lama ikut ditolak. Tidak ada request/header/
token yang dapat memilih profile server. Profile masuk fingerprint flow.

Migration 0005 menambah assurance `maaher-dev-totp-v1` pada oidc_sessions dengan
constraint nama database aktual maaher_test_*. Start/callback memeriksa nama
aktual itu juga. Resolver SECURITY DEFINER tetap dimiliki role NOLOGIN semula;
memeriksa profile transaksi dan nama DB saat memvalidasi token session pada
setiap request. Default SQL tanpa konteks hanya menerima assurance FIDO2.
Runtime tidak mendapat akses baru ke tabel/kunci/provider material. Tenant
membership dan RLS tetap wajib. Tidak ada auto-link email atau local fallback.

Action development terpisah ditargetkan hanya ke Client ID Development. Flag
app_metadata `maaher_dev_totp_approved` adalah persetujuan pemilik untuk mencoba
enrollment sintetis; tidak sama dengan produksi `maaher_staff_approved`.
Action meminta enrollWith otp saat belum enrolled, atau challengeWith otp pada
login berikutnya, tanpa fallback. Keduanya hanya menerbitkan claim development.
Pemilik menyelesaikan enrollment sendiri; binding offline baru dilakukan setelah
pemilik memeriksa akun/faktor. Callback pertama tanpa binding tetap ditolak.
Semua validasi OIDC (signature/PKCE/nonce/freshness/amr) tetap berlaku.

Ini izin development dengan data sintetis, bukan penyelesaian bootstrap/recovery
H1 produksi. Guard nama DB bukan klasifikasi isi data. Deployment harus memakai
tenant/app terpisah dan konfigurasi produksi yang direview. Approval developer
dan faktor TOTP tidak dipromosikan menjadi staff trust/FIDO2 otomatis.

Downgrade 0005→0004 mencabut session dev dan membersihkan pending OIDC flows,
mempertahankan users/bindings/session FIDO2 serta mengembalikan constraint dan
resolver 0004. Downgrade lebih jauh tetap membawa risiko hilangnya guard OIDC
sebagaimana ADR-004. Backup dan review independen tetap diperlukan.

Panduan pemilik/Codex lokal: [AUTH0-DEV-TOTP](../AUTH0-DEV-TOTP.md).
