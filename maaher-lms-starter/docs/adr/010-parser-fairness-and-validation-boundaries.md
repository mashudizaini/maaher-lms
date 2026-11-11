# ADR-010 — bounded fair parser scheduling and validation boundaries

Latest independent result: re-review5131f2c reported APPROVED_WITH_NOTES for
synthetic dev/UAT, F9/F11 CLOSED and F10 CLOSED_WITH_NOTES. Remaining calibration,
linear queue wait and saturation notes are recorded in the
[AUTHOR relay](../../reviews/LMS-05-claude-rereview-relay-20261111.md).
Pending-review wording below describes the original implementation handoff.

11 November 2026 WIB. Follow-up F9/F10 MEDIUM and F11 LOW on4a450d5; base84dd193
(documentation only). No schema, DB role, provider or learner execution change.
Implementation evidence is author evidence; independent re-review still pending.

## CPU budget and platform-specific assertions (F9)

The250ms ceiling was too close to a valid30k dense document: reviewer measured
266ms median on i5-7360U/Docker. Raising it from120ms had not established a robust
slow-host margin; deselecting a combined capability/content test hid that failure.
The hard budget is now1000ms CPU,3000ms wall in markdown_budget.py, not an unbounded
or environment-controlled timeout. This gives about3.75× the reviewer's median,
not a universal guarantee that all valid Markdown runs on arbitrary hardware.
CPU exhaustion still rejects422; wall/crash/memory capability failures remain503.

`parser-preflight.py --calibrate` measures five uncached dense valid30k parses in
each fixed worker, reports process CPU samples/median and margin to the slowest
sample. It does not adjust/disable caps. A margin below2 is WARN_LOW_MARGIN, not
PASS evidence for that host. CPU-bound test-only loop still verifies the actual
SIGPROF timer, independent of hardware speed; HTTP pressure uses real CommonMark.

The Linux-only RLIMIT_AS assertion is now a separate skipif(sys.platform!='linux')
test. Control/frame, valid repeated dense documents, timeout and simulated missing
cap behavior continue on Mac. No whole-test --deselect. Native Mac missing cap
remains local/test WARN; non-local failure remains enforced. Resource profiles
are separate from content semantics. New proofs use semantic v3-controls ID and
explicitly accept the already-signed v2-controls-cpu250 ID because URL/Markdown/
control rules are identical. No unknown/unsigned proof is trusted. Existing v2
lessons/tasks do not require downtime or new versions just for this budget change.
Retiring encryption keys still has the original operational consequences.

## Scheduling and finite capacity (F10)

Previously a free-slot race on two global workers gave unrelated users429 while
one or two actors kept them occupied. The service now enqueues validated tenant:
user scopes, with one running-or-waiting job per account per lane. A second
concurrent request from that account gets its own429/Retry-After1. Accounts cannot
place a long series of pending jobs ahead of peers.

There are still two interactive child processes and one independent maintenance
child per API process, with a fixed dispatcher thread per child. They start
lazily. No process/thread/cache is created per tenant. Tenant queues use FIFO for
accounts and choose a tenant with the least active jobs; stable equal-count ties
rotate. Completion releases admission bookkeeping before waking the requester,
so the next sequential save cannot race its own previous reservation.

Per lane: max16 pending, one job/account, max10 in-flight per tenant. One tenant
therefore cannot consume the whole global queue. Tenant saturation returns429;
global capacity exhaustion returns503/Retry-After1. Pending admission expires
within8s; child exchange is bounded3s; caller's total wait is bounded about11.2s,
below the existing15s BFF timeout, excluding unrelated DB/network contention.
Expired/cancelled entries free scope/capacity; shutdown rejects queued jobs,
finishes bounded active work, and closes child pipes/processes. These limits
remain finite overload behavior, not immunity to arbitrarily many authenticated
attackers or insufficient CPU. Multi-worker/process-total sizing remains unverified.

The maximum parser calls occupying the default synchronous API threadpool is
18 interactive+17 maintenance=35, below its unchanged40-thread default; queues do
not grow unboundedly. This assumes the existing threadpool configuration. The
scheduler releases the GIL while waiting. Only trusted library parsing runs in
children; source code submitted by learners never runs or enters this parser.
Children still receive no DB/Auth0/keyring credentials, only bounded IPC text.

Scope comes only from principal-validated actor.tenant_id/user_id, never body or
unvalidated header. Existing DB budgets60 staff writes/120 learning requests per
minute still apply before parsing. The scheduler's admission is process-local,
not a new cross-worker quota. All RLS, transaction-before-send and write-version
checks remain in force after waiting. Repeated future/queue work cannot mint
sessions or broaden tenant/course access.

## Safe user errors (F11)

An offset near Python datetime's year boundary can overflow astimezone(UTC).
The input validator converts this to ValueError, yielding422 before any version
is appended. Naive datetimes remain rejected. Ordinary UTC/WIB behavior is unchanged.

Rejecting a lone surrogate with Pydantic was insufficient: its default error
response included the invalid input, whose UTF8 encoding then failed. A global
RequestValidationError handler emits at most20 errors, bounded type/loc/msg text
normalized to valid UTF8, without input or ctx. This also fixes the parent lesson
path and avoids reflecting password/source contents. Auth logic is unchanged;
common auth error serialization is included in regression scope. Valid Unicode
and valid escaped surrogate pairs are still accepted. BFF forwards these safe
422 responses without re-encoding invalid source data.

## Evidence and residuals

Full Linux suite347 passed; later queue suite5 passed after expanding HTTP probes
to add simultaneous student drafts. Real opaque sessions/memberships/teacher
assignments in new disposable PostgreSQL DBs, one uvicorn worker/TCP,2/4/8 actors
per scenario, max1 request/s/actor and original account budgets. Both same-tenant
and different-tenant cases measure six distinct uncached author saves and six
student drafts while all attacker loops remain active. Events coordinate load
start/stop or unit ordering only; actual HTTP CPU work is the real parser.

All36 author saves and36 student drafts returned200; attackers' invalid Markdown
returned422. Max author latency4648.78ms, max student387.81ms, health p95 worst9.71ms
in expanded probe. Queuing exchanges fast429 for bounded waiting; do not present
it as instant saves under load or a production SLO. Full JSON, sample counts,
calibration metadata and methods are in LMS-05-fixes-performance.json.

F5 publish/legacy, F6 and F7 Linux were CLOSED by the relayed independent review;
these fixes are not independently CLOSED yet. F12 Draft downtime/key retirement/
staff GET budget remains open, along with F3/N2/N3/N4/tenant pause and separate
auth-parent review. No new migration/backfill/secret or learner runner. No merge,
deploy, manual owner UAT, real Auth0, app-image, remote CI or multi-worker claim.
