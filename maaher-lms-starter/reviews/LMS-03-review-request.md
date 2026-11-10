# LMS-03 — permintaan review independen

Disiapkan author Codex. Branch feat/LMS-03-enrollment bertumpu pada **fe54142**;
review delta **fe54142..HEAD**. Root aplikasi maaher-lms-starter/ satu tingkat
bawah Git root. Laporan asli Claude tetap di Mac; jangan menimpa file tersebut.
LMS-02 APPROVED_WITH_NOTES untuk fe54142 tidak mengesahkan LMS-03 atau auth parent.

Baca AGENTS/CLAUDE, workflow, spec, architecture, skill security review,
docs/tickets/LMS-03.md, ADR-007, LMS-03-HANDOFF/CHECKLIST, serta relay re-review
LMS-02 20261111. Artifact patch/manifest baru adalah snapshot review; Git diff
sumber utama. Semua auth/course lama tetap disertakan pada tes regresi, bukan
klaim audit penuh independen terhadap auth.

## Fokus

- course_student_access dan perluasan SELECT RLS tidak membuka draft/archived,
  peer roster/cohort, tenant asing atau mutation siswa. Session/membership/user/
  tenant harus valid; UUID dan selector tidak memberi akses sendiri.
- Definer owner/no-login/search_path/ACL dan grants tambahan untuk FOR SHARE;
  role runtime tidak owner/BYPASSRLS, tidak membaca password/mencetak session.
- BEFORE trigger memeriksa authority/tenant **sebelum** menyentuh parent/user;
  helper tidak mengunci user global yang bukan siswa aktif tenant actor.
  Pemilik DB tetap memiliki otoritas atas tabel; bukan jalur pengguna aplikasi.
- FK course/cohort/student/tenant, unique lifecycle, active student/cohort,
  role/archive concurrent vs activation/INSERT, lock order, version/audit.
- Revoke permanen untuk role/status/archive, restore tidak aktif otomatis;
  unpublish/draft hanya pause; enrollment tenant lain tetap utuh.
- Public ASGI receive/replay mengganti request._body; multi-frame 256 KiB,
  disconnect, budget commit sebelum parse dan Retry-After. Parsing CommonMark
  pada worker, tanpa menganggap kompleksitas kuadratik telah hilang.
- BFF allowlist/body/Origin/cookie spoof/Set-Cookie, read-only /learn preview,
  admin UI pagination/move/revoke/reactivate dan dua session browser berbeda.
- Seeded upgrade 0007→0008 menjaga content/auth; rollback berisi menolak default,
  explicit data-loss ack hanya pada DB disposable; SQL guard 0008 offline.

## Prompt Claude CLI

```text
Review READ-ONLY LMS-03 branch feat/LMS-03-enrollment di mashudizaini/maaher-lms.
Baca reviews/LMS-03-review-request.md dan dokumen/skill yang dirujuk di sana.
Periksa status Git/source SHA tanpa overwrite perubahan lokal/laporan asli.
Review fe54142..HEAD untuk enrollment dan maintenance ASGI/worker.
Jika meninjau auth penuh, fetch ref main secara read-only dan gunakan
origin/main...HEAD; base auth 8941a79..4733526 tetap terpisah dari verdict LMS-03.
Jalankan suite/probe independen pada DB kosong baru maaher_test_* milik review
sendiri, runtime non-owner/non-BYPASSRLS dan role terpisah. Jangan memakai atau
mengubah DB UAT, database/container lama, .env, binding atau tenant Auth0.
Fixture melakukan rollback destruktif ber-ack hanya pada DB disposable sendiri.
Fokus RLS/tenant/peer access, sebelum-lock authority, definer grants, enrollment
lifecycle/races/versions, ASGI body/quota, Markdown worker, BFF dan rollback guard.
Bedakan signed synthetic IdP dari Auth0 nyata, data otomatis dari UAT manual.
Catat per temuan file:line/severity/repro/dampak; nyatakan checks tidak dijalankan
serta N1/N2/N3/N4 parent yang masih terbuka. Jangan menganggapnya CLOSED tanpa bukti.
Pertahankan laporan sebelumnya. Simpan reviews/LMS-03-claude.md dengan verdict.
Jangan ubah source/Auth0/.env atau guard, merge atau deploy.
```
