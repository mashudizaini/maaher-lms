# ADR-009 — assignment versions, submission snapshots and publish validation

Accepted for local synthetic development, 11 November 2026 WIB; independent
review and Mac UAT pending. Base54543a8, schema0011/0012. No learner runner.

## Content validation and LMS-04 residuals

F5 arose because publish reparsed up to1500 lessons through one global slot.
We persist a Fernet proof using the existing maintained keyring. The authenticated
payload is a domain-separated SHA256 digest of policy ID, kind, tenant/object/
revision and exact UTF8 content plus canonical JSON resources. No raw material,
password or login token is stored in the proof. Lesson INSERT/edit validates
first, signs the stored revision, then conditionally stores the proof against
that exact revision/content/resources. The DB invalidates the proof on content/
resource changes. Copying a proof to another object or changing revision fails.

Publish streams rows20 at a time, verifies proofs, and performs no parser work.
A missing, invalid, obsolete-policy or retired-key proof returns409, preserving
state/version. Previously published legacy material remains available; migration
never retroactively certifies it or silently unpublishes a course. To re-publish
unsigned material, staff explicitly makes the course Draft and runs Periksa
materi lama. Each request checks at most50 rows, stops after approximately2s
plus at most one bounded parse, and returns its cursor. The course version is
locked; a concurrent direct row change fails the conditional proof write. Known
valid proofs are skipped cheaply. Revalidation has a one-time cost and can hit
staff60/min or maintenance429; retry retains already committed proof batches.

Two interactive child processes and one separate maintenance process per API
worker are non-queueing bounded slots. Each receives only trusted Markdown text,
never learner source execution or DB/Auth0/encryption env. Parent caches only128
valid scoped digests/child. CPU250ms, wall2s, address-space256MiB on supported
Linux. This increases margin over the reported105ms valid document while retaining
422 complexity and429 Retry-After1 on overload. It is not a linear parser or a
production throughput claim; worker sizing remains an operational gate.

F6 controls except tab/LF/CR are rejected422 before IPC, invalid UTF8 too. IPC
frame262144 bytes covers worst JSON escaping of30k characters; child independently
rejects controls and oversized frames. F7 capability is explicit in replies and
`scripts/parser-preflight.py`. An unsupported cap logs a fixed warning in local/
test; non-local environments fail503, including cached validations. Linux was
measured; Darwin absence was simulated in tests, not re-tested on the owner's Mac.
Run in a Linux container with suitable process/container limits for real data.

Existing auth keys are reused with a distinct payload domain. Retain old keys
through the existing rotation workflow. Retiring a key requires lesson batch
revalidation and new assignment versions before republish; no immutable version
is rewritten. No new secret/dependency is introduced.

## Assignment lifecycle and version ownership

An assignment belongs permanently to a tenant/course/lesson. Creation locks the
parent course in the same order as lesson deletion so their FK race is serialized. Its mutable parent
has optimistic version, state, and separate draft/published version pointers.
Each edit appends an immutable assignment_versions row, max100 versions/task and
100 tasks/course through the API. Save never changes the version seen by students;
only explicit publish moves the pointer. Archive/unpublish hides new work while
preserving history; restore returns Draft and needs explicit publish. Referenced
lessons/modules cannot be deleted (409); course archive preserves history.

A version stores title, validated Markdown instructions, python/javascript/text
language, plaintext starter code,1–10 rubric criteria totaling100, max attempts
1–20 across all versions, optional timezone-aware deadline, and late policy.
UTC canonicalization is independent of database display timezone; UI enters and
displays Asia/Jakarta/WIB. The version's full rules are included in its proof.
Publish verifies that proof without parsing; unsigned/raw DB versions cannot be
published through the API. Old version content is never substituted in history.

Drafts are one row per assignment/enrollment, student-owned, revision-checked.
Publishing version2 preserves a version1 draft and all its text. Sending the old
draft is409; the UI requires an explicit acknowledgment before saving the copied
answer onto the new version. Learner source is plain UTF8 text, max30k chars,
notes2k. It is stored/rendered escaped, never evaluated or sent to a runner.

Submit uses the exact saved draft's version/revision and a UUID request key.
It atomically copies code/note into an append-only submission with attempt number,
server clock timestamp and submitted/late state. Client timestamp, source/status,
student/tenant IDs are not accepted in this API input. The INVOKER DB trigger
also enforces current published version, own active enrollment, draft revision,
deadline and total attempts, overwriting spoofed code/status/time on raw INSERT.
Staff have read access only to submissions in their authorized courses.

## RLS, transaction and concurrency contract

All four tables FORCE RLS, composite FKs bind tenant/course/assignment/version and
enrollment/student. No UPDATE/DELETE privilege on versions or submissions;
immutability triggers also reject ordinary owner UPDATE/DELETE. New triggers and
rubric validator are INVOKER with fixed search_path and PUBLIC EXECUTE revoked.
The count and grants of18 existing definer functions are unchanged: no new
BYPASS role, membership, reader grant or credential.

Read policies use statement-scoped access helper arrays and uncorrelated child
subplans, retaining LMS-04 scope behavior. Students see published tasks only in
active published enrollments. They may read their own draft/submission versions
when a task is hidden, but never another student's old/private version. Course
unpublish/archive, membership/role revoke and enrollment revoke close work access
as in the parent. Tenant disable remains a pause, not permanent revocation.

The API validates scope before locks; task updates and submits serialize on a
transaction advisory task key. Submit then takes an enrollment/task key and draft
row lock, in the same order in API and trigger. Attempt count/deadline are checked
inside this transaction with clock_timestamp. A simultaneous version change either
finishes before submit and rejects the stale version, or follows its completed
snapshot. Same request UUID+version+draft revision returns the same submission
without consuming an attempt; reuse with another draft is409. Distinct requests
can intentionally use attempts on the same saved draft up to the cap. Draft save
has optimistic revision checks, preventing stale tabs overwriting each other.

Existing authenticated budgets apply before body parsing: staff writes60/min,
student /work reads+writes120/min; body256KiB at BFF and API. Explicit BFF routes,
methods, query parameters and Origin rules forward only session/tenant plus trusted
edge metadata, never arbitrary headers or Set-Cookie. COMMIT remains before send.

## Rollback and operational limits

0010→0011 adds nullable lesson proofs,0012 adds empty assignment tables. Existing
material, completion, enrollments, Auth0 identities/sessions and keyring remain.
No new DB login/role is needed. Populated0012 downgrade takes exclusive locks and
requires exact `-x allow_assignment_data_loss=yes`; without it, including wrong
case/value/base, it raises before dropping data. Offline SQL contains that guard.
An acknowledged downgrade removes all assignment versions/drafts/submissions;
re-upgrade cannot restore them. Restore a verified backup instead for retained
history.0011 downgrade drops only proofs; parent material/revisions persist.

Full auth parent8941a79..4733526, existing14 BYPASS definer review, N2 offline0006,
N3 Unicode/NAT64 and N4 migration cleanup trace remain separate/open. No production
approval, real Auth0 test, automated grading, uploads or learner execution is
implied. Multi-worker/process-memory totals, Docker image, CI remote and real
large-scale assignment capacity still need operational verification.
