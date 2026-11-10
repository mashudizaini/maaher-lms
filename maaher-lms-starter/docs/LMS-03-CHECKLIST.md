# LMS-03 — checklist development

Source base fe54142; branch feat/LMS-03-enrollment. Head schema 0008_enrollment.
Validasi final: **272 API, 12 scripts, 16 Action, 13 browser**, 0 skip,
build/typecheck/audit PASS. Bukti cloud dan command detail pada LMS-03-HANDOFF.md; belum UAT Mac/review Claude.

| Item | Status |
|---|---|
| Admin cohort create/rename/archive/restore | API/browser PASS |
| Enrollment unique, move, revoke, reactivate, version conflict | API/concurrency/browser PASS |
| Role/status/archive tidak menghidupkan kembali enrollment | API/SQL/browser PASS |
| Unpublish/draft menjeda read sampai republish | API PASS |
| Siswa sendiri, tanpa peer cohort/roster | RLS/API PASS |
| Teacher hanya assigned active roster, tanpa mutasi | API PASS, Auth0 guru nyata NOT TESTED |
| Tenant/parent/FK/context palsu/immutable grants | PostgreSQL PASS; scoping sebelum lock diuji tambahan pada final suite |
| Seeded upgrade, guard populated rollback, preservasi auth/course | Fixture DB baru PASS |
| ASGI stream cap/replay/disconnect, tanpa request._body | Unit + full API/browser PASS |
| Parser worker dan health concurrent | PASS; biaya kuadratik CPU tetap terbuka |
| BFF Origin/body/path/query/cookie/header | Browser PASS |
| Build/typecheck/dependency audit | PASS |
| CI remote / Docker application image | UNVERIFIED |
| Auth0 nyata, real staff/student UAT | NOT TESTED cloud |
| UAT Mac LMS-03 / independent review LMS-03 | PENDING |
| Full independent auth parent review | PENDING; LMS-02 verdict hanya delta kursus fe54142 |
| Merge/deploy | Tidak dilakukan |

LMS-02 APPROVED_WITH_NOTES dilaporkan pemilik, dengan delapan LOW lama (tujuh
FIXED oleh reviewer, request._body OPEN pada fe54142). ASGI/perubahan worker
baru belum diberi status CLOSED independen. N2 offline0006, N3 Unicode tambahan/
NAT64 dan N4 trace cleanup historis tetap OPEN; lihat relay re-review.
LMS-04 completion/progress, LMS-05/06 grading dan runner tidak termasuk.
