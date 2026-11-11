# Review independen LMS-04 + re-review F1/F2

Author Codex menyiapkan request ini, bukan laporan Claude. Branch
feat/LMS-04-student-learning, base **4870287** (runtime parent110c9be).
Target source runtime **5b675e6**, review **4870287..5b675e6**;
110c9be..4870287 hanya dokumentasi, diverifikasi cloud.
Laporan asli LMS-03 tetap berada di Mac. Jangan menimpa laporan atau catatan UAT.

Baca CLAUDE/AGENTS, workflow, PROJECT-SPEC, ARCHITECTURE, skill security review,
ticket LMS-04, ADR-008, LMS-04-HANDOFF/CHECKLIST, relay LMS-03, author-response dan
performance.json. Source/test/CI snapshot pada manifest/patch; diff Git utama.

Pemilik kini melaporkan benchmark Mac (DB baru): query student1500
31.471,73→75,50ms dan health p95/8 saves13,41ms, browser provider sintetis.
Baca docs/LMS-04-MAC-BENCHMARK-20261111.md serta laporan asli lokal
reviews/LMS-04-mac-validation-20261111.md bila tersedia. SHA/schema aktual,
metode rinci, status save, suite count dan UAT completion tidak disebut dalam
ringkasan. Verifikasi dari bukti, jangan menganggap benchmark sebagai verdict.

Source cloud tidak berubah dari5b675e6. Commit berikutnya pada tahap pencatatan
ini hanya dokumentasi; manifest/patch/performance.json tetap snapshot historis
source tersebut. Beberapa dokumen lebih baru secara sengaja, sedangkan file
runtime/test/script/CI tetap sama. Jangan menyimpulkan beda hash dokumentasi
sebagai perubahan runtime atau menimpa laporan Mac yang untracked.

## Fokus

- F1: benar-benar InitPlan/uncorrelated bounded calls, bukan cache GUC yang bisa
  dipalsukan atau cache antar request. Prepared statement kehilangan akses setelah
  revoke. SELECT tidak lagi mengevaluasi FOR ALL write predicate per row. Admin
  INSERT RETURNING tetap sah, teacher/archive/student/draft/peer isolation tetap.
- Dedicated reader NOLOGIN/NOBYPASS/NOINHERIT tanpa membership/privileged flags;
  minimum column grants/policy hanya untuk role itu. Tidak ada password/session/
  content/progress write grant atau runtime SET ROLE. GLOBAL old definer LOW
  tidak dianggap closed hanya karena empat helper baru terpisah.
- F2: raw CPU input30KB, real HTTPuvicorn health baseline/2/8/one original60budget.
  Child GIL terpisah, queue tidak tak terbatas, busy429/retry1, CPU120ms/wall1.5s,
  crash/hang fail-closed, credential env tidak diwariskan, no learner code exec.
  Ukur performa sendiri; jangan memakai Event test sebagai bukti CPU isolation.
  Catat platform RLIMIT_AS Mac/multi-worker limits dan biaya algoritme yang tersisa.
- Progress: owner/enrollment/student/tenant/FK/revision, forged IDs/GUC/input,
  stale revision409, idempotent concurrency/audit, material vs title/reorder,
  revoke/archive/draft/regrant dan snapshot race semantics. Completion self-report,
  bukan nilai. Teacher/admin tidak otomatis mendapat analytics siswa.
- BFF Origin/route/method/query/payload/retry/Set-Cookie; UI completed count,
  previous/next/resume, reload, new revision needs_review, stale-write/revoke.
- Upgrade8→9→10 menjaga auth/course/enrollment; rollback10 lock+guard explicitack,
  SQLoffline; restore9→8 policies/grants. Empty/disposable DB saja, tidak UAT.
- Learning120/min bounded member row/retention; existing course60/min utuh.

## Prompt Claude CLI

```text
Lakukan review READ-ONLY LMS-04 branch feat/LMS-04-student-learning di
mashudizaini/maaher-lms. Baca reviews/LMS-04-review-request.md dan semua rujukannya.
Periksa source SHA/status Git tanpa overwrite perubahan/laporan lokal.
Target runtime5b675e6; review4870287..5b675e6 dan re-review MEDIUM F1/F2 terpisah.
Baca laporan asli reviews/LMS-04-mac-validation-20261111.md bila tersedia;
verifikasi SHA/schema dan metode/budget/status saves aktual. Commit cloud setelah
5b675e6 pada tahap ini hanya dokumentasi. Jika source lokal berbeda, nyatakan
scope yang benar tanpa reset/overwrite dan jangan mengklaim target sudah diuji.
Gunakan DB kosong baru maaher_test_* milik review, role runtime non-owner tanpa
BYPASSRLS dan role lain terpisah. Jangan memakai DB UAT/DB lama atau menjalankan
benchmark pada data pengguna; benchmark mengubah policy sementara. Semua rollback
ber-ack hanya pada DB disposable baru itu. Pertahankan .env/Auth0/keyring/binding.
Jalankan suite/probe sendiri, terutama workload actual CPU dan max1500 lessons/
451catalog; ukur metode dan hasil, bukan hanya membaca bukti author. Browser
jika tersedia; jangan sebut terverifikasi bila tidak dijalankan.
Catat per-finding file:line/severity/repro/dampak serta batas pengujian. Bedakan
synthetic provider/ASGI/TCP dari Auth0 nyata dan UAT manusia. Catat N2/N3/N4 lama,
old definer LOW dan tenant pause yang belum ditangani; jangan tutup tanpa bukti.
Untuk full auth terpisah, fetch ref main read-only lalu origin/main...HEAD;
auth parent8941a79..4733526 masih perlu review penuh, bukan bagian otomatis verdict.
Simpan reviews/LMS-04-claude.md, verdict dan status F1/F2 berdasarkan bukti.
Jangan ubah source/guard/Auth0/config/data pengguna, merge atau deploy.
```
