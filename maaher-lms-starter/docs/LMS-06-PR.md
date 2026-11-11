# Add private teacher grading and explicitly released student feedback

Teachers assigned to a course and tenant admins can grade immutable submissions
against the submitted task version's rubric. Draft scores stay private; explicit
release exposes a separate student snapshot. Draft corrections preserve the
previous published grade until release, and reasoned withdrawal clears public
scores/feedback while retaining private immutable history and audit. Zero scores
are valid. Submitted source remains unchanged and never executes.

Schema0013_grading adds five FORCE-RLS tables, composite parent keys and INVOKER
triggers deriving totals, actor, timestamps, publications and audit. Students
cannot read private grade roots/revisions/events even through runtime SQL.
Version checks and per-submission locks serialize updates; fresh authority checks
reject teachers revoked during a lock wait. No new role, dependency, secret or
SECURITY DEFINER. Staff GET180/min, writes share course60/min, student reads share
work120/min. BFF retains explicit paths/query/method/Origin/body/header boundaries.

`/grading` provides queue, original submission/rubric, draft/release/withdraw and
history; `/work` shows only the student's released grade. Conflicts/throttle retain
staff editor input. Forward migration preserves parent data; populated downgrade
requires explicit destructive acknowledgment and was tested only on disposable DBs.

Author Linux validation: full378 API/parser PASS, then4 targeted PASS (2 new cases,
2 repeats); final380-case collection, all unique cases covered across runs, not
one full380 run. Scripts12, Actions16 and browser19 PASS. Build/typecheck/audits
pass (npm0,PyPI41 pins0 findings/errors). Seeded upgrade/guard/offline/acknowledged
rollback, direct SQL isolation/spoofing/immutability and concurrent visibility/
revocation races pass. Browser uses synthetic providers, not real Auth0 UAT.

Stacks on unmerged LMS-05, base13408bb (runtime5131f2c). LMS-05 independent verdict
is APPROVED_WITH_NOTES for synthetic dev/UAT, F9/F11 closed and F10 with capacity
notes. Grading itself still needs independent review and Mac UAT. Slow-host parser
margin, queue saturation, F12, F3, parent N2/N3/N4, tenant pause and full auth
8941a79..4733526 remain separate/open. Remote CI, real Auth0/FIDO2, app Docker image,
multi-worker and large-gradebook capacity were not verified here.

See LMS-06-HANDOFF.md and LMS-06-MAC-SETUP.md for evidence and backup/forward upgrade.
No merge/deploy or production approval. This is a prepared PR description;
GitHub API access is unavailable here, so no PR creation is claimed.
