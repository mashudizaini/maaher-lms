# Permintaan re-review independen LMS-02

Disiapkan **author Codex**, bukan laporan Claude. Pemilik menyampaikan review
awal dengan tujuh LOW tanpa BLOCKER/HIGH/MEDIUM; ringkasannya dicatat dengan
provenance pada [review relay](LMS-02-review-relay-20261110.md). Verdict formal
tidak diberikan. Source f38c231 telah lulus UAT Mac menurut pemilik; **delta
perbaikan dan migration 0007 belum UAT Mac/re-review**.

Branch feat/LMS-02-course-management di mashudizaini/maaher-lms. Root Git berada
satu tingkat di atas root aplikasi maaher-lms-starter/. Scope delta review
**f4f9cf7..HEAD**; delta seluruh course **4733526..HEAD**. Auth parent diperiksa
terarah pada review sebelumnya, belum mendapat review penuh. Ambil ref main
tanpa mengubah source lokal (`git fetch origin main:refs/remotes/origin/main`),
lalu gunakan `git diff origin/main...HEAD` untuk scope penuh. Jika akses remote
gagal, catat keterbatasan dan base eksplisit 8941a79; jangan berpura-pura
main...HEAD telah diperiksa. Pertahankan Git status/perubahan lokal.

Artifact awal LMS-02-manifest.json/author.patch tetap historis f38c231. Snapshot
delta baru ada pada LMS-02-review-fixes-manifest.json dan review-fixes.patch;
Git diff adalah sumber review utama. Laporan Claude LMS-01 tetap SHA256
004a19183409b152d0947ab6f5b99af2000d9dd3324c9a2c77ea66a4106032ce, tanpa perubahan.

## Prompt Claude Code

```text
Anda reviewer independen READ-ONLY untuk LMS-02, branch
feat/LMS-02-course-management di mashudizaini/maaher-lms.
Baca CLAUDE.md, docs/AGENT-WORKFLOW.md, PROJECT-SPEC.md, ARCHITECTURE.md,
.claude/skills/lms-security-review/SKILL.md, ticket LMS-02, ADR-006,
reviews/LMS-02-author-response.md dan docs/LMS-02-HANDOFF.md.
Pertahankan source/config/data dan laporan Claude asli. Periksa diff
f4f9cf7..HEAD (review fixes), 4733526..HEAD (kursus), serta origin/main...HEAD
untuk auth parent jika meninjau penuh; fetch ref main secara read-only dahulu.
Jangan menganggap pemeriksaan terarah auth sebagai approval penuh.
Reproduksi tujuh LOW: assignment published tidak draft; siklus role/status
tidak mengembalikan akses (termasuk concurrency INSERT assignment vs UPDATE);
archived teacher parent/child RLS; target Markdown server dan Unicode URL;
guard rollback berisi; explicit detail fields dan budget mutation atomik.
Periksa definer trigger/ACL, retensi, BFF Retry-After, editor setelah 429,
upgrade 0006→0007 dengan data dan batas cleanup assignment historis.
Gunakan DB kosong baru maaher_test_* milik review, role runtime non-owner tanpa
BYPASSRLS; jangan reset/downgrade DB UAT atau DB lama. Pengujian penghapusan
course dengan allow_course_data_loss hanya pada DB fixture sintetis tersebut.
Jalankan tes aman, jelaskan batas signed synthetic IdP vs Auth0 nyata, rekam
file:line/severity/probe dan pemeriksaan yang tidak dijalankan.
Jangan ubah source/Auth0/.env atau guard, jangan merge/deploy. Simpan laporan
baru reviews/LMS-02-claude-rereview.md; pertahankan laporan lama. Berikan verdict
berdasarkan bukti. Pisahkan auth parent, UAT dev dan gate produksi.
```

Human tetap memutuskan merge/deploy setelah review dan gate terkait. Enrollment
LMS-03 belum diimplementasikan pada delta ini.
