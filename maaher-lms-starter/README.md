# Maaher LMS — project-specific starter (v0.1)

**Status:** engineering scaffold / NOT a completed LMS / NOT production-ready.

Auth0/OIDC untuk admin/operator kini memiliki implementasi development:
[panduan setup](docs/AUTH0-SETUP.md) dan [handoff](docs/LMS-01-AUTH0-HANDOFF.md).
Tenant Auth0 nyata, root trust, recovery dan review independen masih diperlukan.

- Original LMS inspired by permitted observations of `https://lms.timedooracademy.com/`.
- Codex = AUTHOR; Claude Code = independent READ-ONLY REVIEWER; human merge/release approval.
- Mac Intel development; dev host via Tailscale `100.127.103.49` (audit required); GitHub owner `mashudizaini` (repo name proposal `maaher-lms`); UAT hostname `maaherlms.aimz.my.id` through Cloudflare.
- Stack: Next.js/TypeScript, FastAPI/Python, PostgreSQL; Indonesian first; multi-tenant by design.

## Read in order
1. `docs/PROJECT-SPEC.md` — evidence, users, modules, requirements, acceptance criteria.
2. `docs/REA-FINDINGS.md` — authorized investigation log, unknowns, reference screenshots.
3. `docs/ARCHITECTURE.md` — tenant, execution sandbox, data model, testing.
4. `docs/SETUP-DEPLOY.md` — Mac, server read-only audit, GitHub, Cloudflare.
5. `docs/AGENT-WORKFLOW.md` — Codex/Claude usage, skill locations, prompts and release gate.

## Local smoke (not an LMS yet)
1. Install Docker Desktop and verify `docker compose version`.
2. `cp .env.example .env` and set **non-default** `POSTGRES_PASSWORD`.
3. `bash scripts/preflight.sh` then `docker compose up --build -d`.
4. Check `http://127.0.0.1:3000` and `http://127.0.0.1:3000/api/health`.
5. `docker compose down` (preserves database volume).

> Health endpoint only; no signup, lessons or grader have been implemented. Never deploy unreviewed features to a public hostname. Do not store LMS credentials, session cookies or learner screenshots containing PII in Git.

## First sprint
1. Run `scripts/audit-server.sh` locally on the server (read-only) and redact output.
2. Record permitted reference UI evidence in `docs/REA-FINDINGS.md`.
3. Codex: create database schema/migrations for tenant, membership, user, course, enrollment; implement permission tests.
4. Claude independent review; fix, rerun tests; human approval.

**Dependency lockfile:** npm dependency resolution is not locked in this offline-generated scaffold; the first PR must run `npm install` on a networked development machine, commit `apps/web/package-lock.json`, and switch Dockerfile/CI back to `npm ci`. Production release is blocked until dependencies are locked and reviewed.
