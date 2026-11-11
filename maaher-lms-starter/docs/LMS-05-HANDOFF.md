# LMS-05 — author handoff

11 November2026 WIB. Branch **feat/LMS-05-assignments-submissions**, base
**54543a8f63066a44303ab577a70738e614ec226a**, runtime parent5b675e6, schema
**0012_assignments**. Development implementation; independent review/Mac UAT
pending. No merge/deploy. Full auth parent8941a79..4733526 remains unreviewed.

## Latest — follow-up F9/F10/F11

Pemilik melaporkan review independen4a450d5: F5/F6/F7 Linux CLOSED dalam scope
sintetis terbatas, F9/F10 MEDIUM dan F11 LOW baru. Perbaikan author kini ada di
[LMS-05-FIXES-HANDOFF.md](LMS-05-FIXES-HANDOFF.md), dengan347 tes API/parser,
17 browser dan uji HTTP banyak akun/siswa. Baca itu untuk budget CPU/antrean/status
terbaru; angka250ms dan hasil325 di bawah adalah snapshot historis4a450d5.
F9/F10/F11 masih menunggu review ulang. F12/auth parent/temuan lama tetap terpisah.

## Update pemilik — 11 November 2026 WIB

Pemilik melaporkan38 tes API/parser dan2 browser lulus di Mac, preflight Auth0
13 PASS. Native macOS tidak memiliki memory cap; satu assertion khusus Linux
dikecualikan secara eksplisit. Browser memakai provider sintetis. UAT manual
Auth0 nyata belum dilakukan. [Catatan bukti dan batasnya](LMS-05-MAC-VALIDATION-20261111.md)
membedakan hasil yang dilaporkan dari325 API/17 browser cloud. Laporan asli hanya
ada di Mac; source SHA/schema/command/pengecualian perlu diperiksa oleh reviewer.
Tidak ada kesimpulan zero-SKIP atau full-suite Mac dari ringkasan ini.

Berikutnya review independen melalui reviews/LMS-05-review-request.md dan UAT
manual pemilik. Tidak perlu mengulang setup/migrasi hanya untuk review. Patch dan
manifest tetap snapshot4a450d5; cek hash terhadap blob commit itu, lalu tinjau
pembaruan dokumentasi berikutnya. Source aplikasi tidak berubah dalam update ini.

## Result

Staff `/assignments`: create lesson-bound exercises with validated Markdown,
Python/JavaScript/text language, plaintext starter,1–10 rubric criteria total100,
max attempts1–20, optional aware deadline displayed/entered WIB and allow-late.
Save appends immutable version, preserves published pointer until explicit publish.
Unpublish/archive blocks new work without deleting history; restore is Draft.
Staff can inspect submissions only in authorized courses. Max100 tasks/course,
100 versions/task. Referenced lesson/module delete returns409, preserving history.

Student `/work`: active enrollment on published course, lesson-filter link from
/learn, saved own draft with optimistic revision, immutable submitted snapshot,
attempt number/server timestamp/status and history with original instructions,
rubric and deadline. Version2 publish retains version1 draft text and requires
explicit acknowledgment before saving onto2; stale submit409. Same UUID request
is idempotent. Concurrent distinct requests cannot exceed the version's total
attempt cap across versions. Deadline/late and source snapshot enforced in an
INVOKER DB trigger as well as scoped API. Source never runs anywhere.

Four new FORCE RLS tables with composite parent/owner FKs, no UPDATE/DELETE grants
on versions/submissions, immutable triggers even for ordinary owner DML. Existing
18 definers/reader permissions unchanged; no new role/secret/dependency. Staff
writes60/min, student/work reads+writes120/min, body256KiB, explicit BFF paths,
queries/methods/Origin and safe cookie/header handling. Parent session/MFA flows
unchanged. Course archival/enrollment revoke denies student history access;
hidden assignment history remains own-readable while enrollment/course valid.

## F5/F6/F7 response

