# LMS-06 — teacher grading handoff

**Update Mac:** pemilik melaporkan preflight13 PASS, browser grading sintetis2
PASS, suite penuh378 PASS/1 SKIP/1 FAIL fairness (503 bersama422); rerun terisolasi
PASS tidak menutup FAIL. API/web200; login Auth0 nyata belum diuji. Baca
[relay](../reviews/LMS-06-mac-validation-relay-20261111.md) dan
[diagnosis](LMS-06-FAIRNESS-DIAGNOSTIC.md). Root cause masih OPEN. Follow-up hanya
menambah diagnostik tes dan satu kasus redaksi (koleksi381); runtime/schema tetap.
Angka author awal di bawah adalah bukti historis6d83474, tidak menggantikan hasil
Mac. Manifest/patch/verifikasi awal tidak diregenerasi.

11 November 2026, Asia/Jakarta. AUTHOR implementation, independent review pending.
Branch `feat/LMS-06-teacher-grading`; base
`13408bb6ab471d8d33f99162a239177f14decbec` (documentation over runtime5131f2c).
Schema **0013_grading**, parent0012_assignments. See [ticket](tickets/LMS-06.md),
[ADR-011](adr/011-teacher-grading-and-release.md), [checklist](LMS-06-CHECKLIST.md).

## Result and changed areas

Staff can grade immutable submissions using their original rubric, save private
drafts, explicitly release scores/feedback, draft corrections while the old grade
remains visible, and withdraw with a private reason. Students see only their own
released snapshot. Private revision/audit history is retained; scores0..100 and
per-criterion bounds are enforced in API and SQL. Student source never executes.

- API: `app/grading.py`, `grading_limits.py`, ingress/router wiring and restricted
  maintenance counter cleanup. GET queue/detail/history, POST draft/release/withdraw,
  student GET publication. Shared write60/min, staff GET180/min, work120/min.
- DB: `migrations/grading.sql`, `versions/0013_grading.py`; five RLS tables,
  INVOKER triggers, original-rubric/server-total/actor/time checks, private/public
  separation, immutable revisions/events and guarded rollback. No new definer.
- Web: `/grading`, publication component on `/work`, grading BFF allowlist,
  navigation and styles. Feedback escaped;409/429 preserves grading editor.
- Tests/scripts: SQL/API/race/seeded migration tests, two grading browser tests,
  synthetic teacher fixture, harness `--grading`, schema verifier and CI job.
  Parent migration tests now expect head0013; downgrade fixtures stay disposable.

## Actual author validation

Cloud Linux, Python3.12.14, Node24.22.1, PostgreSQL16.15; one API worker and local
TCP where tests specify it. All DBs newly created for this task, not old/UAT DBs.
Own test container `maaher-cloud-review-20261109`, port127.0.0.1:32778 during run.
Credentials were loaded privately, not printed or committed.

| Command / evidence | Actual result |
|---|---|
| `python -m pytest apps/api/tests -x -q -s` |**378 PASS**,0 SKIP,2 existing deprecation warnings,633.87s |
| Final targeted concurrency/authority tests below |**4 PASS**,34.24s;2 new cases plus2 repeated cases |
| `python -m pytest --collect-only -q apps/api/tests` |**380 collected**,1.04s; no deselection |
| `python -m pytest -q scripts/tests` |12 PASS,0 SKIP |
| `node --test infra/auth0/*.test.cjs` |16 PASS,0 SKIP |
| Browser grading /assignments /learning /enrollment /courses |2 /2 /2 /2 /2 PASS |
| Browser auth /OIDC synthetic FIDO2 /synthetic dev-TOTP |7 /1 /1 PASS;**19 unique browser cases total** |
| Next typecheck /production build |PASS |
| compileall API+migrations /pip check /starter verification |PASS |
| npm production audit /PyPI runtime advisory snapshot |0 vulnerabilities /41 pins,0 findings/errors |

**There was no single380-case full run.** The378-case full run preceded two new
race cases; the subsequent4-case run covers both new cases plus two authority
regressions. Runtime source did not change after the full run. All380 final
unique cases were therefore executed successfully across these runs. On native
Mac the Linux-only capability case is expected to SKIP, not content tests.

Supplemental command (all under `apps/api/tests/test_grading.py`):

```bash
python -m pytest \
  apps/api/tests/test_grading.py::test_concurrent_draft_and_visibility_change_never_release_unreviewed_revision \
  apps/api/tests/test_grading.py::test_raw_sql_authority_is_rechecked_after_entry_lock \
  apps/api/tests/test_grading.py::test_lost_teacher_authority_while_waiting_cannot_save -x -q
```

