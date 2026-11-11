# LMS-05 — author response to LMS-04 residuals

Base54543a8; source runtime parent5b675e6, independent reviewer facts in
[LMS-04 relay](LMS-04-review-relay-20261111.md). These are author fixes, **not an
independent CLOSED verdict**. All tests use synthetic data/new disposable DBs.

| Finding | Author change | Evidence / limits |
|---|---|---|
| F5 MEDIUM | Signed exact revision/content/resource proofs on save; publish performs verification only. Legacy validation explicit/batched on dedicated lane;2 interactive slots. | Real uvicorn/TCP1500×29KB publish1127.12ms while8 writes every0.5s all200 in first full323 run. Unique fixture documents parsed before signing; setup cost excluded. No implicit legacy certification. Final325 run:757.63ms,8 writes200; JSON in performance.json. Throughput on Mac/multi-worker still unverified. |
| F6 LOW | Reject forbidden controls beforeIPC; bound frame262144; independent child check. |22000/30000 controls reject without changing child PID; tab/CR/emoji and valid emphasis30k allowed. API assignment422; parent course matrix runs. |
| F7 LOW/INFO | Child reports actual cap; fixed warning+JSONpreflight for unsupported local cap; non-local fail503. CPU250ms/wall2s. |3 Linux child cap reportsPASS256MiB. Missing-cap local warning/production failure simulated through real IPC. Darwin not actually reproduced by author. Budget250 validated on dense valid30k plus adversarial TCP load; not a production sizing claim. |

F1/F2-health CLOSED status remains the reviewer's parent verdict. Their regression
benchmarks continue to run. F3, N2/N3/N4 and tenant pause are unchanged; auth parent
8941a79..4733526 still needs separate full review. Nothing here certifies SMTP,
production FIDO2/operator recovery, backup drills, TLS/edge rate limits or release.

New assignment workflow and negative SQL/tenant/peer/version/concurrency cases are
listed in docs/LMS-05-CHECKLIST.md. All new DB functions are INVOKER; existing18
SECURITY DEFINER functions/grants are unchanged. No code runner or new dependency.
