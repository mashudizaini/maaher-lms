# LMS-05 — Mac setup and owner UAT

Branch **feat/LMS-05-assignments-submissions**, base54543a8, schema **0012_assignments**.
Stacked on LMS-04. Original folder may be `/Users/mashudi/Downloads/AiMZ-Corp Project/maaher-lms-starter`
or the later checkout `maaher-lms-auth0/maaher-lms-starter`; confirm active Git/app
root first. Never use the previously mistaken govriskid path.

1. Read Git status, running source/head and schema. Fetch the branch normally;
   use a separate worktree if local source conflicts. Preserve all untracked
   Claude/Mac reports. Do not reset, clean, stash automatically or reapply old
   patches. Parent54543a8 is documentation only over runtime5b675e6.
2. Preserve .env, existing AUTH_ENCRYPTION_KEY/KEYS/active ID, separate DB URLs,
   Auth0 dev-TOTP configuration, bindings, volumes and all old databases. There
   is no new secret/dependency/Auth0 Action. Do not print their values or copy
   secret files into commits/review archives.
3. Confirm the intended DB contains only synthetic development/UAT data. Back
   it up using the existing secure local workflow. Upgrade forward0010→0011→0012
   with the migration credential: `python -m alembic -c apps/api/alembic.ini upgrade head`.
   Migration adds proofs and empty task tables, preserves existing data. No new
   role/membership/privilege elevation is required. Never use API credentials as
   owner, and never downgrade/reset to make tests pass.
4. Rebuild/restart API and Next development services with the prior working
   workflow. Check head0012. Existing Auth0 preflight now accepts0011/0012; run
   it through the established secure env loader, without exposing secrets.
   Login admin remains the owner's action; do not capture OTP/session/token.
5. Run `python scripts/parser-preflight.py` inside the configured API environment.
   Linux should report3 PASS/256MiB. Native macOS can report WARN_MEMORY_UNAVAILABLE;
   do not count it as an active memory cap. Use local synthetic data only, or
   verify the Linux API container where RLIMIT_AS is active. APP_ENV outside
   local/test rejects unsupported caps. Do not loosen that behavior.
6. Open `/assignments` for staff and `/work` for a synthetic student in a separate
   browser profile, enrolled in a published course. `/courses`, `/auth` and a
   lesson's Tugas pelajaran link also lead to these pages.

## UAT checklist

- Staff: select course/lesson; create title/instructions, Python/JS/text, starter,
  rubric total100, attempts2, optional future deadline in **WIB**. Save Draft,
  publish. Student sees the published version and matching WIB deadline.
- Student: edit plaintext answer, save draft, reload and reopen task. Submit with
  confirmation. Check attempt1, submitted timestamp, immutable code/note and old
  version instructions/rubric in history. No code is executed.
- Staff: save version2 with changed instructions/rubric. Student still sees1
  until explicit publish. After publish, its old draft remains; submit is blocked
  until student acknowledges and saves on version2. Prior submission still shows1.
- Send second attempt; third is denied at cap. Repeating the same request UUID
  returns the same submission; a new saved draft is the normal UI path for another
  attempt. History does not follow later edits to draft/code/rules.
- New synthetic late-policy task: deadline in past with allow-late=false rejects
  submit409; a newly published version with allow-late=true accepts and marks
  Terlambat using database time. Do not change old immutable versions with SQL.
- Teacher assigned courseA cannot inspect courseB; studentB cannot read studentA
  draft/submission. Revoke enrollment: active task/history read and write stop.
  Explicit reactivation can restore history; course/cohort restore alone does not
  re-enroll. Unpublish/archive task hides new work, preserves own history while
  course/enrollment remains valid. Staff can read submissions, not edit answers.
- A lesson/module referenced by a task cannot be deleted (409). Course archive
  is the preserving lifecycle. Tenant disable remains the parent pause behavior.
- Logout each session; report source/schema/provider and actual manual results.

## Legacy course material and F5/F6/F7

New lesson saves are validated and signed automatically. Migration does not sign
old content. Existing published lessons stay available. Before re-publishing an
unsigned course: explicitly Jadikan draf → Periksa materi lama → Terbitkan. The
batch button commits progress and follows cursors. Correct invalid links/controls
if409; wait/retry on429 without discarding editor. Validation has a one-time cost;
publish subsequently verifies proofs without using parser slots. Retired key or
policy invalidates proofs; keep old keys during rotation and revalidate as needed.
Assignment versions are immutable; save a new version if its proof becomes stale.

Run full pytest, browser harness and benchmarks **only against new empty disposable
maaher_test_ databases**, with all restricted role URLs pointing to the same DB.
Fixtures perform acknowledged rollback and old RLS policy reconstruction. Do not
point them at existing UAT/real data. Never delete old DBs/containers to start.

The cloud benchmark excludes one-time fixture validation, uses Linux and one API
worker. Reproduce F5 with a writer every0.5s, plus actual CPU health tests on a new
DB if feasible. Preserve measured failures and limitations; do not assert native
Mac memory support, real Auth0 student login, Docker image, CI or manual UAT from
synthetic browser results. Store `reviews/LMS-05-mac-validation-20261111.md`.

## Ready-to-run Codex CLI prompt

```text
Lanjutkan setup/UAT LMS-05 di repo mashudizaini/maaher-lms, branch
feat/LMS-05-assignments-submissions. Baca AGENTS.md, docs/LMS-05-HANDOFF.md,
docs/LMS-05-MAC-SETUP.md dan ADR-009. Periksa checkout/source/schema aktif;
ambil source tanpa menimpa perubahan lokal atau laporan Claude/Mac saya.
Pertahankan .env/keyring/Auth0 dev-TOTP/binding, seluruh DB/volume/container lama.
Backup DB development yang dipastikan sintetis head0010, upgrade maju ke0012
memakai credential migrasi terpisah, rebuild/restart API/web. Jangan cetak secret,
ubah MFA/Action, beri privilege API, reset/downgrade atau deploy.
Jalankan parser-preflight; laporkan memory cap PASS/WARN yang nyata, jangan
anggap warning native Mac sebagai cap aktif. Jalankan Auth0 preflight existing.
Siapkan /assignments dan /work dengan siswa sintetis enrolled serta dua sesi
terpisah; saya login Auth0 sendiri. Uji versi tugas/rubrik/deadline WIB, save draft,
submit/reload/riwayat immutable, batas attempts/late, publish versi baru dengan
ack draft lama, peer/teacher/tenant isolation, revoke dan logout. Materi lama harus
Draft→Periksa materi lama sebelum republish; jangan auto-sign konten tanpa validasi.
Tes otomatis/benchmark hanya pada DB kosong baru terpisah milik sesi ini.
Catat actual commands/counts/source/schema/provider dan FAIL/SKIP/NOT TESTED di
reviews/LMS-05-mac-validation-20261111.md. Pertahankan semua data. Tidak merge/deploy.
```
