# ADR-007 — cohort, enrollment dan akses siswa

Status: implementasi development LMS-03, 11 November 2026 WIB, di atas fe54142.
Persetujuan yang disampaikan pemilik adalah APPROVED_WITH_NOTES untuk LMS-02;
ADR ini bukan persetujuan independen LMS-03 atau auth parent.

Satu cohort terkait tepat satu course/tenant. Enrollment wajib mempunyai cohort
pada course yang sama; unique(tenant_id,course_id,student_id) berlaku untuk seluruh
lifecycle. Pendaftaran duplikat menghasilkan 409; aktivasi ulang adalah tindakan
admin eksplisit terhadap row/version lama. Tidak ada impor/provisioning otomatis.

Pendaftaran boleh disiapkan pada draft. Akses read-only siswa memerlukan user,
tenant, membership student, enrollment dan cohort aktif serta course published.
Unpublish/edit draft menjeda akses, publish kembali membukanya. Archive course/
cohort mencabut enrollment permanen, restore tidak mengaktifkannya. Perubahan
role/status membership atau status user juga mencabut permanen, dibatasi tenant
membership yang berubah; perubahan status user berlaku lintas tenant miliknya.
Role lain tidak mendapat akses siswa hanya karena mempunyai enrollment lama.

Admin tenant membuat/mengedit/archive/restore cohort, mendaftar/memindahkan/
mencabut/mengaktifkan ulang siswa dan membaca status revoked. Teacher hanya
cohort/roster aktif course yang ditugaskan; tanpa mutasi atau email lookup baru.
Student hanya course materi terbit, cohort dan enrollment miliknya. Roster
mengirim UUID siswa; admin dapat meresolusikan email melalui list_members yang
sudah ada dan sudah dibatasi tenant/admin. Tidak menambah definer untuk profile
atau membuka SELECT users. Teacher memakai label ID singkat sampai scope profil
siswa dirancang. Tidak ada peer list untuk siswa.

0008 menambah FORCE RLS cohorts/enrollments dan FK komposit ke course/cohort/
membership. SELECT policy course/module/lesson diperluas dengan
course_student_access(tenant,course,cohort optional). Helper SECURITY DEFINER
memvalidasi session runtime_identity, tenant selector dan role student aktif,
lalu memeriksa status parent/enrollment melalui role definer yang terbatas.
Tidak memanggil kembali policy sehingga tidak terjadi siklus RLS. Policy write
staff sebelumnya tetap berlaku; runtime tidak dapat mengubah course_id, tenant_id,
student_id atau menghapus row baru. Auth role tidak mendapat SELECT/INSERT baru.

Tiga definer baru: course_student_access, enrollment_lock_student, enrollment_guard.
Owner maaher_definer NOLOGIN non-superuser, fixed search_path, tanpa PUBLIC EXECUTE.
Runtime hanya dapat mengeksekusi dua helper pertama; fungsi trigger tidak dibuka
sebagai RPC. Grants tambahan definer: SELECT course/cohort/enrollment,
UPDATE(version) course/cohort untuk SELECT FOR SHARE, dan UPDATE(status,version,
updated_at) enrollment untuk pencabutan. Password/session/faktor tidak diperluas.
Schema head berisi tepat 14 fungsi definer, ACL/owner diuji.

BEFORE trigger runtime memeriksa admin tenant sebelum menyentuh parent/user;
helper memeriksa target membership sebelum mengunci user global. Pemilik tabel
tetap memiliki otoritas DB yang sudah ada, bukan jalur permission pengguna.
Dua probe menahan baris foreign dan memeriksa penolakan tanpa menunggu lock.

API mutasi mengunci course→cohort→student/membership→enrollment; target student/
parent immutable dan dibaca melalui RLS sebelum lock. INSERT/reactivate/move
memerlukan student aktif. Lock student mendahului row enrollment untuk menghindari
inversi dengan trigger membership. Revoke tidak memerlukan lock membership atau
parent yang sudah revoked/archived. Course lock menyerialkan operasi cohort/
enrollment dengan authoring/archive course. Trigger juga memvalidasi raw runtime
INSERT/UPDATE dan memaksa cleanup; SQL langsung yang tidak mengikuti urutan lock
bisa dibatalkan PostgreSQL, tanpa melemahkan invariant. API adalah jalur mutasi.

Version/cohort/enrollment terpisah dari course.version: perubahan roster tidak
mengembalikan course ke draft. Trigger pencabutan menaikkan enrollment.version;
audit ditulis jika actor admin tervalidasi tersedia. SQL operator tanpa session
tidak diberi actor palsu. N4 cleanup 0007 historis tidak diklaim diperbaiki.

Cap development: 100 cohort/course, 5000 enrollment/course termasuk revoked,
list 30/default dan 50/max. Budget 60 mutation/menit tenant/user dibagi dengan
course authoring; counter commit sebelum validasi body. Middleware ASGI membatasi
stream 256 KiB dan mereplay pesan receive publik, mengganti request._body.
Validasi CommonMark pindah ke endpoint sync/worker; tes menunjukkan event loop
masih melayani health selama worker ditahan. Kompleksitas CPU parser tetap
kuadratik dan perlu pengukuran kapasitas produksi.

Upgrade 0007→0008 mempertahankan auth/course/content/assignment dan membuat
cohort/enrollment kosong. Tidak ada auto-link email, relaksasi MFA atau perubahan
Auth0 Action. Downgrade 8→7 menghapus data baru; guard SQL menolak tabel berisi
kecuali -x allow_enrollment_data_loss=yes setelah backup. SQL guard dapat
dihasilkan offline, tanpa memperbaiki catatan offline guard 0006 lama. Course
content/auth dipertahankan saat rollback ber-ack; data enrollment tidak dibuat
ulang setelah re-upgrade. Semua tes rollback hanya pada DB sintetis baru.

Progress/completion, grading/submission, runner, pembayaran dan upload di luar
scope. /learn adalah pembaca materi minimum untuk membuktikan akses LMS-03,
bukan pernyataan LMS-04 selesai. Real student/teacher Auth0, SMTP/inbox, UAT Mac,
CI remote, Docker image dan review independen tetap memerlukan bukti tersendiri.
