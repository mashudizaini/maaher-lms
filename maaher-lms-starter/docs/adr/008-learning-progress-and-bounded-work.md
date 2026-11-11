# ADR-008 — completion per revisi dan kerja belajar yang dibatasi

Status: development LMS-04 atas permintaan pemilik, 11 November 2026 WIB.
Base 4870287, runtime parent 110c9be. F1/F2 MEDIUM LMS-03 adalah prasyarat
performa untuk layar belajar; hasil author menunggu review independen.

## Read authorization per statement

0009 memisahkan policy module/lesson FOR ALL menjadi INSERT/UPDATE/DELETE.
SELECT memakai scalar InitPlan yang tidak bergantung pada baris untuk scope
course/cohort/enrollment. Context berasal dari runtime_identity yang memverifikasi
session/MFA, membership dan tenant aktif. Tidak memakai app.user_id sebagai
otoritas atau cache hasil role lintas statement/request. Setiap prepared statement
baru memeriksa ulang akses. Beberapa policy dapat membuat beberapa InitPlan;
batasnya jumlah tetap per statement, bukan satu panggilan total per request.

Empat helper access_* dimiliki role baru maaher_access_reader:
NOLOGIN/NOSUPERUSER/NOBYPASSRLS/NOINHERIT, tidak beranggota atau diberikan ke role
lain. Dibutuhkan DBA migration privilege untuk provision role; API tidak boleh
memiliki CREATEROLE/ownership atau diasumsikan menjadi reader. Reader memperoleh
SELECT kolom minimum pada memberships, tenants, courses, courses_teachers,
cohorts, enrollments beserta policy SELECT khusus. Tidak memperoleh password,
session, faktor, isi lesson, progress atau write. PUBLIC EXECUTE helper dicabut,
fixed search_path, tanpa parameter actor/tenant dari caller. UUID scope terikat
session capability dan tenant selector tervalidasi, bukan hanya UUID tebakan.

Course admin SELECT memakai role admin langsung agar INSERT RETURNING course
baru sah dalam statement yang sama. Teacher tetap course tugas nonarsip;
student hanya enrollment/cohort aktif dan course published. Read/write policy
terpisah mempertahankan larangan mutation student. Roster peer dan tenant lain
tetap tertutup. 14 fungsi lama masih memakai definer BYPASSRLS, sehingga catatan
LOW itu tidak dinyatakan closed; empat helper baru tidak memperbesar grants itu.

## Completion diri dan revisi materi

0010 menambah revision pada lesson (default 1) dan lesson_progress yang FK-nya
mengikat tenant/course/enrollment/student/lesson. Primary key enrollment+lesson,
role runtime tidak dapat mengganti owner/tenant/parent progress. Siswa aktif
hanya SELECT/INSERT/UPDATE/DELETE catatan dirinya pada enrollment/course yang
masih dapat diakses. Admin/guru tidak memperoleh analytics progress pada scope ini.

Trigger menaikkan revision bila content/resources benar-benar berubah, termasuk
SQL update, tetapi tidak untuk title/reorder saja. Completion lama tetap tersimpan
dan tidak dihitung bila revision berbeda; UI meminta membaca/menandai ulang.
Tidak menghitung kembali materi yang pernah identik, karena revision monotonik.
Reaktivasi enrollment eksplisit atau perpindahan cohort mempertahankan catatan
pada revisi yang masih valid. Revoke/archive/draft menutup akses sesuai LMS-03;
tenant disable tetap pause sesuai parent, belum menjadi revocation baru.

Complete/uncomplete menerima revision saja; tenant/student/enrollment berasal
session/database. Complete idempotent dan timestamp/audit tidak ditulis ulang
untuk duplikat pada revisi sama. Uncomplete menghapus catatan milik sendiri.
Completion adalah self-report belajar, bukan bukti penilaian, sertifikat atau
anti-cheat. Optimistic revision dan RLS diperiksa pada statement mutasi; akses
baru ditolak setelah revoke. Operasi yang mulai sebelum perubahan otorisasi
memakai snapshot PostgreSQL statement tersebut, tanpa memberikan student hak
UPDATE/row-lock course atau enrollment. Catatan revisi lama tidak mengesahkan
revisi baru saat dua perubahan berpapasan.

API outline mengirim metadata, count completed/total dan first incomplete.
Lesson mengirim previous/next sesuai urutan module/lesson. Navigasi bebas di
course yang sah, tidak memaksa completion sebagai ujian. /learn mendukung
lanjutkan, selesai & lanjutkan, belum selesai, reload dan notifikasi revisi.

## Budget baca dan CPU parser

Learning GET/POST memiliki admission 120/minute tenant/student, satu row per
membership, transaksi counter terpisah sebelum parse/lookup, saturated counter,
retensi 1 hari. Anonymous/nonstudent tidak membuat row. 429 Retry-After:60.
Query learning memakai statement_timeout 2s; bukan pengganti ingress produksi.

Parser policy CommonMark sama, dijalankan child process terpisah dari GIL API.
Trusted library mengurai teks; tidak menjalankan program learner. Satu pekerjaan
aktif per API process, nonblocking busy 429/Retry-After:1 tanpa queue tak terbatas.
Child env tidak membawa DB/Auth0/keyring credential. Per-document CPU profiling
timer 120ms, parent wall timeout 1.5s dengan nonblocking pipes, child termination
saat hang/crash dan fail-closed 503; complexity 422. RLIMIT_AS 256MiB pada host
POSIX yang mendukungnya; perilaku address-space Mac perlu verifikasi. Algoritme
parser tetap dapat kuadratik, kini kerjanya ditolak bila melewati budget.
Cache hanya 128 SHA-256 digest materi yang valid, dengan key tenant/user dari
actor server tervalidasi; tidak menyimpan isi dokumen atau berbagi key antar-akun.
Jumlah child mengikuti jumlah API process; sizing/cgroup multi-worker tetap perlu.

Benchmark aktual, metode dan batas tersedia pada reviews/LMS-04-author-response.md
serta performance.json. Tidak memakai Event untuk menyatakan CPU terisolasi.

## Migrasi dan rollback

Upgrade 0008→0009→0010 menjaga akun/session/binding/course/material/enrollment,
memberi revision 1 dan progress kosong, tidak menandai selesai otomatis.
Retain_auth_data hanya ditambah DELETE learning budget, ACL tetap; tidak mengubah
login, PKCE, OIDC/MFA/Action atau trusted assurance.

Downgrade 0010→0009 menghapus progress, budget dan metadata revision. Jika progress
berisi, guard setelah ACCESS EXCLUSIVE lock menuntut -x allow_progress_data_loss=yes.
Lock membuat check tidak disalip completion baru; backup/quiesce aplikasi dan
keputusan operator tetap wajib. Offline guard 0010 dapat dihasilkan. 0009→0008
mengembalikan read/write policy lama dan mencabut grants helper; role NOLOGIN
cluster dapat tetap ada karena database test lain masih menggunakannya. Tidak
menyentuh course/auth/enrollment data. Rollback bukan prosedur UAT.

N2 offline0006, N3 Unicode/NAT64, N4 trace cleanup, full auth independent review,
SMTP/inbox, real Auth0, CI remote, Docker image dan gate release tetap terpisah.
Tidak ada grading/submission/runner/pembayaran/upload pada LMS-04.
