# LMS-03 — cohort, enrollment dan akses materi siswa

Diimplementasikan pada branch development terpisah `feat/LMS-03-enrollment`,
bertumpu pada LMS-02 fe54142. Pemilik meminta lanjut setelah menyampaikan
re-review APPROVED_WITH_NOTES untuk delta kursus, 11 November 2026 WIB.
Review auth parent dan keputusan merge/deploy tetap terpisah.

## Lingkup dan kontrak

- Satu cohort mengacu satu tenant/course; admin membuat, mengganti nama,
  mengarsipkan/memulihkan. Cap 100 cohort/course, judul 160 karakter.
- Satu enrollment per tenant/course/student sepanjang lifecycle; cohort wajib
  pada course yang sama. Admin mendaftar, memindahkan cohort, mencabut atau
  mengaktifkan ulang secara eksplisit dengan version check dan audit.
  Cap 5000 enrollment/course, termasuk yang dicabut; aktivasi ulang memakai row
  lama, bukan membuat enrollment duplikat. Pendaftaran pada draft diperbolehkan
  untuk persiapan; course/cohort archived menolak enrollment aktif.
- Admin mengelola roster tenant. Guru hanya membaca cohort/roster aktif pada
  course yang ditugaskan; tanpa mutasi enrollment. Roster mengirim ID siswa,
  bukan lookup email global. Admin dapat memilih siswa melalui endpoint anggota
  tenant yang sudah ada; teacher melihat label ID singkat sampai profile siswa
  yang sesuai izin dirancang pada scope berikutnya.
- Siswa mendapat katalog/outline/lesson READ-ONLY hanya bila membership student,
  user, tenant, enrollment dan cohort aktif serta course published. Siswa hanya
  membaca enrollment/cohort miliknya; tidak melihat peer roster atau assignment
  guru. Navigasi minimum /learn membuktikan akses, bukan implementasi progress.
- Perubahan aktual role/status membership atau status user mencabut enrollment
  aktif secara permanen. Archive cohort/course juga mencabut. Restore tidak
  mengaktifkan enrollment. Admin harus re-enroll secara eksplisit ke cohort
  aktif. Unpublish/edit draft hanya menjeda akses sampai publish berikutnya;
  status enrollment tetap aktif, agar authoring rutin tidak menghapus roster.

## Database, transaksi dan batas

Migration 0008_enrollment menambah dua tabel FORCE RLS/FK komposit, tiga definer
non-login/non-superuser dengan ACL/search_path terbatas dan trigger lifecycle.
Course/module/lesson SELECT diperluas hanya melalui helper enrollment valid;
policy write authoring tetap staff-only. Runtime tidak mendapat UPDATE parent,
student, tenant atau DELETE pada tabel baru. Auth credential tidak mendapat akses.

Mutasi API mengunci course→cohort→student/membership→enrollment agar serial dengan
role/status dan archive; revoke tidak menunggu membership setelah row enrollment.
Raw SQL yang menabrak lock order dapat dibatalkan PostgreSQL; gagal tertutup,
bukan pengganti API authoring. Budget terautentikasi 60/menit tenant/user dibagi
antara kursus/cohort/enrollment; transaksi counter commit sebelum parse body.
ASGI receive/replay mengganti request._body; batas body 256 KiB, Origin exact,
BFF route/query/header/cookie allowlist, Retry-After dan cache no-store.
CommonMark validation berlangsung pada endpoint sync/worker, bukan event loop;
biaya kuadratik parser tetap catatan kapasitas, tidak diklaim linear.

Upgrade mempertahankan seluruh data course/identity/auth dan tidak otomatis
mendaftarkan siswa. Downgrade 8→7 menghapus cohort/enrollment; ditolak jika tabel
berisi kecuali `-x allow_enrollment_data_loss=yes` setelah backup. Guard SQL 0008
juga dapat dihasilkan offline. Guard offline 0006 tetap catatan LMS-02 terpisah.

## Acceptance dan tes

Cross-tenant/course/student/cohort/FK, own-only RLS, forged context, active user/
role enforcement, teacher assignment, duplicate/concurrent enrollment, role vs
activation, lifecycle revoke/restore, optimistic conflict, pagination, bounds,
audit, seeded upgrade/destructive rollback guard dan preservasi course/auth.
Browser production Next + API + PostgreSQL: admin cohort→enroll, siswa sesi lain
membaca materi→revoke→404→reactivate→read→archive/restore tetap revoked→logout.
Seluruh auth/course lama tetap diuji. UAT Mac dan review independen LMS-03 pending.

Tidak termasuk: completion/progress LMS-04/09, grading, assignment/submission,
pembayaran, email nyata, import CSV, upload/video hosting atau learner execution.
Tidak ada merge/deploy atau perubahan tenant Auth0 oleh sesi cloud.
