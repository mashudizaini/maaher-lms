# LMS-01 Auth0/OIDC — handoff development

Pemilik menyetujui Auth0/OIDC pada 10 November 2026 dan menyatakan tenant serta
aplikasinya belum dibuat. Tahap ini menyiapkan login development; tidak membuat
akun layanan, memilih paket berbayar, mengirim pesan atau deploy.
**H1 produksi tetap OPEN dan review ulang Claude tetap diperlukan.**

## Implementasi

- `app/oidc.py`: Authorization Code + PKCE S256/state/nonce melalui Authlib
  1.9.5/joserfc 1.8.0; RS256/JWKS, issuer/audience/expiry/auth_time/assurance
  diverifikasi. State disimpan terenkripsi di server dan dikonsumsi sekali
  sebelum token exchange. Cookie browser hanya capability opak.
- Migration **0004_auth0_oidc**: binding issuer/subject privat, login flow dan
  konteks provider session. CLI binding development tidak auto-link email,
  membuat role atau mengganti binding yang ada; ia mencabut session/reset lama.
- Session staff maksimal 30 menit; tidak ada fallback password/reset/TOTP lokal
  setelah user pernah diikat, termasuk jika binding dicabut. Reset pra-binding
  tidak dapat mencabut session OIDC atau mengganti credential staff.
- Membership, user/binding aktif dan RLS tetap diperiksa setiap akses. Marker
  operator tidak memberi tenant admin/global privilege. Tidak ada API global
  atau approval recovery orang lain pada tahap ini.
- BFF callback allowlist, penerusan cookie korelasi dan redirect URL UI fixed.
  UI menyediakan login Auth0 dan mengarahkan staff ke pengelolaan faktor IdP.
- Action meminta WebAuthn roaming tanpa optional fallback; UV=required dan
  enrollment key independen harus diverifikasi pada tenant. Tidak auto-enroll
  root berdasarkan email/password. Rotasi key/retensi mencakup flow OIDC.

Lihat [panduan setup](AUTH0-SETUP.md), [ADR-004](adr/004-auth0-development-login.md)
dan [ticket](tickets/LMS-01-OIDC.md).

## Validasi cloud

Run gabungan awal: 121 PASS/1 FAIL pada retensi karena SELECT kolom expires_at
belum diberikan kepada definer. Hak kolom itu ditambahkan tanpa SELECT state
terenkripsi. Run berikutnya **122 API PASS**, 2 warning, 82.26s tanpa SKIP.
Run final menambah regresi login staff tanpa password/email LMS:
**123 API PASS**, 2 warning, 140.15s, tanpa SKIP. Ini 71 kasus sebelumnya
ditambah 52 kasus OIDC; assertion lama tidak dihapus untuk membuat tes hijau.

Browser source final: **7 PASS** baseline/security, 22.0s, dan **1 PASS** OIDC
positif, 5.6s; tanpa SKIP. Probe positif memakai signature JWT RS256, HTTP
transport IdP sintetis, validator Authlib sebenarnya, API/BFF/Next dan Chromium
aktual. **Ini bukan login ke Auth0 nyata.** Action unit **8 PASS**; typecheck,
production build, pip check, compileall dan verify-starter PASS. Snapshot PyPI:
39 pin runtime, 0 findings/errors; npm produksi: 0 vulnerabilities.

Lingkungan: PostgreSQL 16.15, Python 3.12.14, Node 24.22.1, Next 16.4.5,
Chromium 156.0.8078.79. Warning API terkait deprecation httpx di Authlib dan
Starlette TestClient. GitHub Actions/image runtime/Mac tidak dijalankan ulang.

Fixture menguji head→0003→head, head→0002→head, head→0001→head, base→head.
Session OIDC dicabut pada downgrade 0004, identity/password lama dipertahankan,
18 tabel aplikasi diperiksa hilang setelah base. Downgrade mengembalikan auth
lama yang lebih lemah, bukan rollback produksi aman tanpa maintenance plan.

