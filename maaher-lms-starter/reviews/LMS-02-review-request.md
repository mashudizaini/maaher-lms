# Permintaan review independen LMS-02 dan auth parent

Dokumen ini disiapkan **author Codex**, bukan hasil review Claude. Status review
**PENDING**. Source LMS-02 yang diuji adalah f38c231; perubahan setelahnya pada
tahap pencatatan UAT hanya dokumen. Hasil manual pemilik tersedia di
docs/LMS-02-DEV-UAT-20261110.md.

## Scope dan provenance

- Branch: feat/LMS-02-course-management, repo mashudizaini/maaher-lms.
- Root aplikasi: maaher-lms-starter/. Git root berada satu tingkat di atas
  pada checkout monorepo. Periksa Git status tanpa reset/stash/overwrite.
- Delta course: 4733526..f38c231. Auth parent 4733526 belum di-merge/review atas
  source Auth0 terbaru; periksa main...HEAD untuk seluruh trust boundary.
- reviews/LMS-02-manifest.json dan LMS-02-author.patch adalah snapshot f38c231.
  Dokumen handoff/setup/PR kemudian diperbarui untuk status UAT; beda dokumentasi
  dari manifest tidak boleh disalahartikan sebagai beda source runtime.
- Laporan reviews/LMS-01-claude.md awal tetap utuh, SHA256
  004a19183409b152d0947ab6f5b99af2000d9dd3324c9a2c77ea66a4106032ce.
  Status lama CHANGES_REQUESTED tidak ditulis ulang menjadi persetujuan.

## Fokus pemeriksaan

1. RLS/tenant/session capability, composite FK, role runtime/definer dan grants.
2. Guru hanya kursus yang ditugaskan; assignment/membership/user dicabut atau
   disabled berhenti memberikan akses pada session yang sudah terbit.
3. Version lock, mutation concurrent, rollback error child, publish/draft/archive
   dan akses SQL langsung pada parent/child yang sudah dipublikasikan.
4. Markdown/XSS, resource URL, gambar tidak di-fetch otomatis, BFF Origin/route/
   query/payload serta penanganan ingress. Tidak ada code runner learner.
5. Auth0 issuer/sub binding, PKCE/state/nonce/RS256, local dev-TOTP guard,
   fallback/recovery restriction dan kode diagnosis yang tidak mencetak secret.
6. Upgrade 0006 mempertahankan auth; downgrade menghapus course data dan perlu
   backup. Uji migrasi hanya pada DB kosong sintetis baru milik review.

## Prompt Claude Code

```text
Anda reviewer independen READ-ONLY untuk Maaher LMS, branch
feat/LMS-02-course-management, source LMS-02 f38c231 yang telah lulus UAT Mac
menurut pemilik. Root aplikasi GitHub: maaher-lms-starter/.
Baca CLAUDE.md, docs/AGENT-WORKFLOW.md, PROJECT-SPEC.md, ARCHITECTURE.md,
.claude/skills/lms-security-review/SKILL.md, docs/LMS-02-HANDOFF.md,
docs/LMS-02-CHECKLIST.md, dan reviews/LMS-02-review-request.md.
Periksa source/status Git sebenarnya tanpa menimpa perubahan lokal. Review
4733526..f38c231 untuk delta kursus dan main...HEAD untuk auth parent terbaru.
Bedakan source runtime dengan catatan UAT baru pada dokumentasi.
Jalankan tes aman pada DB kosong baru maaher_test_* dan role terpisah milik
review; jangan memakai DB UAT, database lama, secret IdP atau data pengguna.
Fokus RLS/IDOR/FK, session/MFA/definer, teacher assignment/revoke, publish/version
atomicity, Markdown/XSS/HTTPS, BFF serta migrasi/rollback. Reproduksi temuan dan
catat file:line, severity, dampak, bukti, rekomendasi serta tes yang tidak dijalankan.
Jangan ubah source/Auth0/.env, memperlemah guard, merge atau deploy.
Pertahankan laporan Claude lama. Tulis reviews/LMS-02-claude.md dan pisahkan
temuan auth parent dari LMS-02; berikan CHANGES_REQUESTED, APPROVED_WITH_NOTES
atau APPROVED berdasarkan bukti. UAT dev bukan bukti kesiapan produksi.
```

Setelah laporan ada, author menindaklanjuti temuan dan meminta review ulang
sesuai workflow. Source tidak otomatis digabungkan atau dideploy oleh review.
