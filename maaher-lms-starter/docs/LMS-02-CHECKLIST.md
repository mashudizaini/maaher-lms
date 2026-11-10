# LMS-02 — status development dan review

Source awal yang UAT Mac: **f38c231**. Laporan Mac/manual dari pemilik direkam pada
[UAT development](LMS-02-DEV-UAT-20261110.md). Dokumen ini membedakan bukti
otomatis, laporan manual dan pekerjaan yang masih pending. Delta review setelah
base **f4f9cf7** menambah head **0007_course_review**; UAT/re-review delta pending.

| Item | Bukti/status |
|---|---|
| Course/module/lesson persistence, reload | Otomatis PASS; UAT utama Mac dilaporkan berhasil |
| Publish, edit kembali Draft | Otomatis PASS; UAT utama Mac dilaporkan berhasil |
| Archive/restore dengan materi utuh | Otomatis PASS; UAT utama Mac dilaporkan berhasil |
| Logout | Otomatis PASS; UAT utama Mac dilaporkan berhasil; hitungan session manual tidak diberikan |
| Assignment/revoke guru, role/membership | Regresi published/role cycle/race SQL PASS; UAT delta pending |
| Arsip guru, parent/child SQL RLS | Regresi API/SQL PASS; admin restore tetap tersedia |
| Tenant isolation, FK, forged context, least privilege | Otomatis PostgreSQL PASS; review awal terarah dilaporkan; re-review delta pending |
| Version conflict, publish atomicity, caps | Otomatis PASS; UAT manual khusus belum dirinci |
| Markdown/XSS, HTTPS resources, body/Origin/query | Parser server/Unicode/legacy publish dan browser PASS; re-review pending |
| Detail field eksplisit dan budget course writes | API/concurrency/RLS/retensi PASS; browser 429/Retry-After/editor PASS |
| Migrasi 0006→0007, auth/materi dipertahankan | Cloud seeded upgrade/roundtrip/guard rollback PASS; Mac delta pending |
| Build/typecheck/npm audit | Cloud PASS; Mac build ulang dilaporkan berhasil |
| Auth0 local preflight | Mac 13 PASS menurut CLI; tidak mencakup seluruh setting provider |
| Review Claude awal untuk LMS-02 | Dilaporkan pemilik: tujuh LOW, tanpa BLOCKER/HIGH/MEDIUM; file/verdict formal belum tersedia cloud |
| Respons/re-review LOW | Ketujuh diimplementasikan/diuji author; **RE-REVIEW PENDING** |
| Review auth parent terbaru | **PENDING**, laporan auth lama tetap CHANGES_REQUESTED dan bukan review source Auth0 terbaru |
| GitHub CI remote | **UNVERIFIED**, konfigurasi CI tersedia; belum ada bukti hasil remote |
| Diagnostic flag setelah UAT | Belum dilaporkan; cleanup lokal dibahas pada panduan Mac |
| Merge / deploy | Tidak dilakukan |

Alur utama LMS-02 **lulus UAT development menurut pemilik**. Enrollment/cohort
LMS-03, belajar siswa LMS-04, grading dan runner merupakan scope terpisah.
Validasi delta cloud: **244 API, 12 scripts, 16 Action, 11 browser**, tanpa skip;
build/typecheck, npm0, PyPI41pins0. Detail perintah dan hasil pada handoff.
Sumber perintah, schema, batas dan risiko downgrade: [handoff](LMS-02-HANDOFF.md).
Review request siap dipakai pada [reviews](../reviews/LMS-02-review-request.md).
