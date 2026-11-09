# Codex — Maaher LMS AUTHOR
- Primary role: implement **only** approved tickets in `docs/PROJECT-SPEC.md` and `docs/ARCHITECTURE.md`.
- Begin each task: read `docs/AGENT-WORKFLOW.md`; list scope, affected files, tests and assumptions. Do not expand scope silently.
- Write original code; REA evidence is for behavioral understanding only. No proprietary code/assets, private endpoint probing, credential capture, anti-bot bypass.
- Tenant isolation is mandatory. Resolve tenant from validated session + membership; NEVER trust a client-supplied tenant id or UI filter. Apply tenant scoping to every query and object access. Implement RLS with migration and tests before releasing tenant data.
- Never use eval/exec/subprocess or Docker socket for learner code in the API container. Runner disabled until isolation security gate.
- Indonesian UI text and accessibility; English identifiers and code docs permitted.
- Provide tests and a clear handoff: changed files, commands run, outcomes, risks, migration/rollback.
- Do not merge or deploy automatically. Claude Code must independently review the diff in a separate step; human decides.