F5: saved signed proofs bind policy+tenant/object/revision+exact content/resources.
Lesson edits invalidate proof; API signs only validated exact stored data, CAS
write guards against concurrent changes. Publish streams/verifies proofs and does
no parser work. Legacy missing/invalid proof409; explicit Draft→Periksa materi
lama (50 rows, ~2s+one bounded parse/cursor), separate maintenance process. Valid
proofs skipped. Two bounded interactive processes remain independent. Existing
published legacy material remains; no automatic certification/unpublish.

F6: forbidden controls and invalid UTF8 reject beforeIPC; frame cap262144 covers
safe30k escaped/emoji text. Worker independently enforces controls/frame limits.
F7: reported memory cap capability, fixed warning+preflight in local/test when
unsupported,503 outside them; CPU250ms/wall2s vs prior120ms/1.5s. Linux reports
256MiB; absent-cap warning/failure simulated through real IPC. Darwin not tested
here and unsupported cap must remain WARN. Sizing multi-worker memory/CPU remains
an operational gate. Review may still identify residual availability risks.

Details: ADR-009, reviews/LMS-05-author-response.md and performance.json. Parent
Claude F1/F2-health CLOSED are separate independent conclusions; author fixes for
F5/F6/F7 still await independent review. F3,N2,N3,N4/tenant pause remain open.

## Validation

Linux Python3.12.14, PostgreSQL16.15, Node24.22.1, real Chromium/Next production;
all feature fixtures synthetic, API non-owner/non-BYPASSRLS with separate auth/
operator/mail/maintenance roles. Commands run from application root using the
existing isolated venv and six TEST_* role URLs aimed at NEW EMPTY maaher_test_
databases. No .env/secret/owner-Mac DB was read or changed.

| Check | Actual result |
|---|---|
| `python -m pytest apps/api/tests -x -q -s` | **325 passed**,0 skip,2 existing deprecation warnings,315.34s |
| Existing parent |291 cases retained; new task/proof/migration/race/UTC cases included |
| `python -m pytest -q scripts/tests` |12 passed,0 skip,0.11s |
| `node --test infra/auth0/*.test.cjs` |16 passed,0 skip |
| Browser `--oidc --dev-totp --assignments` |2 passed,15.4s, final UI incl lesson filter |
| Browser learning / enrollment / courses |2 /2 /2 passed; final learning9.8s, courses14.3s |
| Browser auth / OIDC FIDO2 / dev-TOTP |7 /1 /1 passed, total17 unique browser cases |
| Next typecheck/build / compileall / pip check / starter / source diff check (generated patch excluded) |PASS |
| npm production audit / PyPI runtime advisory snapshot |0 vulnerabilities /41 pins,0 findings/errors |
| Parser capability preflight |3 Linux processes PASS256MiB; metadata only, no secrets |

Browser command harness `python scripts/test-lms01-browser.py` uses a new empty
DB for each mode; --oidc selects signed synthetic provider, --dev-totp its local
assurance. These are not real Auth0/security-key/manual UAT results. Assignment
browser uses two separate sessions, real staff UI authoring and learner save/
submit/reload/version-ack/history/cap/revoke; script text remains escaped. BFF
negative routes/Origin/query/body tests included. Unit/API tests include peer/
tenant/directSQL, SQL spoofed source/time/status, version immutability, role and
teacher assignment revocation, stale tabs, attempts races and timezone offsets.

First full run:323 passed/0skip/2 existing deprecation warnings,329.09s. After a
UTC proof canonicalization regression was added, next run failed1/182 passed:
the old test assumed30k '[' always exceeds the now250ms CPU budget. It sometimes
finished sooner and correctly accepted plain valid Markdown. The test now verifies
the actual timer with a test-only CPU-loop worker (not Event), while real TCP
pressure still uses actual adversarial CommonMark with an always-invalid URL
prefix so it cannot accidentally save/cache if it completes underbudget.
No production parser behavior was weakened to satisfy the assertion. The final
suite also covers10 create-task vs delete-lesson races, serialized on the parent
course so FK races return201/409 or404/200 instead of500. Final full run **325 passed**,0 skip,2 existing warnings in315.34s after
these changes; no test was skipped or xfailed.

