# Independent Claude review — LMS-05

AUTHOR implemented this delta. No author approval replaces your independent
review. Read AGENTS.md, CLAUDE.md, docs/PROJECT-SPEC.md, ARCHITECTURE.md,
AGENT-WORKFLOW.md and .claude/skills/lms-security-review/SKILL.md.

Review **54543a8..HEAD** on feat/LMS-05-assignments-submissions; runtime parent
5b675e6. If main/ref unavailable, record that and use exact objects, do not assume
main...HEAD is a delta-only review. Six documentation files in5b675e6..54543a8
are author-verified. Original LMS-04 report remains on Mac, preserve it unchanged.
Scope: F5/F6/F7 response plus assignment/schema/API/BFF/UI; auth parent separate.

Read ADR-009, LMS-05-HANDOFF/CHECKLIST and author-response/performance.json. Verify:
- Proofs bind exact policy/tenant/lesson/revision/content/resources; stale/tampered/
  missing/retired-key proof fails409. Publish never reparses1500 lessons. Legacy
  validation is explicit/Draft/batched, does not silently certify or change state;
  proof write cannot attest a concurrently changed row. Keep key rotation in view.
- Reproduce publish1500×29KB with concurrent writer every0.5s and API health on
  real uvicorn/TCP. Record setup/validation vs publish cost. Test burst/steady
  writer fairness across lanes, parser process caps and actual CPU budgets.
- Controls22k/30k return422 without worker crash. Large safe JSON frames pass.
  Native Darwin memory cap remains WARN if unsupported; production fails closed.
- Assignment immutable versions and draft vs published pointer; rubric/deadline/
  attempts tied to version; timezone-independent proof, UTC server/WIB UI.
- Student own drafts/history, no peer/foreign versions. Assigned teacher only,
  course/role/status/enrollment revoke, archives, RLS and composite FKs directly.
- Concurrent submits/versions/draft tabs: idempotency, attempt cap acrossversions,
  server timestamp/late policy, snapshot from saved draft, no raw runtime bypass,
  immutability owner/API checks and no UPDATE/DELETE grants. Authority beforelock.
- New functions INVOKER, existing18 definers/grants unchanged. BFF allowlist,
  cookie-only auth and valid tenant, edge-secret, bodybound, Origin, query,
  Retry-After/no Set-Cookie. New routes consume existing authenticated budgets.
- Seeded upgrade10→12, exact acknowledgment downgrade guard and offline SQL;
  parent completion/material/enrollment/auth survive acknowledged rollback on
  disposable fixture. No use of old/UAT DBs for tests.

Create your own NEW EMPTY maaher_test_ database/container with distinct owner and
restricted runtime/auth/operator URLs. Full fixture performs destructive rollback;
F1 benchmark temporarily installs legacy policies. Preserve old DBs/containers.
Do not read/print .env secrets or modify source/Auth0/owner sessions. Real browser
harness supports --oidc --dev-totp --assignments and --learning; synthetic provider
must be labeled as such. Do not claim real Auth0/FIDO2, remote CI, image Docker,
Darwin, multi-worker, manual owner UAT or auth approval unless actually tested.

Save a NEW reviews/LMS-05-claude.md, include exact SHAs, executed commands/results,
proven findings with severity/repro/path:line and untested limits. Do not overwrite
prior reports. F3/N2/N3/N4/tenant pause remain open unless independently proven
changed. Full auth review8941a79..4733526 is still separate; this request does not
ask to silently include/approve it. No merge/deploy or learner execution.
