# LMS-06 — independent Claude review request

**Latest owner evidence:** Mac full suite378 PASS,1 Linux-capability SKIP,1 FAIL
fairness (503+422), isolated rerun PASS. Actual node/503 category/HEAD not supplied;
[relay](LMS-06-mac-validation-relay-20261111.md). Test-only follow-up retains safe
partial metrics on failure and adds one redaction case (final collection381).
Runtime/schema unchanged; no root-cause fix/closure claimed. Review this OPEN
issue explicitly; do not accept503 by silently changing assertions. Earlier
author counts380 below refer to6d83474; original artifacts stay unchanged.
Author diagnostics:6 targeted cases PASS on new cloud DB. A separate controlled
test-client response substitution produces expected FAIL and retains partial
safe metrics; it is not a runtime503/Mac reproduction. Full381 not rerun; read
LMS-06-fairness-diagnostics-verification.json and diagnostic guide for boundaries.

11 November 2026, Asia/Jakarta. AUTHOR requests a separate read-only application
review. Save a NEW `reviews/LMS-06-claude.md`; preserve all older reports, source,
.env/keyring/bindings, UAT and test DBs, containers and the owner's running API.
This file is not a Claude verdict. Read CLAUDE.md, docs/AGENT-WORKFLOW.md and
.claude/skills/lms-security-review/SKILL.md, plus ADR-011 and LMS-06-HANDOFF.md.

## Scope and baseline

Branch feat/LMS-06-teacher-grading, base
`13408bb6ab471d8d33f99162a239177f14decbec`, schema0013_grading.
Inspect `git diff 13408bb..HEAD`; record actual SHAs and dirty/untracked state.
Branches are stacked/unmerged; main...HEAD also contains auth/course/enrollment/
learning/assignments parent. Do not treat an LMS-06 approval as review of that
entire parent or the still-separate auth8941a79..4733526. If refs are missing,
report the actual scope; don't invent a diff. New manifest/patch exclude themselves
and verify against a temporary baseline index; historical artifacts stay historical.

LMS-05 re-review5131f2c was reported APPROVED_WITH_NOTES; AUTHOR relay is
LMS-05-claude-rereview-relay-20261111.md, not the original Mac Claude report.
F9/F11 CLOSED, F10 CLOSED_WITH_NOTES for synthetic dev/UAT; parser capacity/
slow-host notes and F12/F3/parent N2/N3/N4/tenant pause remain. Do not silently
close those or reproduce production policy from synthetic tests.

## Focused probes

- All five new tables FORCE RLS, composite tenant/course/submission relationships.
  Active assigned teacher/admin can grade only authorized course. Peer/other
  tenant/revoked student cannot read publications; archived course blocks writes,
  admin may read history; task archive retains submission history.
- Student runtime SQL cannot SELECT grading_entries, grade_revisions or
  grading_events, even after a revision is released. grade_publications contains
  only disclosure fields; no private reason/reviewer/draft leaks. Withdrawal
  clears all grade payload; pre-release ungraded response reveals no draft state.
- Rubric belongs to submitted assignment_version, not current published task.
  Integer/per-index bounds, exact criteria, total0..100 and zero handling.
  Validate raw SQL malformed scores/extra keys/spoof totals/actors/timestamps,
  not just Pydantic. Revision/root/publication/event transitions and generic audit
  must stay atomic; direct publication/event insert/update cannot forge history.
- Immutable revision/event UPDATE/DELETE rejected for runtime and owner ordinary
  DML, runtime TRUNCATE denied. No new definer or expanded old18 definer ACL/body;
  maintenance only expired counter timestamp read/delete, never grade data.
- Concurrent initial drafts, stale updates and draft vs release/withdraw produce
  one winner/one conflict, never implicitly release an unreviewed correction.
  Revoke assignment/membership while a request/raw SQL waits on entry lock:
  authority checked before and after wait using fresh snapshot. Check VOLATILE
  helper does not restore per-row parent performance regressions.
- Queue/history pagination, input/Unicode/body bounds, read-only archives,
  editor retained on409/429, safe feedback escaping and original source immutability.
  BFF exact route/method/query/Origin/cookie/header/256KiB limits, no Set-Cookie
  leakage, Retry-After and student GET-only publication route.
- Staff GET180/min, POST existing60/min, student existing120/min. Counter commits
  on rejected requests and restricted expiry cleanup. Parent GET budget/retention
  scheduler still separate; do not approve production operation based on this.
- Seeded0012→0013 preserves parent identity/session/OIDC/course/enrollment/progress/
  tasks/drafts/submissions hashes. Wrong/no rollback flags and base refuse without
  data loss; exact acknowledged downgrade only on your own disposable DB;
  offline SQL works. Parent submissions survive; generic audit intentionally remains.

## Reproduction and reporting

Use a newly created empty `maaher_test_` DB on your own new review container, with
separate migration/runtime/auth/operator/mail/maintenance URLs to that same DB.
Do not reuse owner/old test DBs: fixtures perform rollback and RLS reconstruction.
Don't delete other containers or run broad process-kill commands. Stop only
services you started; retain your DB/container unless the owner directs otherwise.

Run full pytest without omitting rollback modules. Final author collection380;
full run378 PASS plus4 supplemental PASS (2 new,2 repeats), no single380 run.
On Mac only Linux-capability skipif may skip. Record counts/node IDs and explain
differences; no --deselect to hide content failures. Separate platform capability
from CPU tests. Scripts12, Actions16, browser19 PASS author evidence; rerun only
what your environment supports and mark the rest NOT TESTED.

Grading browser: `python scripts/test-lms01-browser.py --oidc --dev-totp --grading`
on another new empty DB. It uses assigned teacher and student in separate contexts
with a signed synthetic provider. It does not verify real Auth0/FIDO2 or owner UAT.
Remote CI, image, multi-worker and target calibration were not run by AUTHOR.
Probe gradebook scale if feasible; no author grade-throughput SLO is claimed.

Report proven findings with severity/path:line/reproduction/impact/recommendation,
actual tests and limitations. Source changes go back to AUTHOR. No merge/deploy,
production auth or real-user approval is delegated by this request.
