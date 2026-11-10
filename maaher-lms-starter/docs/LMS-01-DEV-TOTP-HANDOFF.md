# LMS-01 — autentikator HP khusus development

10 November 2026. Pemilik menyetujui TOTP HP untuk development sintetis; FIDO2
tetap gate produksi. Source berada pada branch `feat/LMS-01-auth0-development`.
Base perubahan ini: `e5526649c1e96ba94d87a0f0f2d4cc33208eaeea`.

## Perilaku dan file

- `apps/api/app/oidc_policy.py`, `oidc.py`, `database.py`: profile fido2 default;
  dev-totp hanya local/loopback + DB aktual maaher_test_*. Claim berbeda,
  fingerprint mengikat profile dan setiap transaksi auth/tenant memasang
  assurance server. Profile invalid menolak login dan session OIDC existing.
- Migration `0005_dev_totp.py` / `auth0_dev_totp.sql`: constraint assurance dan
  nama DB; resolver session memeriksa assurance pada setiap request. Owner/grant
  fungsi tetap restricted. Runtime tetap tidak bisa membaca tabel OIDC.
- `infra/auth0/development-totp-post-login.cjs`: Action khusus Client ID dev,
  flag app_metadata dev tersendiri, enrollWith OTP awal dan challengeWith OTP
  berikutnya. Tidak ada fallback atau claim FIDO2. Action FIDO2 asli tidak diubah.
- `.env.example` / Compose meneruskan selector hanya ke API. Checker memeriksa
  head 0005 dan kecocokan profile `.env` dengan API yang sedang berjalan.
- Tes API/policy, Action, fixture migrasi dan wrapper browser diperbarui.
  CI root menambahkan Action dev serta browser dev pada database tersendiri.
- `AUTH0-DEV-TOTP.md`: source sync Mac, Dashboard, app_metadata/Action,
  pemindaian QR, callback pertama tanpa binding, binding setelah pemeriksaan
  pemilik dan login kedua. ADR-005/ticket dan tautan panduan lama diperbarui.

## Hasil verifikasi cloud pada source final

| Pemeriksaan | Hasil |
|---|---|
| API/unit `python -m pytest -q -x --tb=short apps/api/tests` | **143 passed**, 0 skip, 85.76s |
| Checker `python -m pytest -q scripts/tests/test_auth0_preflight.py` | **8 passed**, 0 skip |
| Action `node --test infra/auth0/*.test.cjs` | **16 passed**, 0 skip |
| Browser baseline `python scripts/test-lms01-browser.py` | **7 passed** |
| Browser FIDO2 signed synthetic provider `... --oidc` | **1 passed** |
| Browser TOTP signed synthetic provider `... --oidc --dev-totp` | **1 passed** |
| `npm run typecheck`, `npm run build` | **PASS** |
| compileall app/migrations, starter verifier, git whitespace check | **PASS** |

API termasuk token dev ditolak profile FIDO2, state tidak berlaku setelah ganti
profile, session dev ditolak ketika profile/lingkungan berubah, tenant asing
ditolak, DB aktual non-test ditolak (SELECT read-only pada postgres), serta
privilege dan regresi review lama. Fixture memverifikasi 0005→0004→head,
head→0003/0002/0001→head, base→head dan preservasi data fixture; downgrade 0005
mencabut session dev sambil mempertahankan session FIDO2 dan users/binding.

API final memakai DB kosong baru `maaher_test_dev_totp_final_20261110`.
Browser memakai DB terpisah `maaher_test_totp_browser_base_20261110`,
`maaher_test_totp_browser_fido_20261110`, `maaher_test_totp_browser_dev_20261110`.
Container milik sesi cloud: `maaher-cloud-review-20261109`; port saat pengujian
127.0.0.1:32770. Seluruh hasil DB, termasuk dua percobaan awal, dipertahankan.
Container dihentikan setelah validasi. Tidak ada akses Docker/DB/source Mac.