F5 first full:1500 unique29k-character lessons (ASCII29KB), publish1127.12ms,
8 other-course saves every0.5s all200, health p95 after publish/during writer4.81ms.
Fixture validates each exact document with trusted raw CommonMark before signing;
setup/validation time excluded. Not an80s migration promise: legacy backfill is
still a one-time bounded cost. Final run: publish **757.63ms**, eight other-course saves all200, health sampled
after publish/during writer p951.81ms. Real CPU load health baseline1.43ms,
2 writers2.77ms,8 writers8.18ms,sequential1.93ms; responses422/429,52/60 budget.
Current student SQL1500 lessons23.31ms vs reconstructed21985.89ms; catalog451
15.31ms; outline incl progress ASGI116.91ms. See methods in performance.json.

F1 regression reconstructs old0008 SELECT/FORALL policies temporarily in its own
DB, restores them, measures same-data SQL/ASGI and same-connection prepared revoke.
F2 health uses real uvicorn/TCP and original52/60 account budget, no Event/cache
shortcut. Exact JSON/methods in performance.json. Shared-host local figures, not
production SLO, real Auth0, native Mac, image or multi-worker verification.

## Upgrade / rollback

Use migration credential, backup confirmed synthetic UAT DB first. Upgrade
0010→0011→0012 leaves old identity/auth/keys/material/revision/progress/enrollment
unchanged, proofsNULL for legacy, empty task tables. No privilege elevation/new
role needed. `verify-auth0-local.py` accepts0011/0012; live Auth0 preflight not run
in cloud because real tenant credentials/bindings belong to Mac.

0012 downgrade exclusively locks all four tables. Populated history requires exact
`-x allow_assignment_data_loss=yes`; wrong/no flag raises before drops. Offline
SQL contains lock+guard. Acknowledged rollback deletes all tasks/versions/drafts/
submissions and is tested ONLY on own disposable DB, preserving material/progress/
enrollment/auth; re-upgrade does not restore deleted task history.0011 downgrade
drops proof only. Do not use destructive rollback merely to run tests or update.
Parent progress/course/enrollment guards remain; old offline0006 N2 still open.

## Preserved evidence and next step

Final full DB `maaher_test_lms05_releasefinal_20261111`; prior full2/release,
assignment/proof/dev/full attempts are retained. Browser DBs browserauth/fido/totp/
courses/enrollment/learning/browserassignment and final browserassignmentsfinal/
browserlearningfinal all use prefixmaaher_test_lms05_ and suffix_20261111.
Migration creates random maaher_test_lms05_migration_, plus parent migration
fixtures' old prefixes on new empty databases. No databases are dropped by this
work. Only owned cloud container maaher-cloud-review-20261109, port127.0.0.1:32776,
was started for tests and is stopped at completion; files/databases retained.

Original reviews/LMS-01-claude.md SHA256 remains
004a19183409b152d0947ab6f5b99af2000d9dd3324c9a2c77ea66a4106032ce. Prior patches/
manifests/Claude reports are historical and untouched. New LMS-05 manifest/patch
base54543a8 exclude themselves, verify current files and baseline apply check.

Follow LMS-05-MAC-SETUP.md, preserve reports/.env/keyring/Auth0/bindings/data,
backup+forward upgrade and real owner synthetic UAT. Then independent Claude
review via reviews/LMS-05-review-request.md. Full auth review remains separate.
Human alone decides any merge/release. GitHub GraphQL PR access returned Forbidden;
source branch and review-ready PR description are provided, no PR falsely claimed.
No direct access or changes to the owner's Mac, Auth0 or Timedoor; no merge/deploy.
