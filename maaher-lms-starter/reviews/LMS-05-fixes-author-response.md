# LMS-05 — AUTHOR response F9/F10/F11

11 November 2026 WIB. Base84dd193; independent runtime review was54543a8..4a450d5.
Original Claude report remains on Mac; author relay records its scope/verdict.
These are implemented fixes with author evidence, **not independent CLOSED**.

| Finding | Change | Evidence and limits |
|---|---|---|
| F9 MEDIUM | Fixed CPU1000ms/wall3000ms, separate OS memory assertion with skipif; dense30k always runs five times uncached. Diagnostic calibration reports host margin, never disables/auto-expands caps. | Full347 Linux0skip; dense samples89.410–96.648ms, max-sample margin10.35. Three-lane preflight local and production-profile caps active; loaded diagnostic samples up to227.941ms. Slow reviewer Mac/i5 profile must still reproduce; no --deselect. |
| F10 MEDIUM | Finite tenant-aware FIFO/least-active scheduling instead of global free-slot race. One job/account,10 in-flight/tenant,16 pending/lane, fixed2+1 worker processes; expired/cancelled work releases capacity. | Real uvicorn/TCP, actual opaque sessions/RLS,2/4/8 actors≤1request/s, same/different tenants. Expanded probe:36 normal author saves+36 student drafts all200 while every attacker loop remains active; invalid attacks all422. Max author4648.78ms/student387.81ms, worst health p959.71ms. Capacity still finite; beyond caps returns429/503 safely. Multi-worker not tested. |
| F11 LOW | UTC astimezone overflow becomes validation422. Global RequestValidationError response bounds/normalizes type/loc/msg, omits input/ctx so lone surrogate does not crash error encoding or expose source/password. |14 boundary cases include4 overflow dates,9 raw surrogate paths and valid Unicode pair acceptance. No version append on invalid date. Parent lessons covered. Real Next/browser cases verify task/draft/date422 without reflecting sentinel input. |

F5/F6/F7 remain CLOSED within the original independent scope, including functional
legacy214s/86calls and Linux memory256MiB. New proof policy is semantic v3; signed
v2 accepted explicitly because URL/Markdown/control semantics are unchanged. No
revalidation/backfill/new assignment versions needed just for resource budget
change; old proof/key rotation invariants still tested. No unknown/unsigned proof
is implicitly certified. Real key retirement remains F12 operational note.

Full347 API/parser passed/0skip/2 existing warnings; after adding simultaneous
student HTTP coverage, queue suite5 passed again (no runtime change between runs).
17 real Chromium cases,12 scripts,16 Action, Next build/typecheck/compile/pip/starter
and audits pass (npm0; PyPI41pins0 findings/errors). Browser uses synthetic provider;
HTTP load fixtures insert trusted synthetic opaque sessions, not Auth0 login.
Detailed methods/raw numbers in LMS-05-fixes-performance.json and FIXES-HANDOFF.

F12 Draft downtime/retired-key version workflow/staff GET budget remains OPEN.
F3/N2/N3/N4/tenant pause and auth parent8941a79..4733526 remain separate. Not tested:
native Mac/slow reviewer machine, real Auth0/FIDO2, owner manual UAT, remote CI,
app image or multi-worker. No schema/provider/privilege changes or learner runner;
no merge/deploy. Preserve all historical reports/snapshots and old databases.