Earlier parent assignment subset26 PASS; grading+migration subset30 PASS before
the final full run. One initial new budget test failed after23 PASS because its
fixture updated a counter before creating that counter. The fixture now creates
it with a real GET before exhaustion; subsequent subset/full runs pass. No rate
budget/runtime behavior was weakened. Final test-only lock-cleanup changes avoid
hanging a failing authority assertion; the repeated targeted cases passed.

Browser harness: `python scripts/test-lms01-browser.py --oidc --dev-totp --grading`
with new role-specific test URLs on the same new DB. Other modes use the existing
auth/FIDO2/dev-TOTP/courses/enrollment/learning/assignments flags on separate DBs.
All providers are signed **synthetic providers**, including FIDO2/TOTP profiles;
no real Auth0 enrollment/login or manual owner UAT is claimed. Grading browser
asserts actual teacher role/assignment and a separate student browser session.
It verifies original rubric despite newer task version, private draft, release,
correction hidden until share, withdrawal, private history, unchanged source,
escaped script text, retained editor after429 and BFF negative paths.

SQL/API coverage includes tenant/peer/student/teacher isolation; no student SELECT
on private revision/event/root even after release; zero scores;14 invalid bodies;
actor/time/total spoof normalization; immutable owner/runtime DML; conflicting
drafts and release/withdraw races; authority before and after blocked locks;
read budget/retention grants; history pagination and generic audit. Seeded
migration hashes identity/session/OIDC/material/enrollment/progress/task/draft/
submission data across upgrade and acknowledged downgrade. Invalid flags/base
are refused; offline SQL works; old18 definer bodies/grants remain unchanged.

## Parent regressions and remaining limitations

Machine-readable methods/results: [verification JSON](../reviews/LMS-06-verification.json).
Full-run parent publish1500×29KB1326.59ms,8 concurrent writer requests200;
health sampled after publish/during writer p951.65ms. Fixture validation/signing
setup is excluded. Current student SQL1500 lessons21.85ms vs reconstructed old
26365.05ms; outline ASGI177.76ms, catalog45121.09ms. These are parent regression
measurements on this host, not gradebook throughput or production SLOs.

Real HTTP parent fairness2/4/8 accounts, same/different tenant: all36 normal
author saves and36 student drafts200 while all attack loops were active. Worst
normal save3698.21ms, student465.92ms, health p9514.23ms. Dense valid CPU max
130.156ms at1000ms budget, margin7.68×. The independent reviewer's slower-host
and16/20-tenant capacity notes still apply; these results do not close them.

[LMS-05 re-review relay](../reviews/LMS-05-claude-rereview-relay-20261111.md)
records F9/F11 CLOSED and F10 CLOSED_WITH_NOTES, with the old344/347 count gap
resolved. Full auth8941a79..4733526 remains unreviewed/separate. F12, F3, parent
N2/N3/N4 and tenant pause remain open; grading GET limits address this feature
only. Real Auth0/FIDO2, Mac manual UAT, remote CI, Docker application image,
multi-worker and target-hardware calibration were not run here. No new grading
lock timeout or large-gradebook capacity result is claimed.

## Upgrade, preservation and next action

Use [Mac setup](LMS-06-MAC-SETUP.md). Back up the confirmed synthetic development
DB, use migration credential for forward0012→0013, rebuild/restart API/web. Keep
.env/keyring/Auth0 policies/bindings and all existing DBs/reports intact. No new
secret, dependency or global role. The migration credential must own the parent
objects; never make the API role owner/superuser to work around a failure.

Rollback destroys grade history and is not the Mac setup path. It requires exact
`-x allow_grading_data_loss=yes` if populated and is tested only on new disposable
DBs. Parent submissions/data survive; generic audit remains; re-upgrade cannot
recover removed grades. Counter cleanup remains local/test synthetic only.

New test DBs retained under `maaher_test_lms06_*_20261111`: initial,grading,
gradechecks,full,finalraces,browsergrading,browserauth,browserfido,browsertotp,
browsercourses,browserenrollment,browserlearning,browserassignments. Migration
fixtures also create new random DBs, including parent-prefix names. None deleted.
Only the owned cloud container is stopped at completion; its DBs remain stored.
No direct Mac, Auth0, Timedoor or old database changes were made by cloud AUTHOR.

Historical patches/manifests and original Claude reports are unchanged. Original
LMS-01 Claude SHA256 remains
`004a19183409b152d0947ab6f5b99af2000d9dd3324c9a2c77ea66a4106032ce`.
New LMS-06 manifest/patch use base13408bb, exclude themselves and validate against
an independent temporary Git index, without applying to the workspace.

Follow [review request](../reviews/LMS-06-review-request.md) for independent Claude
review; save a new report. GitHub API PR access is unavailable in this environment;
the source branch and [PR description](LMS-06-PR.md) are the reviewable delivery.
No merge/deploy, production approval, runner or real-student rollout.
