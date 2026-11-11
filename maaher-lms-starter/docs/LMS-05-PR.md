# Add versioned assignments and immutable student submissions

Teachers/admins can author rubric/deadline/attempt rules as immutable exercise
versions. Saving a new draft version preserves the current published version;
only explicit publish changes what students see. Enrolled students save revision-
checked drafts and submit immutable snapshots with version, server timestamp,
late status and an idempotency key. Peer/tenant access is denied; staff read only
submissions in authorized courses. Learner code is stored as escaped text.

LMS-04 residual F5 is addressed with signed saved-content proofs, so publish
verifies rather than reparses up to1500 lessons. Legacy material needs explicit
Draft/batched validation on a separate lane. Controls reject422 before IPC; cap
reporting distinguishes unsupported native Mac memory limits and fails closed
outside local/test. CPU250ms/wall2s and bounded process pools remain overload limits.

Schema0011/0012 preserves existing identity/material/enrollment/progress, adds no
secret/role/definer privilege, and guards destructive task-history downgrade with
an exact acknowledgment and exclusive locks. Seeded migration and offline SQL
are tested only on disposable DBs. Existing budgets/BFF boundaries remain.

Validation:325 API/12 script/16 Action/17 browser cases passed,0skip; API2 existing
deprecation warnings. Real TCP publish1500×29KB757.63ms with eight other-course
writes all200; health CPU-load p95/8 writers8.18ms. Build/typecheck/audits pass
(npm0,PyPI41pins0findings). Methods/counts in LMS-05-HANDOFF.md.
Synthetic Linux results are not Mac manual UAT, real Auth0, CI, image or multi-worker
approval. Independent Claude review F5/F6/F7 and LMS-05 remains pending.

Owner subsequently reports38 API/parser and2 browser cases passed on Mac, plus
Auth0 preflight13 PASS. One Linux-specific assertion was explicitly excluded;
native Mac memory cap remains unavailable. Browser provider is synthetic; manual
real-Auth0 UAT is not yet performed. Original report and actual source/schema/
commands/exclusion must be inspected independently; this is not a full-suite Mac
or production approval. See LMS-05-MAC-VALIDATION-20261111.md.

This PR stacks on feat/LMS-04-student-learning (base54543a8). Main still includes
unmerged auth and earlier milestones; full auth review8941a79..4733526 is separate.
F3/N2/N3/N4/tenant-pause remain open. No grading, runner, merge or deploy approval.


Follow-up to independent4a450d5 review: parent F5/F6/F7 closed in limited scope.
Author fixes for F9/F10/F11 use CPU1000ms/wall3000ms, separate OS memory assertion,
finite fair tenant/account queues, compatible signedv2 proofs and safe422 input
errors.347 API/parser,12 scripts,16 Action,17 browser passed; expanded real HTTP
probe adds36 author saves+36 student drafts all200 during2/4/8-actor pressure.
Queues trade immediate global429 for bounded waiting (author max4.65s in probe),
not unlimited capacity. No schema/backfill/config changes. Details FIXES-HANDOFF;
Mac slow-host rerun and independent re-review pending. F12/old notes/auth unchanged.
