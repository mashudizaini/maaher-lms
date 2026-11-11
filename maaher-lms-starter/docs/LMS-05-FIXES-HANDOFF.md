# LMS-05 review fixes — author handoff

11 November 2026 WIB. Branch **feat/LMS-05-assignments-submissions**, base
**84dd193709f7cb126e655f7f143e16b3577058a1**; reviewed runtime4a450d5, schema remains
**0012_assignments**. F9/F10 MEDIUM and F11 LOW implemented for re-review. Parent
review APPROVED_WITH_NOTES remains limited to synthetic small–medium dev/UAT;
no production/auth-parent approval. Original report is on Mac, not rewritten here.

## Behavior

- Parser now queues finite work from validated tenant:user scopes rather than
  rejecting any user just because both global slots are occupied. Least-active
  tenant first, FIFO among accounts;1 in-flight/account/lane,10/tenant,16 waiting.
  Two interactive children and one maintenance child, not a process per tenant.
  Own concurrent/tenant limit429, global capacity/expiry503, Retry-After1. Waiting
  can take seconds; no promise of zero overload on arbitrary scale/hardware.
- Hard CPU1000ms/wall3000ms, queue8s/caller about11.2s; existing BFF15s. CPU cap
  chosen with margin above reviewer's valid266ms; not auto-unbounded. Calibration
  prints uncached CPU samples/margins, WARN below2. Memory256MiB/Linux, native
  Mac WARN local/test and fail outside remain. Only separate Linux capability
  assertion can skip; content/frame/CPU tests always execute.
- Compatible signedv2 content proofs remain valid with semanticv3 policy. Same
  Markdown/URL/control rules: existing courses and immutable task versions need
  no backfill/version changes for this resource-profile update. Unknown policy/
  unsigned/tampered/retired-key proofs remain rejected. Genuine key retirement
  has the original operational cost (F12 still open).
- Extreme offset date UTC overflow returns422 before a version is written.
  Lone surrogate errors now serialize safely422 with bounded type/loc/msg and
  no input/ctx, including parent lesson and student draft. Genuine Unicode still
  works. Common auth validation-error responses change, not auth/session/MFA
  policy; that compatibility is covered in the parent regression suite.

Files: markdown_budget/service/worker, content_attestation, assignments deadline
validator, main+validation_errors, diagnostic script, parser/queue/boundary tests
and assignment BFF browser assertions. No migrations, credentials, DB role/grant,
provider Action, UI flow or learner execution changes. Source code submitted by
students remains stored text and is never given to the Markdown parser/executor.

## Validation actually run

Cloud Linux/Python3.12.14, PostgreSQL16.15, Node24.22.1, Next production and real
Chromium. All tests own NEW EMPTY maaher_test_ DBs, distinct non-owner runtime/
auth/operator/mail/maintenance roles. No real tenant/Auth0/Mac data accessed.

| Command/check | Actual result |
|---|---|
| `python -m pytest apps/api/tests -x -q -s` | **347 passed,0skip,2 existing deprecation warnings**,413.53s |
| Expanded `python -m pytest apps/api/tests/test_parser_fairness.py -x -q -s` | **5 passed,0skip**,81.37s after full suite; adds simultaneous student draft coverage, runtime unchanged |
| Earlier parser/content subset /queue+input subset |16 passed/35.38s;18 passed/82.60s before expanded student coverage |
| Scripts /Auth0 Action |12 passed/0.16s;16 passed/0skip |
| Chromium assignments /auth /FIDO2 /dev-TOTP /courses /enrollment /learning |2/7/1/1/2/2/2 = **17 passed**,0skip |
| Assignment browser additions |Raw task/draft surrogate + extreme date through Next BFF return422, sentinel input not reflected |
| Next typecheck/build, compileall, pip check, starter, source diff check |PASS |
| npm production audit /PyPI advisory snapshot |0 vulnerabilities /41 pins,0 findings/errors |
| `parser-preflight.py --calibrate`, local and production profile |Three Linux processes each report active256MiB,CPU1000/wall3000; all measured margins>2 |

