# LMS-05 — development acceptance checklist

11 November2026 WIB; schema0012, base54543a8. Evidence in HANDOFF/performance.json.
Tests below are author evidence. Owner reports partial Mac automation; see
[LMS-05-MAC-VALIDATION-20261111.md](LMS-05-MAC-VALIDATION-20261111.md).
Independent review and manual real-Auth0 UAT remain pending. Cloud snapshot4a450d5.

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
| F6 controls/frame/child PID, F7 dense valid input/cap reporting |Cloud unit/IPC PASS; native Mac cap unavailable per owner report |
| Missing memory capability local WARN vs production503 |Cloud simulated IPC PASS; Mac cap absence reported, original evidence/exclusion needs review |
| All new functions INVOKER; old18 definers/grants unchanged |DB suite/source PASS |
| Upgrade10→12 preserves parent; guarded seeded/offline rollback |Disposable DB PASS |
| Full API /scripts /Action /browser |**325 /12 /16 /17 passed**,0skip; API2 existing deprecation warnings |
| Build/typecheck/compile/pip/starter/diff/audits |PASS; npm0, PyPI41 pins0 findings/errors |
| Mac partial automated validation |Owner reports38 API/parser +2 browser PASS;1 Linux-specific assertion excluded; not independently reproduced |
| Mac Auth0 preflight |Owner reports13 PASS; real login/MFA end-to-end still untested |
| Real Auth0/manual UAT, Docker image, remote CI, multi-worker |NOT TESTED here; manual real-Auth0 UAT not yet performed per owner |
| Independent LMS-05/F5/F6/F7 review |PENDING |
| Full auth parent8941a79..4733526 |PENDING, outside this delta |
| F3, N2/N3/N4, tenant pause |OPEN/unchanged |
| Merge/deploy/runner/grading |Not performed; grading LMS-06 |