Semua DB cloud baru/sintetis: final `maaher_test_oidc_final_3`, browser baseline
`maaher_test_oidc_browser_final` dan browser positif
`maaher_test_oidc_positive_browser`, pada container cloud milik sesi ini
`maaher-cloud-review-20261109` (port setelah restart 127.0.0.1:32769).
Data DB/container Mac tidak diakses. Container cloud dihentikan setelah
validasi, seluruh database hasil dipertahankan.

## Reproduksi

Gunakan DB pengujian kosong baru dan keenam TEST_* URL/role terpisah sesuai
handoff lama. Root starter:

```sh
.venv/bin/pip install -r apps/api/requirements-dev.lock
.venv/bin/python -m pytest -q -ra --tb=short apps/api/tests
node --test infra/auth0/staff-post-login.test.cjs
npm --prefix apps/web ci
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
# Ganti TEST_* URLs ke DB browser kosong yang berbeda untuk setiap command:
PLAYWRIGHT_EXECUTABLE_PATH=/usr/bin/chromium .venv/bin/python scripts/test-lms01-browser.py
PLAYWRIGHT_EXECUTABLE_PATH=/usr/bin/chromium .venv/bin/python scripts/test-lms01-browser.py --oidc
```

Di Mac gunakan PLAYWRIGHT_CHANNEL=chrome atau executable Chrome yang sesuai.
Wrapper baseline sengaja mengosongkan konfigurasi Auth0. `--oidc` memilih
test-only uvicorn target di tests/ dengan HTTP mock dan signature RSA; tidak
ada trust override dalam API produksi. Runtime Dockerfile tidak menyalin tests.
CI ditambah untuk Action dan kedua mode browser; remote run belum terjadi.

## Masih diperlukan

1. Buat tenant Development dan Regular Web Application Auth0. Callback lokal:
   `http://127.0.0.1:3000/api/auth/oidc/callback`. Domain dan Client ID nonsecret;
   Client Secret hanya pada API melalui konfigurasi lokal/secret store.
2. Verifikasi enrollment key/first-root, MFA console, backup key/recovery dan
   entitlement paket pada tenant nyata. Action menolak staff tanpa key yang
   sudah terdaftar. Template bukan bypass enrollment-root.
3. UAT live atas claims/PKCE/callback/key challenge, subject asing, kehilangan
   credential LMS/key, revoke, TLS/proxy dan IdP outage. Provider-only revocation
   belum otomatis logout session aplikasi; cabut binding/session Maaher juga.
4. Operator approval bagi user lain dan full recovery siswa tanpa identity
   independen belum diimplementasikan. Login staff tidak menutup seluruh H1.
5. SMTP/inbox, ingress/edge, retensi operasional, backup/restore, review Claude
   serta persetujuan release tetap gate terpisah. Tidak ada domain wildcard atau
   credential dummy disimpan sebagai konfigurasi Auth0 produksi.

## Menerapkan dan review di Mac

Ekstrak source ke folder baru. Patch OIDC incremental memakai
`maaher-lms-cloud-fixed.zip` sebagai baseline; cumulative patch memakai ZIP
review pertama pemilik dan mencakup dua fix expiry MFA cloud sebelumnya.
Manifest mencatat before/after hash; patch historis Mac tetap dipertahankan.

Minta Codex lokal membandingkan source aktif dengan manifest lalu memilih patch
yang cocok. Jalankan `git apply --check` dari root starter standalone; dari root
GitHub nested tambahkan `--directory=maaher-lms-starter`. Bila gagal, rekonsiliasi
diff sambil mempertahankan perubahan lokal; tidak melakukan reset atau apply
ulang full patch historis. Sesudah tes lokal, Claude meninjau token validator,
state/config binding, role SQL, fallback, Action, migrasi/rollback dan bukti live
yang tersedia. Tidak ada approval baru yang ditulis atas nama Claude.
