# Add cohort enrollment and published student access

Admins can organize a course into cohorts, enroll active tenant students, move
students, revoke access and explicitly reactivate it. Students can read published
materials through /learn only while their membership, enrollment and cohort are
active. Teachers can read assigned active rosters; students cannot read peers.
Archive or role/status changes permanently revoke enrollment; restoring a parent
does not restore access. Ordinary draft/unpublish pauses read until republished.

Migration 0008 adds FORCE RLS, tenant/parent keys, unique enrollment lifecycle,
restricted definer helpers and triggers. API lock order and optimistic versions
protect concurrent enrollment/role changes. A populated downgrade refuses to
remove cohort/enrollment data without explicit data-loss acknowledgement after
backup; course content and identity remain intact. Upgrade does not auto-enroll.

The shared mutation ingress now uses public ASGI receive/replay instead of
request._body. CommonMark validation moves to synchronous worker endpoints;
quadratic parser CPU cost remains a documented capacity concern. Auth sessions,
MFA, Auth0 Actions and provider configuration are unchanged.

Validation: 272 API/unit (0 skip, two existing deprecation warnings), 12 scripts,
16 Action tests and 13 real Chromium browser cases; build/typecheck, npm audit 0
and PyPI runtime snapshot 41 pins/0 findings. Details: LMS-03-HANDOFF.md. Cloud uses PostgreSQL 16,
separate non-owner runtime roles, real Chromium and a signed synthetic IdP.
UAT Mac, real teacher/student Auth0, CI remote, application image build and
independent LMS-03 review are pending. Auth parent's full review remains open;
LMS-02 APPROVED_WITH_NOTES applies to fe54142 only. No merge/deploy approval.
