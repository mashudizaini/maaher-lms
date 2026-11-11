# Add versioned assignments, immutable submissions and bounded parser scheduling

Staff can author lesson-bound tasks with immutable exercise versions, rubric,
WIB deadline/late policy and total attempt cap. Saving a draft version preserves
the version students currently see until explicit publish. Enrolled students save
revision-checked drafts and submit immutable snapshots with original rules,
server timestamp/status and idempotency key. RLS/composite FKs restrict peers,
tenants and assigned teachers; submitted source is escaped text and never runs.

Course publish verifies signed saved-content proofs instead of reparsing up to
1500 lessons. Legacy material needs explicit Draft/batched validation. Parser
workers use fixed CPU1000ms/wall3000ms/memory256MiB where supported, finite fair
tenant/account queues, per-account/tenant admission and bounded expiry. Separate
Linux memory assertion permits platform SKIP while dense valid content always
runs; calibration reports host margin without expanding caps. Equivalent signed
v2 proofs remain compatible. Date UTC overflow and lone-surrogate errors return
safe422 without reflecting input/ctx, including parent lessons/student drafts.

Schema0011/0012 preserves identity/material/enrollment/progress. Populated task
rollback requires exact acknowledgment/exclusive guards. The parser/input fixes
on5131f2c add no migration, secret, role or provider policy. Existing write/learning
budgets and BFF Origin/query/body/cookie boundaries remain in force.

Cloud Linux validation on fixes:347 API/parser,12 script,16 Action and17 browser
passed,0skip;2 existing API deprecation warnings. Expanded queue suite5 passed
after adding concurrent student draft coverage. During real TCP2/4/8-actor loads,
36 author saves+36 student drafts all200 (author max4.65s, student max388ms).
Publish1500×29KB904.23ms with8 other-course writes200; setup validation excluded.
Build/typecheck/audits pass (npm0,PyPI41pins0findings). Raw methods FIXES-HANDOFF.

Owner reports Mac5131f2c active, build/restart without migration,343 PASS+1 Linux
capability SKIP,0 deselected and2 browser PASS, with fairness normal/draft saves
successful. The344 reported cases leave3 unreconciled against347 cloud collection;
read the original Mac report/commands/node IDs before declaring full-suite Mac.
Native Mac memory remainsWARN; summary does not verify real Auth0/manual UAT,
remote CI, app image or multi-worker. See FIXES-MAC-VALIDATION-20261111.md.

Stacks on feat/LMS-04-student-learning, initial base54543a8, fixes base84dd193.
Independent parent review4a450d5 APPROVED_WITH_NOTES covers only synthetic
small–medium dev/UAT; F5/F6/F7 Linux scoped CLOSED. F9/F10/F11 author fixes still
await independent re-review. F12, older notes and full auth8941a79..4733526 remain
separate/open. No grading, learner runner, merge/deploy or production approval.
