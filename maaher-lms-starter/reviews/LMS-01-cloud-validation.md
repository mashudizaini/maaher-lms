# LMS-01 — validasi dan perbaikan tambahan di cloud

Tanggal: 10 November 2026 WIB. Peran: Codex AUTHOR. Ini tidak menggantikan
review independen Claude; tidak ada approval, commit, merge, push atau deploy.

## Integritas input

- ZIP pemilik: `maaher-lms-review.zip`, 328560 byte, SHA-256
  `638a2f79784a19da26d5f107c43b0b5f80158066604909e6b1dc04654d51f24a`.
- Sebelum perubahan: 70 file dalam ZIP cocok dengan manifest AUTHOR; tidak ada
  mismatch. Lima file tidak masuk ZIP: `.gitignore` dan empat skill di `.agents`
  serta `.claude`. Semuanya dipulihkan dari full patch dan cocok dengan hash
  manifest, bukan dibuat ulang dari perkiraan.
- Baseline GitHub `8941a79dcf611df66c4ee43e78b902b62ddbfce2` dibaca dari objek
  Git yang tersedia. 25 file baseline diekstrak ke direktori sementara; full
  patch lolos check dan diterapkan **hanya ke salinan baseline sementara**.
  Hasilnya cocok dengan seluruh 75 file manifest. Ada dua warning whitespace
  patch historis, tidak ada kegagalan apply.
- Hash full patch, incremental patch dan laporan Claude asli cocok dengan
  manifest. SHA laporan Claude asli tetap
  `004a19183409b152d0947ab6f5b99af2000d9dd3324c9a2c77ea66a4106032ce`.
- `LMS-01-review-manifest.json` adalah snapshot input historis. Perubahan cloud
  dicatat terpisah di `LMS-01-cloud-manifest.json`; manifest historis tidak
  diubah untuk memberi kesan source lama dan baru identik.

## Temuan tambahan dan perbaikan

### R1 — request operator kedaluwarsa selalu mengembalikan ID lama

`request_authorization()` mengembalikan row lama tanpa memeriksa expiry.
Sesudah sepuluh menit, klik ulang tetap menghasilkan ID yang tidak dapat
disetujui operator. Test baru pada source input mereproduksi ID lama yang sama.

Perbaikan di `apps/api/app/mfa.py`: hapus hanya request kedaluwarsa milik
session/purpose tersebut sebelum membuat request baru. Audit independen
operator tetap dipertahankan. `ON CONFLICT ... RETURNING id` membuat retry
request yang belum kedaluwarsa tetap idempotent tanpa menimpa approval.

Regresi membuktikan ID diperbarui, grant lama ditolak, grant baru dapat dipakai
sekali dan kedua audit approval dipertahankan. Regresi terpisah memastikan
retry ID yang masih valid tidak membatalkan grant dan replay tetap ditolak.

### R2 — setup recovery expired menutupi faktor aktif yang sah

`verify()` memilih pending enrollment berdasarkan keberadaan row, sebelum
memeriksa expiry. Pending recovery expired tetap menutupi active factor;
kode autentikator lama yang sah selalu ditolak dengan 400. Test source input
mereproduksi penolakan tersebut tanpa mengganti faktor aktif.

Perbaikan: pending enrollment dipilih hanya jika belum expired. Faktor aktif
yang trusted tetap dapat digunakan bila setup recovery ditinggalkan.
Enrollment expired tanpa faktor aktif tetap tidak dapat menaikkan session.
Tidak ada penghapusan atau penggantian faktor aktif, password, atau pelemahan
syarat approval operator. Tidak ada migrasi database baru.

Keempat regresi ada di `apps/api/tests/test_mfa_expiry_regressions.py`.

## Hasil yang dijalankan di cloud

Lingkungan: Python 3.12.14, PostgreSQL 16.15 dalam container baru,
Node 24.22.1, Next 16.4.5, Playwright 1.65.0 dan Chromium sistem
156.0.8078.79. Koneksi runtime/auth/operator/mail/maintenance terpisah dan
role nonowner/non-BYPASSRLS sesuai fixture. Trust socket database hanya untuk
cluster sintetis ini dengan port yang dipublikasikan pada loopback.

