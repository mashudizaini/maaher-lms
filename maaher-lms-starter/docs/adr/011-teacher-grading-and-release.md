# ADR-011 — private grading revisions and explicit disclosure

11 November 2026, Asia/Jakarta. LMS-06, base13408bb, schema0013_grading.
LMS-05 re-review closes F9/F11 and F10 with capacity notes for synthetic dev/UAT;
[relay](../../reviews/LMS-05-claude-rereview-relay-20261111.md). This ADR is an
implementation decision, not independent approval of grading or auth.

## Grade the original submission

An admin or teacher currently assigned to the course grades an immutable
submission against its original assignment-version rubric. Each criterion has
an integer score0..maximum and optional plain-text comment; DB derives the total
0..100. A later published task version cannot replace the submitted rubric.
No submitted source executes. Grades do not automatically complete lessons or
combine multiple attempts into a course result.

`grading_entries` is the private per-submission state/version. `grade_revisions`
stores immutable rubric scores, feedback, private reason and reviewer/time.
`grading_events` stores immutable transition history. `grade_publications` is a
separate disclosure-only snapshot: state, revision reference, scores, total,
feedback and publication time; no private reason, actor or draft fields.
`grading_read_limits` holds committed staff GET counters.

Saving a draft creates a revision without disclosing it. Initial release is
explicit. After release, draft corrections require a private reason and leave
the previous publication visible until explicitly released. Withdrawal requires
a reason and clears all public grade payload fields, retaining private history.
Students receive ungraded/grade:null before first release and withdrawn/grade:null
after withdrawal; they cannot infer private draft existence from that response.
At most100 revisions and300 state transitions per submission; histories paginate.
Zero is a valid score. Feedback/comments are escaped plain text, not Markdown.

## Database and access boundaries

All five tables FORCE RLS; composite parent keys bind tenant/course/submission.
Runtime SQL students cannot SELECT entries, revisions or events, including the
revision behind a released snapshot. Publication SELECT additionally depends on
their own visible submission through parent active enrollment/published-course
RLS. Peers and other tenants remain invisible. Assigned teachers lose access
after assignment/role/membership revocation; admins retain archive read access,
but archive blocks all grading mutations. Task archive retains submission history.

New functions are INVOKER with fixed search_path and PUBLIC execution revoked;
no new SECURITY DEFINER or role. Existing18 definer bodies/ACLs do not expand.
Runtime/owner cannot UPDATE/DELETE immutable revisions/events; runtime has no
TRUNCATE grant. As with the parent, this protects ordinary DML, not a malicious
database administrator capable of disabling triggers or changing schema.

Revision triggers validate rubric/index/score shape independently of API,
canonicalize scores, compute total and override reviewer/time. Inserting a valid
revision advances its root atomically. Root version changes generate the audit
event and public snapshot in the same transaction. Publication/event triggers
derive payloads from root/revision and reject independent spoofed transitions.
Private reasons stay in private tables; generic audit events record action and
submission target without feedback/reason text.

Each API mutation locks the submission's grading root and checks optimistic
version. SQL authority is checked before and after lock acquisition. The
PL/pgSQL VOLATILE authority check uses a fresh READ COMMITTED snapshot after a
wait, so a teacher revoked while waiting cannot grade with cached authority.
Stale versions return409 without silently merging edits. No new lock timeout
is introduced; operational DB wait limits remain a separate consideration.

## HTTP and UI

`/grading` provides staff queue/detail/history/draft/release/withdraw; student
`/work/submissions/{id}/grade` exposes only their current publication. Queries
are bounded and fields explicit. Staff grading GET has180/min per tenant/user;
POST shares the existing course60/min budget. Student grade GET shares work
120/min. Committed counters survive rejected requests. Maintenance can read only
expired counter timestamps/delete expired rows, without reading grades; existing
local/test-only retention invokes that direct cleanup, no definer expansion.
This does not approve a production retention scheduler or budget all parent GETs.

Next BFF explicitly allows grading paths/methods/query fields, retains exact
Origin checks,256KiB body bound, restricted cookie/header forwarding and
Retry-After without upstream Set-Cookie. Teacher editor preserves unsaved scores
on409/429. Student page fetches publication separately from immutable submission
snapshot and clears displayed protected data after authorization failure.

## Migration and operational limits

Forward0012→0013 adds empty grade tables/functions/indexes and a submission
composite unique constraint; preserves parent identity, material, enrollment,
progress, drafts and submissions. No new credential, dependency, Auth0 policy or
global role is needed. Use migration ownership, never elevate the API account.

Downgrade exclusively locks all grading tables. Populated grade history requires
the exact `-x allow_grading_data_loss=yes`; wrong/no flags and downgrade-base fail
before deletion. Offline SQL includes the same guard. Acknowledged downgrade
destroys grades/history, not parent submissions; re-upgrade cannot recover them.
Generic audit events deliberately remain. Only disposable review DBs were rolled
back; owner setup uses backup and forward upgrade only.

Author tests cover SQL isolation, trigger spoofing, audit, score validation,
concurrency, revocation during lock wait and seeded/offline rollback, plus two
browser profiles. Full author evidence is in [handoff](../LMS-06-HANDOFF.md).
Independent grading review, Mac UAT, real Auth0, remote CI, app image and
multi-worker remain pending. Parser queues/slow-host margins, F12, F3, parent
N2/N3/N4, tenant pause and full auth review remain separate. No production SLO,
grade scale benchmark or automated grader is claimed.
