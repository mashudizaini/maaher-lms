# LMS-02 — status development dan review

Source code yang diuji: **f38c231**. Laporan Mac/manual dari pemilik direkam pada
[UAT development](LMS-02-DEV-UAT-20261110.md). Dokumen ini membedakan bukti
otomatis, laporan manual dan pekerjaan yang masih pending.

| Item | Bukti/status |
|---|---|
| Course/module/lesson persistence, reload | Otomatis PASS; UAT utama Mac dilaporkan berhasil |
| Publish, edit kembali Draft | Otomatis PASS; UAT utama Mac dilaporkan berhasil |
| Archive/restore dengan materi utuh | Otomatis PASS; UAT utama Mac dilaporkan berhasil |
| Logout | Otomatis PASS; UAT utama Mac dilaporkan berhasil; hitungan session manual tidak diberikan |
| Assignment/revoke guru, role/membership | Otomatis PASS; UAT manual khusus belum dirinci |
| Tenant isolation, FK, forged context, least privilege | Otomatis PostgreSQL PASS; review independen masih pending |
| Version conflict, publish atomicity, caps | Otomatis PASS; UAT manual khusus belum dirinci |
| Markdown/XSS, HTTPS resources, body/Origin/query | Otomatis API/browser PASS; review independen masih pending |
| Migrasi 0006, auth dipertahankan | Cloud roundtrip PASS; Mac backup/upgrade dilaporkan berhasil |
| Build/typecheck/npm audit | Cloud PASS; Mac build ulang dilaporkan berhasil |
| Auth0 local preflight | Mac 13 PASS menurut CLI; tidak mencakup seluruh setting provider |
| Review Claude untuk LMS-02 | **PENDING**, belum ada reviews/LMS-02-claude.md |
| Review auth parent terbaru | **PENDING**, laporan auth lama tetap CHANGES_REQUESTED dan bukan review source Auth0 terbaru |
| GitHub CI remote | **UNVERIFIED**, konfigurasi CI tersedia; belum ada bukti hasil remote |
| Diagnostic flag setelah UAT | Belum dilaporkan; cleanup lokal dibahas pada panduan Mac |
| Merge / deploy | Tidak dilakukan |

Alur utama LMS-02 **lulus UAT development menurut pemilik**. Enrollment/cohort
LMS-03, belajar siswa LMS-04, grading dan runner merupakan scope terpisah.
Sumber perintah, schema, batas dan risiko downgrade: [handoff](LMS-02-HANDOFF.md).
Review request siap dipakai pada [reviews](../reviews/LMS-02-review-request.md).
