# LMS-05 review fixes — Mac verification

11 November 2026 WIB. Branch feat/LMS-05-assignments-submissions. Base84dd193,
reviewed implementation4a450d5. Latest source adds F9/F10/F11 fixes; schema remains
0012_assignments. See ADR-010 and LMS-05-FIXES-HANDOFF.md. Original review and Mac
reports, patch/manifest snapshots and existing databases must be preserved.

**Update:** pemilik melaporkan source5131f2c sudah aktif, build/restart tanpa
migrasi,343 PASS/1 SKIP capability Linux/0 deselected,2 browser PASS dan fairness
berhasil. [Batas bukti dan selisih3 kasus](LMS-05-FIXES-MAC-VALIDATION-20261111.md).
Pertahankan laporan asli reviews/LMS-05-fixes-mac-validation-20261111.md. Berikutnya
review independen; periksa source/schema secara read-only. Langkah setup di bawah
untuk checkout baru/kebutuhan yang belum selesai, bukan perintah mengulang setup
Mac yang telah berhasil. Jangan menyentuh DB lama untuk menyamakan jumlah tes.

1. Inspect active Git root, status, source and schema. Fetch source normally;
   use an isolated worktree if needed. Preserve untracked reviews/LMS-05-claude.md
   and LMS-05-mac-validation-20261111.md. Do not reset/clean/stash automatically,
   apply old patches, or assume local4a450d5 includes84dd193 documentation.
2. Preserve .env/keyring/Auth0/Action/bindings, database URLs, volumes and old
   databases. No new config secret/dependency/DB role/schema or migration is
   needed for these fixes. Do not rerun downgrade/upgrade to validate parser work.
3. Rebuild/restart development API/web using the existing working workflow.
   Existing v2 lesson and immutable assignment proofs remain valid; do not
   revalidate every old course or create new assignment versions for this update.
4. In the API environment run `python scripts/parser-preflight.py --calibrate`.
   Expected CPU1000ms/wall3000ms. Record all five CPU samples and margins per lane.
   Mac cap can be WARN_MEMORY_UNAVAILABLE; Linux/container must report active
   256MiB. Margin below2 remains WARN_LOW_MARGIN, not a reason to disable caps.
   Report valid-document422 or CPU failures as FAIL; do not hide them with
   --deselect or exclude a combined test.
5. Only the separate test `test_linux_memory_capability_only` uses platform
   skipif. Always run `test_dense_valid_30k_repeated_without_cache`, control/frame,
   CPU timer and missing-cap behavior tests. On Mac the Linux capability case can
   be SKIP while the others must still execute; report exact PASS/FAIL/SKIP counts.
6. Full tests/browser/benchmarks use NEW EMPTY disposable maaher_test_ DBs owned
   by this session. All role URLs must point to the same new DB. Fixtures perform
   destructive acknowledged rollbacks and temporary legacy RLS reconstruction:
   never run them on existing UAT/real DBs. Preserve all old containers/databases.
7. Reproduce test_parser_fairness.py using real uvicorn/TCP sessions,2/4/8 actors
   ≤1 request/s each, ordinary author plus student draft, same/different tenant.
   Record all statuses/latencies/health and actual account budgets, not just a
   ParserPool thread model. Waiting can take several seconds; capacity/timeout
   remains finite. Test concurrency and per-account/tenant admission separately.
8. Run validation_boundaries and old parent regressions. Extreme offset dates,
   lone surrogates in task/draft/lesson/unknown key must return UTF8-safe422 and
   avoid reflecting input/ctx. Genuine Unicode must still save. Browser assignment
   suite now includes invalid date/surrogate through Next production BFF.
9. Actual Auth0/manual UAT remains the owner's action, separate from synthetic
   browser provider tests. Leave staff MFA/profile/binding unchanged; never capture
   OTP/token/session or print secrets. Do not claim real Auth0, CI, app-image,
   multi-worker or Linux memory-cap tests unless actually performed.

Save a NEW `reviews/LMS-05-fixes-mac-validation-20261111.md` with commands, SHA,
schema, platform, counts, exclusions and limitations. Then independent reviewer
uses reviews/LMS-05-rereview-request.md. F9/F10/F11 author fixes await re-review;
F12/full auth/older findings remain separate. No merge/deploy/runner.

```text
Ambil branch feat/LMS-05-assignments-submissions dari mashudizaini/maaher-lms.
Baca AGENTS.md, docs/LMS-05-FIXES-HANDOFF.md dan LMS-05-FIXES-MAC-SETUP.md.
Pertahankan perubahan lokal, semua laporan Claude/Mac, .env/keyring/Auth0/binding,
dan semua DB/volume lama. Ini tidak memerlukan migrasi; rebuild/restart API/web.
Jalankan parser-preflight.py --calibrate; rekam CPU1000ms/wall3000ms dan margin
nyata. Hanya tes capability Linux yang boleh SKIP sesuai skipif; jangan --deselect
tes kontrol/frame/dokumen valid. Semua tes otomatis/benchmark harus memakai DB
kosong baru terpisah. Uji regresi F9/F10/F11 termasuk HTTP lintas/sama tenant,
penulis dan draf siswa saat beban2/4/8 akun, input tanggal/surrogate422, browser
serta parent. Simpan hasil aktual di reviews/LMS-05-fixes-mac-validation-20261111.md.
Jangan ubah MFA/Action, reset/downgrade, hapus DB/container, merge atau deploy.
```
