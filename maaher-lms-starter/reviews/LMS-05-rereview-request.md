# LMS-05 independent re-review — F9/F10/F11

AUTHOR has implemented fixes; do not turn author tests into independent approval.
Read CLAUDE.md, AGENTS.md, reviewer skill and original reviews/LMS-05-claude.md on
Mac, plus its author relay. Preserve every prior report unchanged.

Base **84dd193**, reviewed runtime **4a450d5**, branch
feat/LMS-05-assignments-submissions. Review84dd193..HEAD and actual local changes.
If84dd193 unavailable, fetch normally or use4a450d5..HEAD and record that six
intervening files are documentation only after verifying Git objects. Never
silently use main...HEAD to approve auth parent. Verify SHA/schema/working tree.
Original patch/manifest snapshots are historical4a450d5. New fixes patch/manifest
are based84dd193; neither overwrites old evidence.

Read ADR-010, FIXES-HANDOFF, fixes-author-response and fixes-performance.json.
Use NEW EMPTY disposable databases/own containers; no owner UAT DB or migrations
on populated old DBs. Do not read/print .env/keys, alter Auth0 or stop owner servers.

- **F9:** valid30k dense document always executes in its own test, repeated with
  scoped cache misses. Only RLIMIT_AS assertion is Linux skipif, never --deselect.
  Reproduce on the slow reviewer Mac/Linux profile where266ms exceeded250ms.
  Budget now1000ms CPU/3000ms wall, fixed hard caps; preflight --calibrate reports
  actual samples/margins without changing caps. Verify real CPU timer and dense
  content, not just a mocked/Event workload. Unsupported local memory remainsWARN,
  production fail-closed. Check new v3 proofs explicitly accept only semantic-
  equivalent signedv2, preserving old courses/versions without automatic trust.
- **F10:** inspect bounded tenant-aware queue, one in-flight/account/lane,
  max10/tenant,16 pending/lane and fixed2+1 workers. Verify least-active tenant,
  FIFO account order, sequential completion race, expiry/cancellation/shutdown,
  no per-principal process/cache growth. Cross-worker totals are not verified.
  Test actual HTTP/TCP sessions2/4/8 actors≤1 save/s, same and different tenants,
  normal author plus student draft. Ensure all attacker loops are active for
  each normal save. Record200/422/429/503, latency/wait/health and unaltered
  budgets, not a thread-only model or only percentages. Overload beyond finite
  capacity is allowed to fail safely; no general no-DoS claim. Review threadpool/
  queue deadlines relative to BFF15s and behavior when CPU is constrained.
- **F11:** raw JSON lone surrogates in task/rubric/starter/draft/lesson/unknown
  key must give safe422, no input/ctx reflection, valid Unicode still accepted.
  Extreme offset dates overflow UTC safely422 before writing a version.
  Inspect common RequestValidationError handler, including auth error regression
  and bounded output/UTF8 normalization. No auth policy change is intended.

Run all old tenant/peer/teacher/SQL/deadline/immutable/race/migration/proof/browser
regressions as feasible. CPU/HTTP probes use synthetic data/trusted parser, never
learner execution. No schema/backfill needed for fixes; do not rerun setup on
existing UAT. Keep original reviewer containers/data; stop only own new probes.
Save NEW `reviews/LMS-05-claude-rereview.md`, exact commands/results and proven
findings/path:line, F9/F10/F11 status and untested limits. F12 remains operational
open; F3/N2/N3/N4/tenant pause and full auth8941a79..4733526 separate. No real
Auth0/FIDO2/owner UAT/CI/image/multi-worker claim unless actually tested.
No merge/deploy or changed source; return findings to AUTHOR if needed.
