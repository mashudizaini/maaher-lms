# LMS-04 — checklist development

Base4870287; head schema0010_learning_progress. Bukti rinci LMS-04-HANDOFF.md.

| Item | Status |
|---|---|
| Student complete/uncomplete idempotent, reload/restart | API/browser PASS |
| Next/previous, resume, course count | API/browser PASS |
| Material revision invalidates; title only preserves | API/browser PASS |
| Own enrollment/tenant/revision/FK, no peer/admin writes | RLS/API PASS |
| Revoke/archive/draft/membership revalidation | Parent/API/browser PASS |
| F1 maximum1500 lessons/451 catalog, InitPlan/prepared revoke | Bench/API/SQL PASS, re-review pending |
| F2 actual CPU load2/8/1, original budget60, child crash/timeout | Bench/HTTP/unit PASS, re-review pending |
| Reader grants minimal, NOLOGIN/NOBYPASS, not assumable | PostgreSQL PASS |
| Seeded upgrade/guarded downgrade/offline0010 | Migration fixture PASS |
| Full regression | **291 API, 12 scripts, 16 Action, 15 browser**, 0 skip |
| Build/typecheck/compile/pip check, npm/PyPI audit | PASS, 0 findings/errors on audits |
| Mac UAT / real Auth0 / Docker image / remote CI | PENDING/UNVERIFIED |
| Independent review F1/F2 + LMS-04 | PENDING |
| Full auth parent review | PENDING |
| N2/N3/N4, old definer LOW, tenant pause | OPEN/unchanged scope |
| Merge/deploy/runner | Tidak dilakukan |

Approval tidak disimpulkan dari tes author atau dari laporan LMS-02. Scope belajar
ini self-report completion, bukan grading/analytics guru/sertifikat/pembayaran.