| Pemeriksaan | Hasil aktual |
| --- | --- |
| API input, sebelum perbaikan | 67 passed, 1 warning, 55.02s; tanpa SKIP |
| Empat probe expiry pada source input | 2 failed (R1/R2), 2 passed, 5.07s |
| API setelah perbaikan | **71 passed**, 1 warning, 63.29s; tanpa SKIP |
| Browser setelah perbaikan, Next production + API nyata | **5 passed**, 26.2s |
| Migrasi dan rollback | Jalur 0001→head, head→0002→head, head→0001→head, base→head dijalankan fixture kedua suite API; assertions preservasi legacy dan penghapusan 15 tabel lulus |
| Role SQL aktual dan probe COMMIT uvicorn | Lulus di suite API, termasuk barrier sebelum response dan failure login/logout |
| Typecheck dan production build | Lulus; typecheck diulang sesudah perubahan konfigurasi browser |
| pip check / compileall / verify-starter | Lulus |
| PyPI advisory runtime | 34 pin diperiksa; 0 findings/errors |
| npm audit produksi | 0 vulnerabilities |

Warning API: deprecation Starlette TestClient terhadap backend httpx.
Warning warna log browser tidak mengubah hasil. Audit advisori adalah snapshot
pada waktu run dan tidak memverifikasi keamanan deployment/OS.

Command inti, dari root source dengan keenam `TEST_*_DATABASE_URL` menunjuk
ke database baru yang kosong:

```sh
.venv/bin/python -m pytest -q -ra --tb=short apps/api/tests
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
# Gunakan DB browser kosong yang terpisah dari DB suite API.
PLAYWRIGHT_EXECUTABLE_PATH=/usr/bin/chromium .venv/bin/python scripts/test-lms01-browser.py
.venv/bin/pip check
.venv/bin/python scripts/verify-starter.py
.venv/bin/python -m compileall -q apps/api/app apps/api/migrations apps/api/tests scripts
.venv/bin/python scripts/audit-api-dependencies.py
npm --prefix apps/web audit --omit=dev
```

Opsi `PLAYWRIGHT_EXECUTABLE_PATH` ditambahkan ke config browser untuk memakai
Chromium yang terpasang. Tanpa opsi tersebut, perilaku channel/download browser
sebelumnya tetap berlaku. Di Mac gunakan channel Chrome sesuai handoff lama;
path Linux di atas bukan perintah untuk Mac.

Container khusus run cloud: `maaher-cloud-review-20261109`, port saat run
127.0.0.1:32768. DB input `maaher_test_cloud_review_1`, probe sebelum fix
`maaher_test_cloud_probe_1`, final `maaher_test_cloud_final_1`, dan browser
`maaher_test_cloud_browser_1`. Tidak ada akses ke database atau Docker Mac.
Container milik run cloud dihentikan setelah validasi dan datanya dipertahankan.

## Batas klaim dan langkah lanjut

- H1 produksi belum CLOSED: root trust/operator MFA belum dipilih. Adapter
  sintetis tetap menolak produksi dan DB non-test. Recovery faktor yang diuji
  masih memerlukan password-valid session; total credential loss belum didukung.
- Belum diuji dalam sesi ini: SMTP hingga inbox nyata, MFA/SSO operator nyata,
  ingress Cloudflare/TLS publik, edge rate limit, backup/restore drill, GitHub
  Actions remote, Mac, build image runtime/test Docker. Tidak ada klaim rerun
  item tersebut dari laporan sesi lokal sebelumnya.
- Perubahan source dan keempat regresi memerlukan review ulang Claude bersama
  perbaikan Mac sebelumnya. Laporan Claude lama tetap CHANGES_REQUESTED.
- Pilihan operator produksi perlu jawaban pemilik. Rekomendasi untuk dievaluasi:
  IdP/SSO terkelola dengan MFA yang dipaksakan untuk operator/admin, faktor
  phishing-resistant dan recovery yang tidak hanya mengandalkan email LMS.
  Ini usulan arsitektur, belum keputusan atau integrasi yang diaktifkan.
- Cara membawa patch ke Mac: `docs/LMS-01-CLOUD-APPLY.md`. Source asli di ZIP
  dan salinan proyek sebelumnya tetap dipertahankan; tidak ada perubahan Mac
  atau GitHub yang terjadi otomatis.
