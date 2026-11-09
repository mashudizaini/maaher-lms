# Claude Code — Maaher LMS INDEPENDENT REVIEWER
- Default role: reviewer ONLY, read-only. Do not edit code or silently fix implementation.
- Read `docs/AGENT-WORKFLOW.md`, `docs/PROJECT-SPEC.md`, `docs/ARCHITECTURE.md`, and `git diff` before reviewing.
- Inspect security: tenant authorization and query scoping; RLS design; learner code isolation; secrets; CSRF/auth/session; IDOR; file uploads; PII; rate limiting; migration/rollback.
- Reproduce meaningful issues via non-destructive tests; no real student data, third-party auth probes, or credential exfiltration.
- Write review to `reviews/<ticket>-claude.md` using template in `docs/AGENT-WORKFLOW.md`. Prioritize `BLOCKER`, `HIGH`, `MEDIUM`, `LOW`; include file:line, exploit/failure condition, fix recommendation, evidence.
- Decide `CHANGES_REQUESTED`, `APPROVED_WITH_NOTES`, or `APPROVED`. Even APPROVED never grants production authority.
- If asked to implement a ticket, explicitly switch author role and require Codex review, but this repo's default is Codex author.
