# LMS-05 — development acceptance checklist

11 November2026 WIB; schema0012, base54543a8. Evidence in HANDOFF/performance.json.
Latest follow-up: [FIXES-HANDOFF](LMS-05-FIXES-HANDOFF.md), base84dd193.
Independent4a450d5 review closed F5/F6/F7 Linux in limited synthetic scope;
F9/F10/F11 author fixes await re-review. F12 remains open.

Tests below are author evidence. Current fixes runtime5131f2c; owner now reports
343 PASS/1 capability SKIP/0 deselected and2 browser PASS on Mac. See
[fixes Mac relay](LMS-05-FIXES-MAC-VALIDATION-20261111.md):3 cases not yet reconciled
against347 cloud collection. Original implementation snapshot4a450d5 and its
[earlier Mac relay](LMS-05-MAC-VALIDATION-20261111.md) remain historical.
Independent re-review and manual real-Auth0 UAT remain pending.

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
| F5 publish/legacy |Independent parent CLOSED/functionally CLOSED; new signed-v2 compatibility regression PASS, re-review pending |
| F5 1500×29KB publish plus concurrent writer |Independent parent CLOSED; author regression904.23ms,8 writes200 |
| F6 controls/frame/child PID; F7 Linux cap |Independent parent CLOSED; new dense CPU test separated from OS capability |
| Missing memory capability local WARN vs production503 |Cloud simulated IPC PASS; Mac cap absence reported, original evidence/exclusion needs review |
| All new functions INVOKER; old18 definers/grants unchanged |DB suite/source PASS |
| Upgrade10→12 preserves parent; guarded seeded/offline rollback |Disposable DB PASS |
| Full API /scripts /Action /browser |**347 /12 /16 /17 passed**,0skip; API2 existing warnings; expanded queue suite5 PASS |
| Build/typecheck/compile/pip/starter/diff/audits |PASS; npm0, PyPI41 pins0 findings/errors |
| Mac historical subset |38+2 reported; later reviewer proved excluded test hid a valid-content F9 failure; rerun revised tests |
| Mac Auth0 preflight |Owner reports13 PASS; real login/MFA end-to-end still untested |
| Real Auth0/manual UAT, Docker image, remote CI, multi-worker |NOT TESTED here; manual real-Auth0 UAT not yet performed per owner |
| Independent LMS-05 parent review |APPROVED_WITH_NOTES dev/UAT synthetic small–medium only; F5/F6/F7 scoped CLOSED |
| F9 valid30k /separate Linux assertion /CPU diagnostic |Author Linux PASS; Mac343/1 SKIP/0 deselected reported; exact node IDs/calibration need independent review |
| F10 real HTTP2/4/8 accounts, tenant isolation, student drafts |Cloud36 author+36 student writes200; Mac normal/draft success reported; re-review PENDING |
| F11 date overflow/surrogate422, redaction/valid Unicode |Cloud API/browser PASS; reconcile Mac coverage from original report; re-review PENDING |
| Current Mac count reconciliation |343+1=344 vs347 collected in cloud:3 cases unexplained, not declared failed |
| F12 Draft downtime/key retirement/staff GET budget |OPEN operational notes |
| Full auth parent8941a79..4733526 |PENDING, outside this delta |
| F3, N2/N3/N4, tenant pause |OPEN/unchanged |
| Merge/deploy/runner/grading |Not performed; grading LMS-06 |
