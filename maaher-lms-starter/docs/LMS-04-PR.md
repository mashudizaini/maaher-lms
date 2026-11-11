# Add revision-aware student completion and bound learning resource costs

Students can mark lessons complete/incomplete, resume the first unfinished lesson,
move to the previous/next lesson and retain progress after reload. Editing lesson
content/resources requires a fresh completion; title/reorder alone preserves it.
Only the active enrollment owner on a published course can read/write progress.
Completion is self-reported learning state, not grading or certification.

The LMS-03 review found expensive per-row RLS and parser CPU contention. Migration
0009 uses statement-scoped access InitPlans and separates SELECT from FOR ALL
write policies. Four helpers have a dedicated NOLOGIN/NOBYPASS read-only owner
with minimal column grants. The parser runs in a bounded child with CPU/wall
limits and nonblocking busy429, without DB/Auth0 env. Existing URL policy remains.

Local same-data SQL benchmark: student1500 lessons 26079→18.08ms; new outline
ASGI request including progress133.03ms. Actual uvicorn CPU load probe: health
p95 1.71ms baseline→11.31ms with8 saves; original account budget52/60 used.
Invalid-complexity and busy saves reject422/429. These are local synthetic results,
not production SLOs. Methods/JSON: reviews/LMS-04-author-response.md/performance.json.

Migration0010 adds revision/progress and bounded learning requests, preserving
identity/course/enrollment. Populated progress rollback requires explicit loss
ack after an exclusive guard lock; tested only in disposable databases. API/MFA/
OIDC credentials and configuration are not changed; no learner execution.

Validation: 291 API (0 skip,2 existing deprecation warnings),12 scripts,16 Action,
15 Chromium browser cases, build/typecheck/pip/compile, npm0 and PyPI41pins0.
Branch stacks on unmerged4870287; independent review and Mac UAT pending. Auth
parent full review and old N2/N3/N4 remain open. No merge/deploy approval.
