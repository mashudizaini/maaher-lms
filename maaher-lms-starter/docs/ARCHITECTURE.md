# 03 — Solution architecture & security decisions

## Runtime topology
Browser → Cloudflare (DNS/TLS/WAF; Access during UAT) → tunnel on private Linux host → `127.0.0.1:3000` → Next.js (UI & BFF) → private Docker network → FastAPI API → PostgreSQL. Background queue and grader are **future, separately isolated services**. Tailscale is for administrator SSH, not public routing. No database/API direct public exposure.

## Stack and repository
Monorepo: `apps/web` (Next.js + React + TypeScript, Indonesian UI), `apps/api` (FastAPI + Python), `infra`, `scripts`, `docs`, `.agents/skills`, `.claude/skills`, `.github/workflows`. PostgreSQL 16 suggested pending compatibility/security review. Dependency exact releases should be pinned via lockfiles at first implementation PR.

## Database design (target, not yet migrated)
- `tenants(id, slug, name, status)`
- `users(id, email, identity_provider_id, status)`
- `memberships(id, tenant_id, user_id, role, status)` unique(tenant_id,user_id)
- `courses(id, tenant_id, slug, title, state, owner_id)` unique(tenant_id,slug)
- `cohorts(id, tenant_id, course_id, title)`
- `enrollments(id, tenant_id, course_id, cohort_id, student_id)`
- `modules(id, tenant_id, course_id, position)` / `lessons(id, tenant_id, module_id, position, content)`
- `exercises(id, tenant_id, lesson_id, language, constraints, rubric_version)`
- `submissions(id, tenant_id, exercise_id, student_id, status, source_ref, submitted_at)`
- `grading_results(id, tenant_id, submission_id, grader_version, score, sanitized_feedback)`
- `lesson_progress(id, tenant_id, lesson_id, student_id, status, completed_at)`
- `audit_events(id, tenant_id, actor_id, action, target_type, target_id, timestamp)`

All tenant-owned relations carry tenant_id; enforce composite FK where possible and deny direct client-chosen tenant scopes. Enrollment and teacher relationships must be verified server-side. Migrations use Alembic; review rollback/destructive change impact. Use UTC DB timestamps, display `Asia/Jakarta` in UI.

## Tenant isolation contract — release blocker
1. Authenticate a server-validated identity. Resolve active tenant only from membership (a requested tenant can be a selector **after** validation, never an authorization signal).
2. Every service/repository query scopes by validated tenant, plus object-level course/student permissions.
3. PostgreSQL Row Level Security on tenant tables, `FORCE ROW LEVEL SECURITY` where appropriate. App DB role must not have BYPASSRLS or own data tables. Set tenant context inside each transaction (`SET LOCAL`/`set_config(..., true)`), fail closed when absent; avoid shared session leaks.
4. Tenant scope in job payloads, object storage keys/policies, signed download URLs, cache keys and logs. No cross-tenant object ID lookup.
5. Integration tests: cross-tenant reads/writes/downloads denied with direct identifiers; membership revocation stops access; teacher cannot grade unassigned course.

## Auth implementation and external decisions

LMS-02 development menambah schema 0006 untuk authoring course/module/lesson dan
assignment guru. Contract permission, RLS, version/publish, safe Markdown dan
rollback dijelaskan pada [ADR-006](adr/006-course-authoring.md). Pembacaan materi
siswa tetap menunggu enrollment; belum ada runner atau upload service.
Pemilik menyetujui Auth0/OIDC untuk admin/operator pada 10 November 2026.
Implementasi development tahap 1 dan batas produksinya dijelaskan pada
[ADR-004](adr/004-auth0-development-login.md); panduan tenant/aplikasi ada pada
[AUTH0-SETUP](AUTH0-SETUP.md). Keputusan provider ini menggantikan status
"belum dipilih" di catatan historis, tanpa membuka gate produksi/operator.
Pemilik kemudian memilih TOTP HP khusus local development dengan data sintetis;
[ADR-005](adr/005-development-phone-totp.md) membatasi profile/session/DB tersebut
secara eksplisit. Kebijakan FIDO2/UV produksi tetap berlaku.

LMS-01 implements PostgreSQL-backed opaque sessions with `HttpOnly`, `Secure`,
`SameSite=Lax` cookies and exact Origin checks on mutations. Argon2 hashing,
PyOTP TOTP and Fernet encryption use maintained libraries; no custom crypto or
ad-hoc JWT. See [ADR-001](adr/001-auth-lifecycle.md) for implementation, scope,
secret management and remaining external decisions.
Independent review hardening is specified in
[ADR-002](adr/002-auth-security-review.md): the tenant runtime role cannot
read password hashes or mint sessions; a separate restricted auth credential
holds verifier privileges. Tenant RLS binds to a validated session capability,
and definer functions have a dedicated NOLOGIN non-superuser owner with fixed
search_path and minimum grants. COMMIT precedes successful responses/cookies.

MFA is mandatory for tenant-admin operations and every newly authenticated
admin session. An enrolled user's other tenant operations also require MFA.
There is no platform-operator API or global role in this implementation;
offline provisioning is local-development only. **Operator access still requires
MFA on the host/identity/credential-management workflow before use outside local
synthetic development. This requirement is not satisfied by admin TOTP alone.**
Operator identity, recovery controls and transactional email provider require
server audit, configuration and end-to-end verification. Until those gates and
independent review pass, LMS-01 is not complete or approved for real learners.
Password/email possession cannot bootstrap or replace MFA. The implemented
operator authorization/recovery adapter is deliberately restricted to synthetic
test databases. Auth0/OIDC is now selected; production enrollment, root trust,
recovery and operator workflow still require implementation/verification and
independent review. Existing password-only enrollments are not automatically trusted.

## Coding lab / auto-grader: high-risk system
- Frontend editor (e.g. Monaco) only edits/saves text; not an executor.
- Never run learner code via Python `exec`, Node eval, shell, local Python subprocess, or Docker socket in FastAPI/Next containers.
- Later: isolated worker pool **on a separate host/VM** with VM/microVM-grade sandbox and per-job ephemeral filesystem; no host mounts, no privileged mode, no secrets, no outbound network, enforced CPU/RAM/time/process/output/storage quotas; language allowlist; versioned tests.
- Queue submit → validated artifact → sandbox worker → normalized escaped results → grade/teacher override → audit. Limit concurrency and attempt frequency; no arbitrary Docker control from web API.
- No grader service is included in starter. Add only after separate threat model, penetration tests, and capacity review.

## Data protection / backup
Collect minimal learner data (potentially minors). Parent/guardian consent and legal/privacy requirements reviewed before real enrollment. Encrypt in transit, access-control backups, retention and deletion policies, admin audit, restore drill. Separate UAT dummy dataset from production.

## Repository policy
One repository `mashudizaini/maaher-lms` proposed. GitHub branch protection: PR required, passing CI, human approval, Claude review artifact; CODEOWNERS for security/deploy. No private keys or Cloudflare/Tailscale tokens in repo.
