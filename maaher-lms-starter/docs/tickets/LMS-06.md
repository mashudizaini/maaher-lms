# LMS-06 — penilaian guru dan feedback siswa

11 November 2026 WIB. Pemilik meminta kelanjutan setelah re-review5131f2c:
F9/F11 CLOSED, F10 CLOSED_WITH_NOTES untuk dev/UAT sintetis. Base13408bb
(dokumentasi), branchfeat/LMS-06-teacher-grading. Auth parent tetap terpisah.

Scope: admin tenant/pengajar assigned course menilai submission immutable memakai
rubrik versi submission, skor integer0..max/kriteria, total dihitung server/DB.
Draf nilai privat; bagikan eksplisit; koreksi membuat revisi immutable dan perlu
alasan, siswa tetap melihat nilai sebelumnya sampai dibagikan. Tarik nilai butuh
alasan, hapus payload publik namun pertahankan histori privat/audit. Siswa hanya
nilai dirinya yang dibagikan dan masih punya akses enrollment/course. Grade bukan
completion otomatis, bukan auto-grader atau learner execution.

Private grading_entries/revisions/events terpisah dari grading_publications
(snapshot disclosure-only). Student SQL tidak membaca draf/alasan privat/history.
RLS/FK komposit sebelum API; fungsi baru INVOKER, timestamp/actor/total/snapshot
server-derived, optimistic version dan lock per submission, satu urutan audit
untuk setiap perubahan. Maks100 revisi/300 perubahan per submission. Archivecourse
menutup grading write; teacher revoked/unassigned tidak membaca/mengubah; siswa
revoked/course unpublish tidak membaca. Archive task tidak menghapus histori.

UI /grading untuk staff, nilai di riwayat /work siswa, teks feedback escaped.
BFF route/method/query/Origin/body/cookie allowlist. Staff grading GET180/min pada
counter baru; POST memakai budget course60/min existing; student gradeGET memakai
work120/min existing. Counter lama dibersihkan maintenance role tanpa menambah
SECURITY DEFINER atau grant definer lama. Schema0013_grading: forward preserves
parent; populated rollback guard allow_grading_data_loss=yes eksak, offline SQL.

Tes: tenant/peer/teacher RLS SQL; private draft/history isolation; original rubric;
score validation/server total/spoof timestamps/actors; publish/correct/withdraw;
concurrent new grade/corrections/state race + authority-before-lock; immutable
owner/runtime history; counter/retention/BFF; seeded migration/guard/offline;
browser guru/siswa dua sesi, stale conflict/429 editor, nilai0 valid. Seluruhparent.
Tidak merge/deploy, Auth0 nyata/UAT manual/CI remote masih terpisah. Parsercapacity
notes, F12 dan F3/N2/N3/N4 parent tidak dinyatakan selesai. Uji DB kosong baru saja.
