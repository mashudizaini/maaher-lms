# LMS-02 — manajemen kursus development

Kelanjutan yang diminta pemilik setelah UAT Auth0 berhasil, 10 November 2026.
Implementasi asli berdasarkan PROJECT-SPEC/ARCHITECTURE, bukan hasil observasi
Timedoor yang belum tersedia. Branch ditumpuk pada source LMS-01; review auth
dan produksi tetap terbuka. Tidak ada merge/deploy otomatis.

Lingkup: admin membuat kursus, menunjuk guru aktif dalam tenant, mengarsipkan/
memulihkan kursus; admin/guru yang ditugaskan mengelola modul/pelajaran, urutan,
Markdown, tautan materi HTTPS, terbitkan/tarik publikasi. Semua query memakai
tenant dari session+membership, FORCE RLS, FK komposit dan role runtime terbatas.
Siswa belum mendapat akses materi sampai enrollment LMS-03 mengatur haknya.
Unggah berkas, video hosting, pembayaran dan runner tidak termasuk tahap ini.

Asumsi: kursus terdiri dari modul dan pelajaran berurutan. Materi Markdown tidak
mengeksekusi HTML/script; gambar eksternal menjadi tautan, tidak dimuat otomatis.
Tautan HTTPS tidak di-fetch server. Setiap edit mengembalikan kursus ke draft;
publikasi memerlukan modul/pelajaran berisi. Optimistic version mencegah edit
saling menimpa; seluruh perubahan diaudit tanpa mencatat isi pelajaran.

File: migrasi 0006, API courses, BFF khusus, UI /courses/ dan link dari /auth,
fixture/migration/API/SQL/browser tests, CI dan handoff. Tes wajib: tenant asing,
forged GUC tanpa session, role siswa/guru tanpa assignment, pencabutan assignment/
membership, FK tenant, XSS/URL berbahaya, state/version conflict, publish validation,
audit, migrasi roundtrip dan browser login→kursus→pelajaran→publish→logout.

Batas sumber daya: 500 kursus per tenant, 30 modul per kursus, 50 pelajaran per
modul, 50 pengajar per kursus, 10 tautan per pelajaran, Markdown 30.000 karakter;
list kursus paginated.
Menghapus modul/pelajaran adalah tindakan eksplisit pada draft dan menghapus
isinya; kursus diarsipkan, tidak dihapus. Backup/restore sebelum penggunaan nyata.