Full suite ran after final runtime changes. The queue test was then expanded to
exercise real student drafts concurrently with normal authors; all5 cases reran
on another new DB. No runtime change followed those runs. No whole-test exclusion,
xfail or --deselect; Linux memory test actually executed. Native Mac skip behavior
is explicit in source, not claimed as a local Mac run.

Expanded real HTTP probe: trusted test fixture creates opaque sessions, active
memberships and assigned teacher courses; server still performs real session/RLS
checks on each request. Three loads2/4/8 accounts≤1request/s,6 normal author saves
and6 student drafts per load, repeated for same/different tenants. Every normal
save records all attack loops still active; attacks run until normal loops finish,
up to12 requests/actor/load, never raising original budgets. Student drafts use
their own enrollment/version/revision; they do not pass through Markdown parsing.

| Accounts | Same-tenant author max /student max ms | Different-tenant author max /student max ms |
|---|---|---|
|2|758.77 /219.88|851.33 /219.93|
|4|2081.30 /260.07|1476.96 /210.85|
|8|4648.78 /387.81|2393.09 /210.65|

All36 author writes and36 student drafts200; no innocent429/503 in these episodes.
Attacks422, per-account max observed budget≤19/60 in expanded run. Worst health
p959.71ms. Queue ordering/bounds/expiry/sequential completion also tested with
controlled stub ordering; Events there are not CPU-isolation evidence. HTTP CPU
work is real CommonMark, not an Event/model-only assertion. One API worker only.

Dense valid30k five uncached CPU samples89.410–96.648ms,1000ms budget/max margin10.35
in full run. Diagnostic samples under other load up to227.941ms; record all values
in fixes-performance.json, do not substitute fastest sample for host calibration.
Actual CPU-loop child verifies SIGPROF independent of parser speed. The adversarial
TCP suite preserves original52/60 account budget and422/own429 statuses; health
p95/8 concurrent requests11.06ms. These old single-account collisions are different
from unrelated-account fairness; do not interpret their own429 as F10 regression.

F5 publish regression1500×29KB904.23ms,8 other-course writes all200. Fixture content
validated before signing; one-time setup excluded, health after publish/during
writer2.35ms. F1 SQL1500 student24.44ms vs reconstructed23192.19ms; current outline
ASGI132.20ms and catalog45116.55ms. Full methods/raw metadata in performance JSON;
none are production SLOs or proof of the owner's slow-host behavior.

## Operations and next step

No schema upgrade/downgrade/backfill needed. Rebuild/restart the existing dev API/
web after safe source update; preserve .env/keyring/Auth0/binding and all data.
Follow LMS-05-FIXES-MAC-SETUP.md; rerun dense content and calibration on the actual
Mac and Linux/container. Do not deselect content tests to hide capability failures.
Only test_linux_memory_capability_only skips on non-Linux. Capture exact source/
schema/counts/platform and any FAIL/WARN without changing security settings.

Then independent Claude re-review via reviews/LMS-05-rereview-request.md, save NEW
reviews/LMS-05-claude-rereview.md. F9/F10/F11 author fixes are not independently
CLOSED; full auth8941a79..4733526 remains separate. F12 and F3/N2/N3/N4/tenant pause
remain open. Real Auth0/FIDO2/manual owner UAT, native slow Mac, remote CI, app
Docker image and multi-worker not tested here. The production-profile parser
capability check is not a production auth/application deployment test.

All new test DBs retained: maaher_test_lms05fix_{targeted,fixes,full,studentpressure}_20261111,
seven browser DBs browserassignments/auth/fido/totp/courses/enrollment/learning
under that prefix/suffix, plus parent migration fixtures' freshly created random
DBs. Only the owned cloud maaher-cloud-review-20261109 was started, dynamic test
port127.0.0.1:32777; it is stopped after completion, not deleted. No existing Mac/
reviewer DB/container/service was touched; no user database reset or downgrade.

Historical LMS-05 patch/manifest and original Claude reports remain unchanged.
New fixes-author.patch/manifest use base84dd193 and exclude themselves; baseline
apply check uses an independent temporary Git index, never applies to workspace.
API PR access remains unavailable (previous Forbidden); branch/review description
are the reviewable delivery. No merge/deploy or learner runner.
