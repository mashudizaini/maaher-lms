# LMS-01 — checklist setelah review independen Claude

Tahap Auth0/OIDC terbaru ada di [handoff Auth0](LMS-01-AUTH0-HANDOFF.md):
migration 0004, binding identity, session staff dan guard fallback. Provider
disetujui pemilik tetapi tenant live/first-root/recovery belum tersedia.
Checklist historis berikut tidak menyatakan acceptance produksi selesai.

Tambahan cloud 10 November 2026 WIB: **71 API PASS tanpa SKIP**, **5 browser
PASS** setelah dua perbaikan expiry MFA. Build/typecheck, pip check dan audit
dependensi lulus. Lihat [laporan cloud](../reviews/LMS-01-cloud-validation.md).
Hasil di bawah yang menyebut 67 tes merekam validasi Mac/Linux sebelumnya;
review ulang Claude dan acceptance produksi tetap belum selesai.

**BELUM SELESAI untuk penggunaan nyata.** Perbaikan kode lokal dan regresi sudah
lulus; provider trust/operator MFA produksi, kebijakan retensi operasional,
ingress/TLS/SMTP nyata dan review ulang masih menjadi gate. Laporan Claude
asli dipertahankan, statusnya CHANGES_REQUESTED; belum ada persetujuan reviewer.

Sumber acceptance: PROJECT-SPEC LMS-01, ARCHITECTURE auth/tenant contract.
Keputusan terkini: [ADR-002](adr/002-auth-security-review.md). Respons lengkap:
[author response](../reviews/LMS-01-author-response.md). Perintah/data uji:
[handoff](LMS-01-HANDOFF.md).

Hasil final: **67 PASS Mac/Python 3.13.5**, **67 PASS Linux/Python 3.12**,
**5 PASS browser Chrome**. Tanpa SKIP. API = 2 unit + 1 health + 64 kasus
integrasi; 31 kasus regresi baru berada pada
[`test_review_regressions.py`](../apps/api/tests/test_review_regressions.py).
Fixture migrasi bersama berada pada `tests/conftest.py`; helper proof operator
hanya memakai database/credential sintetis dan bukan bypass produksi.

