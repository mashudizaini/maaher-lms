# LMS-05 — owner relay of independent Claude review

11 November 2026 WIB. AUTHOR record of the owner's chat summary, not a new
independent review. Original `reviews/LMS-05-claude.md` exists on the Mac; it is
absent from this cloud checkout and must remain unchanged.

Verdict **APPROVED_WITH_NOTES only dev/UAT synthetic small–medium courses**.
Reviewed `54543a8..4a450d5`, schema0012; no tracked Mac changes and no documentation
commit after4a450d5 available locally. Cloud84dd193 is six documentation files,
not part of that review; its content is author-verified only. No auth-parent or
production approval. Tests used a new reviewer container/database.

- F5 publish CLOSED: own1500×29KB corpus, real uvicorn/TCP2.1–2.5s vs80s,
  concurrent writers all200, health p95 during publish about11ms.
- F5 legacy validation functionally CLOSED:1500 lessons,86 calls/214s, no implicit
  certification. Draft availability and retired-key costs remain operational notes.
- F6 CLOSED:22k/30k forbidden controls422 without child restart; safe30k frames pass.
- F7 CLOSED on Linux:256MiB RLIMIT_AS in3 lanes, local and production profile;
  native Mac remains WARN by design.
- **F9 MEDIUM**: dense valid30k `*a* `×7500 median266ms on i5-7360U/Docker,
  above250ms CPU. The deselected test failed on document validation, not its
  memory assertion. Native Mac150ms but similar document intermittently422.
  Split OS capability test with skipif; recalibrate CPU margin. CI remote not run.
- **F10 MEDIUM**: shared global slots;2/4/8 actors at most1 save/s caused ordinary
  simulated saves429 at22/28/48%. Reviewer used ParserPool threads, not HTTP sessions.
- **F11 LOW**: extreme date+offset UTC overflow and lone surrogates in instructions/
  student draft yielded500; parent lesson has the same class of encoding failure.
- **F12 LOW/INFO**: legacy validation requires Draft and pauses students, retiring
  proof keys needs assignment versions, staff GET lacks ingress budget. Still open.

Reviewer verified SQL/session tenant/peer/teacher isolation, trigger-normalized
spoofed submissions, immutable versions/submissions, server deadline/timezone,
12 parallel submits at cap3 giving exactly3 successes/no deadlock, authority before
locks, new INVOKER functions and unchanged18 definers. Seeded upgrade10→12 parent
hashes preserved; wrong/base downgrade refused; ack rollback restored0010 schema
apart from dropped-column tombstones. Next production BFF87/87 passed.

Not tested by reviewer: CI remote, real Auth0/FIDO2, Playwright, app Docker image,
multi-worker or owner UAT. F3/N2/N3/N4/tenant pause and full auth8941a79..4733526
remain separate/open. Repo/.env/Auth0/old DB and owner API PID were preserved;
only probe processes stopped, reviewer container stopped not deleted. No merge/deploy.
F9/F10 must close before depending on Linux CI success or many writers. AUTHOR
fixes below require fresh independent review, not self-assigned CLOSED status.