Percobaan awal menemukan kesalahan format URL pada harness Alembic, lalu sebuah
assertion tes memakai fungsi SQL yang memang tidak boleh dipanggil runtime.
Harness diperbaiki; tes memakai list_members yang sah dan memeriksa penolakan
melalui resolver. Tes nama DB juga memastikan konfigurasi valid sebelum memeriksa
penolakan, sehingga tidak lulus karena secret/config belum tersedia. Angka di
tabel adalah run final setelah koreksi tersebut, bukan hasil percobaan awal.
Instalasi npm sempat gagal karena cache default di luar writable root; berhasil
dengan cache `/tmp/maaher-npm-cache`, tanpa mengubah lockfile/TLS. Dua warning
deprecation httpx/Authlib tetap ada. Dependency/lockfile tidak berubah; audit
dependensi tidak diulang pada perubahan ini.

## Migrasi, rollback dan batas

Upgrade hanya DB development Auth0 yang sudah diperiksa sintetis, backup dahulu,
dari 0004 ke **0005_dev_totp**, lalu restart API/web. CLI memakai credential
migrasi, bukan role runtime/auth. Jangan source file dotenv sebagai shell.
Database test lama bukan target upgrade lokal. Panduan operasi lengkap di
[AUTH0-DEV-TOTP](AUTH0-DEV-TOTP.md).

Downgrade 0005→0004 menghapus session dev beserta pending OIDC flows; users,
bindings dan session FIDO2 dipertahankan. Kembalikan profile API ke fido2 pada
rollback. Downgrade lebih jauh menghilangkan guard OIDC dan tetap bukan rollback
produksi yang aman sebagaimana ADR-004.

**Belum diuji:** tenant Auth0 nyata, enrollment HP, token exchange Client Secret
Mac, binding/login nyata dan konfigurasi Dashboard/Actions. Cloud tidak memiliki
secret Mac dan allowlist tidak mencakup tenant Auth0. Browser/transport memakai
provider sintetis dengan signature RSA nyata; tidak mensimulasikan keamanan
perangkat atau menyatakan MFA live sudah lulus. Preflight tidak menutup gap ini.

H1 root trust/recovery produksi tetap terbuka; dev approval tidak diangkat
menjadi produksi. Prod perlu app/tenant terpisah dan FIDO2/UV/recovery yang
diverifikasi. Tidak ada merge/deploy atau perubahan policy Auth0 dari cloud.
Remote CI dan review Claude atas perubahan ini belum terverifikasi.

## Review independen

Laporan Claude awal tetap utuh; SHA256:
`004a19183409b152d0947ab6f5b99af2000d9dd3324c9a2c77ea66a4106032ce`.
Patch/manifest lama adalah snapshot historis. Gunakan diff Git terbaru dan
manifest dev-totp untuk review ini. Untuk penilaian seluruh Auth0, review
`git diff main...HEAD` dari root Git, bukan hanya delta TOTP terhadap base di atas.

```text
Review READ-ONLY branch feat/LMS-01-auth0-development sebagai reviewer independen.
Baca CLAUDE.md/AGENTS.md dan skill lms-security-review pada maaher-lms-starter/.
Mulai dari docs/LMS-01-DEV-TOTP-HANDOFF.md, ADR-005 dan ticket LMS-01-OIDC.
Periksa diff main...HEAD, terutama default FIDO2, claim dev terpisah, pembatasan
local/loopback/DB aktual, resolver session existing, role SQL/RLS, migration
0005 rollback, Action enrollment/challenge dan binding setelah verifikasi pemilik.
Jalankan tes pada DB baru milik review sendiri. Bedakan provider sintetis dari
Auth0 nyata. Pertahankan laporan lama; tulis reviews/LMS-01-dev-totp-claude.md.
Jangan ubah source, data pemilik, policy Auth0, merge atau deploy.
```
