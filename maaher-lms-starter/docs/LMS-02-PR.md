# Add tenant-isolated course authoring

Staff who could sign in previously had no course management screen. Admins can
now create courses, assign active tenant teachers and manage ordered modules and
Markdown lessons through /courses. Assigned teachers can edit their courses;
students and unrelated tenants cannot use the management API. Edits return a
published course to draft, and concurrent changes use version checks.

Migration 0006 adds four FORCE-RLS tables with composite tenant keys and one
restricted role-lookup definer. Markdown HTML is skipped, external images become
manual HTTPS links, and no learner code or server asset fetch is executed.
Course archive preserves content; explicit module/lesson deletion is permanent.
Downgrade to 0005 deletes all course data. Back up before migrating.

Validation: 198 API/unit, 12 script tests, 16 Action tests, 11 Chromium browser
cases; typecheck/build and npm production audit pass. Provider tests use a signed
synthetic IdP. Owner-reported Auth0 dev-TOTP UAT belongs to the parent branch.
The owner now reports successful Mac course UAT on f38c231 after backup/0006
upgrade, local 198 API, 12 scripts, 16 Action, 2 browser and 13 preflight PASS.
See LMS-02-DEV-UAT-20261110.md; remote CI and independent Claude review remain pending.

Stacked branch: base feat/LMS-01-auth0-development at 4733526. The authentication
parent remains unmerged and needs its own independent review. This change does
not approve production access or deployment. Details: LMS-02-HANDOFF.md.
