# LMS-05 — development acceptance checklist

11 November2026 WIB; schema0012, base54543a8. Evidence in HANDOFF/performance.json.
Tests below are author evidence; independent review and Mac UAT pending.

| Acceptance | Status |
|---|---|
| Staff assigned course authoring, immutable versions, separate published pointer |API/browser PASS |
| Rubric total100, attempts1–20, languages, aware UTC deadline/WIB UI |API/browser PASS |
| Own draft save/reload, stale tabs, version-change acknowledgment |API/browser PASS |
| Snapshot code/note, server timestamp/late, historical version/rules retained |API/SQL/browser PASS |
| Idempotent retries, concurrent distinct cap across versions |API/SQL PASS |
| Peer/tenant/teacher isolation, forged context/FKs, role/enrollment revoke |API/SQL/browser PASS |
| No UPDATE/DELETE grant; owner immutability trigger; no learner execution |SQL/source/browser PASS |
| Task archive/unpublish history, explicit restore/publish, parent FK preservation |API PASS |
| Existing rate budgets/body bounds, explicit BFF methods/query/Origin |API/browser PASS |
| F5 proof binding/rotation/stale/tamper, explicit legacy batch |API/unit PASS, review pending |
| F5 1500×29KB publish plus other-course writer every0.5s |TCP bench PASS, review pending |
| F6 controls/frame/child PID, F7 dense valid input/cap reporting |Unit/IPC PASS, actual Darwin pending |
| Missing memory capability local WARN vs production503 |Simulated real IPC PASS; native Mac not run |
| All new functions INVOKER; old18 definers/grants unchanged |DB suite/source PASS |
| Upgrade10→12 preserves parent; guarded seeded/offline rollback |Disposable DB PASS |
| Full API /scripts /Action /browser |**325 /12 /16 /17 passed**,0skip; API2 existing deprecation warnings |
| Build/typecheck/compile/pip/starter/diff/audits |PASS; npm0, PyPI41 pins0 findings/errors |
| Real Auth0, native Mac/owner UAT, Docker image, remote CI, multi-worker |NOT TESTED here |
| Independent LMS-05/F5/F6/F7 review |PENDING |
| Full auth parent8941a79..4733526 |PENDING, outside this delta |
| F3, N2/N3/N4, tenant pause |OPEN/unchanged |
| Merge/deploy/runner/grading |Not performed; grading LMS-06 |
