# LMS-01 — diagnosis callback Auth0 development

10 November 2026. Base delta ini: `ec98cbe`. Pemilik melaporkan pesan generik
LMS setelah menyesuaikan Action, serta mengonfirmasi QR maupun permintaan OTP
belum muncul. Respons API lokal yang dibagikan pemilik adalah enabled=true dan
assurance=maaher-dev-totp-v1. Ini membuktikan profile lokal, bukan setting IdP.
Root cause live belum terbukti; binding belum boleh dipakai untuk melewati
enrollment yang belum diselesaikan.

## Perubahan

- `apps/api/app/oidc_diagnostics.py`: enum kode tetap dan logger opt-in
  AUTH0_LOCAL_DIAGNOSTICS=true, hanya APP_ENV=local + origin loopback valid.
  Default off. Mapping exact empat pesan policy Action ke kode allowlist;
  teks callback lain tetap generic, tidak dicetak. Callback error belum
  terautentikasi: kode mapping adalah petunjuk, bukan proof IdP/approval.
- `apps/api/app/oidc.py`: denial mengeluarkan kode tahap hanya pada log privat
  development. State/cookie/config, provider, token/assurance/MFA/freshness dan
  identity binding dibedakan. Response/URL/UI tetap generik; tidak ada code,
  token, subject, email, exception atau secret yang masuk diagnostic.
  Konsumsi state, verifikasi token, session/grant dan membership tetap berlaku.
- `.env.example` / Compose: flag API baru dengan default false, tidak ke web.
- `scripts/read-auth0-diagnostics.py`: membaca log Compose proyek (200 entri,
  10 menit, stdout+stderr ditangkap) atau 1 MiB terakhir file API lokal. Hanya
  kode allowlist terakhir yang dicetak. Raw log, path, error subprocess dan
  output lainnya tidak dikirim ke stdout/chat. Exit 0 berarti kode ditemukan,
  bukan login lulus; exit 1 gagal baca; exit 2 belum ada code/SKIP.
- Tes guard/log redaction, mapping exact dan callback bertanda tangan ditambah;
  reader ditambahkan ke CI root. Panduan diagnosis Mac dan ticket diperbarui.

## Validasi pada source final

| Pemeriksaan | Hasil |
|---|---|
| `PYTHONPATH=apps/api python -m pytest -q -x --tb=short apps/api/tests` | **170 passed**, 0 skip, 68.11s |
| `python -m pytest -q apps/api/tests/test_oidc_diagnostics.py scripts/tests/test_oidc_diagnostic_reader.py scripts/tests/test_auth0_preflight.py` | **31 passed**, 0 skip (19 sudah termasuk suite API; 12 tes scripts) |
| `python scripts/test-lms01-browser.py --oidc --dev-totp` | **1 passed**, Chromium, signed synthetic provider |
| Reader smoke dari warning proses Python nyata ke file privat | **PASS**, hanya OIDC_PROVIDER_DENIED yang tercetak |
| compileall app/reader, starter verifier, git whitespace check | **PASS** |

Tes callback memverifikasi reason owner/unknown provider, assurance, MFA,
binding, payload, nonce dan exchange; error publik tetap sama, token/session
tidak terbit, state tidak dapat direplay dan sentinel/cookie-state/code/secret
tidak ada pada log diagnosis. Unit tests memeriksa flag default off, produksi,
nonloopback, URL invalid, exact match serta guard reader semua enum termasuk
kode FIDO2. Suite API juga mencakup roundtrip migrasi 0001–0005 dan regresi
privilege/tenant/review sebelumnya.

Run API pertama berhenti pada regresi key rotation karena tes diagnosis baru
sengaja merusak seluruh baris flow. Tes diperbaiki agar hanya merusak flow milik
tes itu sendiri melalui state_hash. Run final di DB kosong baru seluruhnya lulus;
tidak ada bypass/skip atau perubahan key rotation untuk membuatnya lulus.

Database hasil yang dipertahankan: `maaher_test_oidc_diag_20261110` (awal),
`maaher_test_oidc_diag_final_20261110` (final), dan
`maaher_test_oidc_diag_browser_20261110` (browser). Container cloud milik sesi
`maaher-cloud-review-20261109`, port saat tes 127.0.0.1:32771, dihentikan sesudah
validasi. DB/container/source Mac tidak diakses atau diubah oleh cloud.

Frontend, Action Auth0, dependency dan migration tidak berubah. Build/typecheck,
audit dependency, suite Action dan delapan browser lain tidak diulang pada delta
ini; hasil historis tetap snapshot sebagaimana handoff dev-totp. Dua warning
deprecation httpx/Authlib tetap ada. Remote CI/review Claude belum diverifikasi.

## Kelanjutan Mac dan rollback

Ambil source terbaru dengan mempertahankan perubahan lokal. Ikuti bagian
diagnosis pada [AUTH0-DEV-TOTP](AUTH0-DEV-TOTP.md): flag true hanya development,
restart/rebuild API yang benar, owner melakukan satu login baru, reader mencetak
kode aman dan Codex lokal menindaklanjuti dengan bukti. Jangan mencetak raw API
log/callback atau meminta password/OTP/QR/token pada agent/chat. Jangan membuat
binding sebelum enrollment milik pemilik diverifikasi; jangan menghapus validasi.

Tidak ada migrasi baru. Kembalikan flag false dan restart API setelah diagnosis.
Rollback source tidak memerlukan perubahan data/schema. Tidak ada perubahan
policy tenant Auth0, provisioning, merge atau deploy dari sesi cloud ini.
Login nyata/OTP enrollment serta akar masalah Mac tetap menunggu bukti live.
Gate H1 produksi dan review independen tetap terbuka.

Reviewer: periksa diff delta `ec98cbe..HEAD` untuk logger/reader; review keseluruhan
Auth0 melalui `git diff main...HEAD`. Pastikan generic public error, opt-in local
guards, tidak ada raw provider/exception/secret log atau jalur auth yang dilonggarkan.
Laporan Claude awal tetap utuh, SHA256
`004a19183409b152d0947ab6f5b99af2000d9dd3324c9a2c77ea66a4106032ce`.
Manifest/patch lama adalah snapshot historis, gunakan snapshot diagnostics untuk
delta ini. Jangan mengubah source sebagai bagian review atau menyatakan synthetic
provider sebagai pengujian Auth0 nyata.
