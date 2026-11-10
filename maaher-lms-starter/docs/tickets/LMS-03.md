# LMS-03 — rancangan iterasi cohort dan enrollment

Status: **rancangan scope berikutnya**, belum diimplementasikan. Dasar kebutuhan
adalah PROJECT-SPEC LMS-03, setelah alur authoring LMS-02 dilaporkan lulus UAT
development. Catatan ini tidak menyatakan review/merge LMS-02 sudah selesai.

Tujuan: admin memasukkan siswa ke cohort/kursus di tenant yang sama; siswa
hanya mendapat akses kursus tempat ia mempunyai enrollment aktif. Teacher
tetap dibatasi pada kursus yang ditugaskan. Tidak ada akses berdasarkan email
atau hanya karena kursus published/UUID diketahui.

## Scope awal yang direncanakan

- Cohort terkait satu course dan satu tenant; admin create/edit/archive.
- Enrollment siswa aktif ke course/cohort yang sah, uniqueness per tenant/
  course/student, pindah cohort dan revoke secara eksplisit dengan audit.
- Tenant dari session + membership tervalidasi; FORCE RLS dan FK komposit untuk
  course/cohort/student, tanpa perpindahan resource antartenant lewat input.
- Hak baca/pengelolaan per role: admin tenant, teacher pada course yang ditugaskan,
  siswa hanya enrollment miliknya. Draft/archived/revoked tidak membuka materi.
- API dan UI admin cohort/enrollment dengan pagination, bounds dan version checks;
  query akses materi siswa memeriksa status enrollment/membership/course kembali.

## Acceptance dan tes yang perlu dibuat pada implementasi

- Enroll duplikat/concurrent tidak membuat dua enrollment aktif; perpindahan
  cohort atomik, role dan parent UUID diverifikasi server.
- Student/teacher/cohort/course dari tenant lain ditolak, termasuk SQL role
  runtime dengan GUC palsu dan FK lintas parent/tenant.
- Revoke enrollment/membership/assignment dan unpublish/archive menghentikan
  akses yang relevan pada session yang sudah ada; tidak ada implicit reactivation.
- Parent auth dan authoring tetap lulus regresi; upgrade mempertahankan data
  course/identity, downgrade impact didokumentasikan dan diuji pada DB baru.
- Browser admin create cohort→enroll→student melihat akses yang sah→revoke;
  aktor yang sama tidak mendapat hak lewat role dari browser.

Progress/completion dan navigasi belajar lengkap tetap LMS-04/LMS-09. Pembayaran,
email nyata, sertifikat, grading, upload dan eksekusi kode tetap scope terpisah.
Rincian schema/API/caps akan ditetapkan dalam rencana implementasi bounded,
dengan dampak pada course publication dan enrollment revocation yang direview.
