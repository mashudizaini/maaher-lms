# 05 — Codex AUTHOR ↔ Claude REVIEWER: runbook

## Goal & strict lanes
Codex owns implementation branches and tests. Claude independently inspects committed diff and does not modify source by default. Any reviewer-identified issue returns to Codex for fixes and another review. Human merges and deploys; GitHub CI cannot certify a security model alone.

## Skill setup and navigation
All project skills are **already in this repo**; no download/install required:
- Codex: `.agents/skills/rea-discovery/SKILL.md`, `.agents/skills/lms-feature-delivery/SKILL.md`
- Claude: `.claude/skills/rea-discovery/SKILL.md`, `.claude/skills/lms-security-review/SKILL.md`

Mac Terminal:
```bash
cd /path/to/maaher-lms-starter
find .agents/skills .claude/skills -name SKILL.md
codex   # start author session from repo root
# in another terminal after commit/PR:
claude  # start reviewer session from same repo root
```
The session may auto-select or be instructed explicitly to read `SKILL.md`. If discovery is not shown, ask agent to open the exact path above. Never use skills from untrusted URLs without inspecting them. `.agents/skills` and `.claude/skills` are repo-local paths; user-global skills would be separate.

## REA (optional)
Read `docs/REA-FINDINGS.md`; use a browser with a legitimate account and minimum necessary permission, redact personal data. Review REA upstream before running `npx rea-agents setup`; exact CLI flags can change. Do not commit browser cookies or screenshots containing student data.

## MCP (minimum viable)
- No MCP is mandatory to run starter. Tools: Git CLI, Playwright when UI work begins, optional REA for permitted discovery.
- GitHub CLI recommended for PR workflow; no repository token in code.
- Browser/Playwright MCP: install only from trustworthy project, read requested permissions, use test account; deny access to real production credentials by default.
- Cloudflare/admin MCP not installed by default to prevent inadvertent changes. Prefer dashboard/manual with approvals.
- Postgres MCP production write access: prohibited; only read-only dev database if genuinely needed.

## Ticket lifecycle
1. Write ticket (ID, role, screens, acceptance criteria, tenant security tests, out-of-scope).
2. Codex branch `feat/LMS-xx-short-name` implements only ticket; runs tests, lint/types, migration checks.
3. Codex commit + PR; handoff includes files changed and exact test output.
4. Claude independently reviews `git diff main...HEAD`, checks data access, tenant isolation, coding sandbox boundaries and UI/test quality; writes `reviews/LMS-xx-claude.md`.
5. Codex fixes; Claude re-review. Human approves PR once blocking issues solved + CI green.
6. Staging UAT then separate production approval.

## Ready-to-run prompts
### Codex — AUTHOR
```text
You are AUTHOR for Maaher LMS ticket LMS-01 (auth and tenant membership design/implementation).
Read AGENTS.md and docs/PROJECT-SPEC.md, docs/ARCHITECTURE.md, docs/AGENT-WORKFLOW.md.
Use .agents/skills/lms-feature-delivery/SKILL.md. First give a bounded plan and security assumptions.
Implement only ticket requirements, with negative cross-tenant tests and migrations as needed.
Do NOT implement a coding runner or deploy. Report changed files, commands/results, risks, and Claude review instructions.
```
### Claude Code — REVIEWER
```text
You are independent READ-ONLY REVIEWER. Codex authored changes in this branch.
Read CLAUDE.md, docs/ARCHITECTURE.md, docs/PROJECT-SPEC.md, docs/AGENT-WORKFLOW.md,
and .claude/skills/lms-security-review/SKILL.md.
Inspect `git diff main...HEAD`, execute safe non-destructive tests, and report only proven issues,
including path:line, severity, reproduction, recommended fix and untested risks.
Save report at reviews/LMS-01-claude.md. Do not modify application code.
```
### Codex — fix review
```text
Read reviews/LMS-01-claude.md, address BLOCKER/HIGH with minimal patch and regression tests.
Respond per finding. Do not deploy; request a fresh independent Claude review.
```
### Codex — REA discovery
```text
Use .agents/skills/rea-discovery/SKILL.md and docs/REA-FINDINGS.md.
Study only normal authenticated browser flows in owner-authorized Timedoor account.
Log OBSERVED/INFERRED/UNKNOWN with redacted evidence. Propose original Maaher equivalent.
Never copy protected assets or bypass security. Do not code yet.
```

## Review report template
```md
# LMS-XX Claude Review
Base / head SHA:
Files inspected:
Tests run and results:
Findings:
- [BLOCKER/HIGH/MEDIUM/LOW] path:line — symptom, proof, user/tenant impact, fix
Untested risks:
Decision: CHANGES_REQUESTED | APPROVED_WITH_NOTES | APPROVED
```
