# Add tenant-isolated course authoring and address review findings

Staff can create courses, manage ordered modules and Markdown lessons, and
publish/archive/restore through /courses. Only tenant admins and assigned active
teachers can use the management API; students wait for enrollment. Content edits
return a course to draft; assigning or removing a teacher preserves publication.
Role or membership status changes permanently revoke old assignments, including
concurrent changes; teachers cannot read archived courses or their lessons.

Migrations 0006/0007 enforce tenant keys, RLS, restricted definer ownership and
an authenticated mutation budget (60/minute per tenant/user). The server validates
active Markdown/resource HTTPS targets, hidden Unicode and trailing-dot hosts.
429 responses preserve unsaved editor content. Upgrade preserves course/auth
content and valid assignments; review known historical role cycles manually.
Downgrading past 0006 deletes courses and now refuses populated rollback without
explicit data-loss acknowledgement. Back up first; no UAT database rollback.

Validation: 244 API/unit (0 skip, 2 existing deprecation warnings), 12 scripts,
16 Action tests, 11 Chromium browser cases; production Next build/typecheck,
pip check, npm production audit 0 and PyPI snapshot 41 pins/0 findings. Tests
cover seeded migration preservation, guarded rollback, direct runtime SQL/RLS,
assignment/role races, Markdown and quota concurrency. OIDC tests use a signed
synthetic IdP, not the owner's real Auth0 tenant.

The owner reported successful Mac UAT on the earlier f38c231/0006. Their relayed
Claude review reported seven LOW and no BLOCKER/HIGH/MEDIUM. The author addressed
all seven; re-review and Mac UAT of 0007 are pending. CI remote and application
Docker image build are unverified. Branch is stacked on unmerged auth parent
4733526, whose full independent review remains pending. No merge/deploy or
production approval. See LMS-02-HANDOFF.md and reviews/LMS-02-author-response.md.
