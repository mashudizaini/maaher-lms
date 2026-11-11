# LMS-04 — navigasi belajar dan completion dengan prasyarat performa

11 November 2026 WIB. Pemilik meminta lanjut LMS-04 setelah menyampaikan review
LMS-03: F1 (RLS per-row lambat) dan F2 (parser CPU mengganggu proses) MEDIUM.
Base development 4870287, runtime parent 110c9be. Tidak menganggap LMS-03 approved;
verdict formal tidak disebut pada ringkasan terakhir. Full auth review terpisah.

Lingkup: (1) perbaikan F1 dengan scope akses tervalidasi sekali per SQL statement,
set-based RLS tanpa cache otorisasi lintas request; (2) F2 parser library terpercaya
di proses terpisah, satu pekerjaan aktif per API process, CPU/wall/memory bounds,
busy 429, tanpa menjalankan kode learner; (3) siswa membaca, menandai selesai/
belum selesai, melihat hitungan completion, melanjutkan yang belum selesai,
berpindah pelajaran dan reload persistence di /learn.

Completion adalah catatan belajar diri, bukan nilai/sertifikasi. Terikat enrollment
milik siswa dan revisi lesson. Perubahan isi/resources menaikkan revision dan
membuat catatan lama tidak dihitung sampai siswa menandai ulang; title/reorder
saja tidak membatalkan. Move cohort/reaktivasi eksplisit mempertahankan completion
revisi yang masih sama. Draft/unpublish/revoke/archive/role/status menolak read/
write sesuai LMS-03; tidak ada akses melalui UUID atau state dari browser.

File: migration scope read + migration lesson progress, helper RLS role read-only
NOLOGIN/NOBYPASSRLS dengan grants minimum, parser process service/worker, learning
API/BFF/UI, fixture/tests/benchmarks, CI dan handoff. Scope tidak menambah auth
provider, grading/submission, upload atau runner. N2/N3/N4 parent tetap dicatat.

Acceptance: semua regresi parent; cross-tenant/peer read-write/FK/forged context;
completion idempotent dan konflik revisi; perubahan materi, revoke/regrant,
archive/draft, restart API/reload; SQL plans/bounded helper evaluations; benchmark
outline 100/1500 lesson dan katalog 451 published courses untuk student/admin;
CPU adversarial 30KB dengan 2/8 saves dan health p95 dibanding baseline, termasuk
budget asli 60/min; child crash/timeout/busy fail-closed; two-browser student/admin
UAT otomatis. DB tes baru saja; migrasi maju menjaga data lama, rollback berisi
butuh ack eksplisit. Independent review dan Mac UAT baru tetap diperlukan.
