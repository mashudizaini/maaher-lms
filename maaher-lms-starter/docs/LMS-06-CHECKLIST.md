# LMS-06 — author acceptance checklist

11 November 2026, Asia/Jakarta. Base13408bb; schema0013_grading.
Evidence: [handoff](LMS-06-HANDOFF.md), [verification JSON](../reviews/LMS-06-verification.json).
Statuses below are AUTHOR validation, not independent approval.

| Acceptance | Status |
|---|---|
| Original submitted rubric, integer scores0..max, server-derived total |API/SQL/browser PASS |
| Private draft, explicit release, hidden correction, reasoned withdrawal |API/SQL/browser PASS |
| Student publication only; no private root/revisions/events even through SQL |API/SQL PASS |
| Tenant/peer/teacher assignment/enrollment/course lifecycle isolation |API/SQL/browser PASS |
| Revision/event immutability, audit order, forged actor/time/total normalization |SQL PASS |
| Stale version and concurrent draft/release/withdraw do not expose new draft |API/SQL race PASS |
| Revoked teacher authority checked before/after waiting on root lock |API/raw SQL PASS |
| Zero score, Unicode/plain text, input bounds, original source unchanged |API/SQL/browser PASS |
| BFF method/query/Origin/body/cookie boundaries;409/429 editor preservation |API/browser PASS |
| Staff GET180/min, shared POST60/min, student120/min, restricted counter retention |API/SQL PASS |
| INVOKER new functions; old18 definer definitions/grants unchanged |Migration/source PASS |
| Seeded parent hashes preserved, offline/guarded rollback, re-upgrade |Disposable DB PASS |
| Full API/parser suite |378 PASS,0 SKIP;2 existing warnings |
| Supplemental race/authority run |4 PASS:2 new and2 repeated cases |
| Final collection /unique executed cases |380 /380 across runs; no single full380 run |
| Scripts /Actions /browser |12 /16 /19 PASS |
| Next build/typecheck, compile, pip/starter, audits |PASS; npm0,PyPI41 pins0 findings/errors |
| Mac install/forward migration/manual UAT |PENDING; no direct cloud access to Mac |
| Independent LMS-06 review |PENDING |
| Real Auth0/FIDO2, remote CI, app Docker image, multi-worker |NOT TESTED here |
| Parser capacity/slow-host calibration notes, F12, F3, parent N2/N3/N4, tenant pause |OPEN/separate |
| Full auth parent8941a79..4733526 |PENDING/separate |
| Merge/deploy/production approval/learner execution |Not performed |