| Checklist | Status saat ini | Bukti file dan tes |
|---|---|---|
| [x] Session/login/logout | Implementasi + diuji | `auth.py`, `database.py`; suite identity cookie/Origin/expiry/logout/restart. Password benar tidak diveto failure counter; session MFA tidak diusir pool password-only. |
| [x] COMMIT sebelum respons/cookie | Implementasi + diuji uvicorn nyata | Semua yield DB dependency `scope='function'`; `test_m1_real_uvicorn_does_not_send_headers_or_cookie_until_commit` memakai barrier dan observer DB. Failure login/logout wajib **503**, tanpa cookie sukses; rollback dan request berikutnya pada client sama diperiksa. |
| [x] Invitation | Implementasi + diuji | `auth_lifecycle.py`, fungsi 0003 `accept_invitation`: once/expiry/revocation/concurrency/existing owner. Stale cookie tidak menghalangi akun baru, tidak menjadi bukti akun lama (`test_l1_*`). Admin baru tetap tidak mendapat akses sebelum MFA bertrust. |
| [x] Password reset | Implementasi + diuji | Respons generik, TTL satu jam, token satu kali, password policy, reset mencabut session. Reset/email tidak memberikan hak enrollment MFA (`test_h1_password_and_compromised_email_cannot_bootstrap_mfa`). |
| [x] Membership/role/penemuan anggota | Implementasi + diuji API dan browser | `list_members`, `change_member`, endpoint tenant-members berpagination; role/revoke berdasarkan email anggota di UI. `test_l6_*` memeriksa crosstenant, promosi/demosi pada session aktif, self-protection, pagination tanpa gap; browser workflow anggota lulus. |
| [x] Audit auth/tenant/operator | Implementasi + diuji | Audit actor/action/target, auth history private; audit operator tetap ada setelah recovery session dicabut. SQL runtime ditolak UPDATE/DELETE audit. Tidak mencatat token/password/kode/URI. Audit DDL/aktivitas host bukan klaim aplikasi. |
| [x] Isolasi tenant | Implementasi + diuji SQL langsung | RLS berasal dari capability session valid, bukan GUC userid palsu; `test_m4_forged_gucs_*`, read/write/object-ID negatif dalam identity suite. Role/tenant/membership aktif diperiksa ulang. |
| [x] Pencabutan akses | Implementasi + diuji | Revoke satu tenant, role berubah, user/tenant disabled, expiry/reset/recovery. Akses tenant lain dipertahankan; undangan tidak reaktivasi revoke. |
| [x] Hak runtime minimum | Implementasi + diuji role aktual | `test_m4_runtime_actual_login_*` (9 kasus) sebagai LOGIN maaher_api: SELECT hash/users/session/faktor, INSERT session true/false dan fungsi auth sensitif ditolak. AUTH_DATABASE_URL terpisah, bukan fallback runtime/owner. |
| [x] Pemilik SECURITY DEFINER | Implementasi + diuji | 9 fungsi NOLOGIN maaher_definer, non-superuser, fixed search_path pg_catalog/public/pg_temp, no PUBLIC EXECUTE. Definer tidak SELECT password hash/secret MFA, INSERT session atau CREATE schema (`test_m6_*`). |
| [x] Bootstrap MFA melawan password/email curian | Implementasi fail-closed + diuji | Request tanpa authority, grant sekali pakai terikat session melalui role operator independen. `test_h1_*` menolak password/reset email/authorization dari session lain/replay/boolean produksi. Faktor 0002 tidak dianggap trusted. |
| [x] Recovery pemilik sah | Implementasi sintetis + diuji API/browser | Proof operator independen, konfirmasi faktor baru, password baru, revoke semua session/reset token; faktor lama tidak dihapus sebelum konfirmasi. Recovery yang diotorisasi tidak dievikt password holder. Bukan layanan recovery produksi yang sudah diaktifkan. |
| [x] MFA admin dan metadata | Implementasi + diuji | Admin/confirmed-factor user memerlukan elevasi untuk tenant, memberships, security-events, acceptance akun lama dan logout. Login baru belum ter-MFA; replay ditolak. Kuota OTP bertahan lintas login dari IP penyerang; network pemilik dan proof recovery terpisah. |
| [x] Biaya/state endpoint anonim | Implementasi + diuji | Pre-Argon global/per-network budget; empat password slots lintas worker; keyspace counter tetap. Probe 40 login + 40 reset random tidak memperbanyak auth events NULL/login_attempts dan dibatasi sebelum hashing (`test_m2_*`). |
| [x] Retensi sensitif | Implementasi + kebijakan sintetis diuji | Dedicated maintenance role/function: expired sessions/tokens/requests, counters, audit horizons, invitation/outbox. Test membuktikan data expired hilang tetapi identity/membership/live session tetap. Belum dijalankan pada database pengguna. |
| [x] Poison outbox + PII purge | Implementasi + diuji | InvalidToken/format dikarantina satu kali, pesan valid tetap terkirim via callback; token/alamat scrub sent/dead/expired. Worker menolak role owner/API. Maksimal lima retry dalam TTL, interval 10 menit (`test_m5_*`, `test_l3_*`). |
| [x] Rotasi key | Implementasi + diuji sintetis | Versioned MultiFernet; rotate factor/pending/outbox atomik, key baru-only tetap valid, satu ciphertext rusak rollback seluruh rotasi (`test_l2_*`). Produksi tetap menunggu operator trust/backup gate. |
| [x] UI/BFF/CSP/header | Implementasi + 5 tes browser lulus | Alur login→operator proof→MFA→invite/accept→reset; recovery owner; penemuan/ubah peran/revoke. CSP nonce per response tanpa unsafe-inline/eval produksi, parser-injected script ditolak, headers seluruh route. HSTS HTTP loopback bukan bukti TLS publik. |
| [x] CI least privilege/config | Diubah + policy lokal diperiksa | contents:read, actions pin SHA resmi, PostgreSQL, browser dan audit jobs. GitHub Actions **belum dijalankan** dalam sesi ini. |
| [x] Migrasi/rollback | Diuji pada kedua platform | 0001→head, head→0002→head, head→0001→head, base→head; identity tahap 1 dipertahankan; 15 tabel aplikasi diperiksa hilang setelah base. Perbaikan rollback 0001 tetap ada. |
| [ ] Trust bootstrap/operator produksi | Keputusan/config eksternal belum tersedia | Adapter SQL/CLI menolak non-test/produksi. Perlu root operator MFA independen, verifikasi identitas/perangkat di luar email login/reset, proses emergency/revocation/audit. Jangan mengakali dengan boolean atau rename DB. |
| [ ] Full account recovery tanpa password maupun email | Belum diimplementasikan; bergantung root trust independen | Recovery faktor yang lulus tes masih membutuhkan session password-valid. Kehilangan seluruh credential memerlukan provider/verifikasi perangkat terdaftar yang disetujui sebelum menerbitkan konteks recovery. H1 tidak dinyatakan CLOSED end-to-end. |
| [ ] SMTP/inbox nyata | Konfigurasi dan UAT eksternal | SMTP account/domain/SPF/DKIM/DMARC/TLS egress/scheduler/monitoring. Tidak ada pesan nyata dikirim. |
| [ ] Retensi/ingress operasional | Kebijakan/config eksternal | Horizon sintetis perlu keputusan legal/retensi, scheduler/monitoring/hold. Proxy harus overwrite IP dan edge key; BFF/API secret berbeda; edge rate limit/load test. Produksi menolak ingress tak tepercaya; routing nyata belum diuji. |
| [ ] Review ulang/backup/TLS/human approval | Belum selesai | Claude perlu memeriksa source/diff terbaru dan response. Laporan lama bukan approval perbaikan ini; backup/restore drill dan persetujuan manusia tetap diperlukan. |

Dependency locks dipertahankan: 34 pin runtime/42 dev, package-lock web.
Audit ulang: PyPI 34 pin, 0 findings/errors; npm produksi 0 vulnerability.
Ini snapshot advisori, bukan jaminan keamanan OS/OpenSSL/deployment.
Tidak ada apply ulang patch historis, penghapusan DB/container lama, data
pengguna yang dimigrasi/dibersihkan, commit, merge atau deploy.
