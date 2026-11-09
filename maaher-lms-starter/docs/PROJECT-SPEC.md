# 01 — Maaher LMS Product Spec · v0.1 (baseline)

**Product:** original Indonesian-first, multi-tenant coding-education LMS. **Domain planned:** `maaherlms.aimz.my.id`; release sequence restricted UAT → explicit public launch. **Owner/account:** `mashudizaini` (GitHub namespace; repository not yet created).

## Confirmed input vs assumptions
- Confirmed by project owner: legitimate Timedoor student/teacher account; learner/teacher/admin; courses, coding lab, assignments, graded feedback, progress; auto-evaluation in stages; GitHub + Cloudflare + Tailscale on-prem dev host; Mac Intel; Codex author / Claude reviewer.
- Reference LMS authenticated screens: user-provided screenshots are inputs, but exact controls/routes/labels and workflows still require annotated verification in `REA-FINDINGS.md` before treated as facts. Public web inspection did not expose usable authenticated page content.
- Assumptions pending validation: payments, live sessions, certificates, parent accounts, video storage, school branches, number of students, curriculum levels. **Out of scope until approved.**

## Personas and permissions
| Role | Allowed scope | Essential abilities |
|---|---|---|
| Platform operator | Global support with explicit privileged workflow | tenant provisioning, health, controlled support audit |
| Tenant admin | Current tenant only | manage teachers/students/courses, enrollment, reporting |
| Teacher | Assigned courses/cohorts in tenant | publish lessons, review submissions, feedback/grades |
| Student | Own enrollments in tenant | lessons, browser editor, exercises, submissions, progress |

A user may belong to multiple tenants. Tenant selection requires authenticated membership. No cross-tenant sharing by default.

## Modules: phase 1 acceptance backlog (not all implemented in starter)
| ID | Module | Minimum acceptance criteria | Priority |
|---|---|---|---|
| LMS-01 | Auth & tenant memberships | session, invite, password reset, membership check, role matrix, audit, negative cross-tenant tests | P0 |
| LMS-02 | Course management | tenant-scoped courses, modules, lessons, publish/unpublish; safe rich text and assets | P0 |
| LMS-03 | Enrollment / cohorts | students in cohorts, enrollment uniqueness and access enforcement | P0 |
| LMS-04 | Student learning | Indonesian navigation, lessons, completion state, next-step | P0 |
| LMS-05 | Assignments & submissions | exercise version, submission history, rubric, status, deadlines/timezone | P0 |
| LMS-06 | Teacher grading | feedback, rubric score, audit history, teacher course access only | P0 |
| LMS-07 | Coding lab | Monaco-like browser editor, Python/JS exercises; save draft; no arbitrary execution on API host | P0-design, P1-runner |
| LMS-08 | Auto-grader | isolated ephemeral runner, limited language allowlist, tests, deterministic result, CPU/memory/time/output/network quotas | P1 (blocked until runner security review) |
| LMS-09 | Progress | completion %, attempts, scored outcomes; role-scoped teacher/student view | P0 |
| LMS-10 | Tenant admin | teacher/course/student management and audit events | P0 |
| LMS-11 | Localization | id-ID default, time Asia/Jakarta, accessible UI and error strings | P0 |
| LMS-12 | Notifications | email/in-app optional; no unverified third-party integration | P2 |

## Primary learning journeys
1. Admin creates course→cohort→invites teacher and students.
2. Teacher publishes coding lesson with exercise and reference output/rubric.
3. Student opens lesson→edits code→saves draft→submits. Submission is immutable/versioned.
4. Teacher sees assigned submissions→grades/reviews→student sees feedback and updated progress.
5. When sandbox is approved: submission enters queue→runner processes with limits→result stored as untrusted output (escaped)→human override possible.

## Nonfunctional SLO targets (initial design targets, not measured)
- Responsive mobile/desktop, keyboard-navigation and WCAG 2.2 AA aim.
- Tenant isolation tests for every resource and file, RLS safety tests.
- API pagination, structured audit logs without secrets, daily backups and restore drill before public release.
- Defined max payload/upload limits; user-content virus scan if uploads are enabled.
- Availability and capacity targets to be finalized after server audit and expected concurrency.

## Explicit stop conditions
No public release without secure authentication, tenant isolation, validated database migrations, backup/restore test, negative security tests, independent reviewer signoff, and human go-live approval. No remote code execution without isolated runner review.
