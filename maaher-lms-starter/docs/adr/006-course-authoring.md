# ADR-006 — kursus, modul dan pelajaran

Status: implementasi development LMS-02 setelah instruksi lanjut pemilik pada
10 November 2026. Source asli Maaher; perilaku Timedoor belum diverifikasi REA.
Auth0 parent branch belum mendapat signoff produksi; modul ini tidak melewati gate.

## Permission dan database

| Peran | Pengelolaan |
|---|---|
| Admin tenant aktif dengan session/MFA yang sah | Buat kursus, kelola seluruh kursus tenant, assign guru, arsip/pulihkan |
| Guru aktif | Baca/edit/publish hanya kursus nonarsip yang ditugaskan; tanpa create/assign/arsip |
| Siswa | Tidak mendapat endpoint pengelolaan; pembacaan materi menunggu enrollment LMS-03 |

Migration 0006 menambah courses, courses_teachers, course_modules, course_lessons.
Seluruhnya FORCE RLS dan membawa tenant_id; FK komposit mengikat course/module/
lesson/membership ke tenant yang sama. PK/FK/owner/tenant tidak bisa diubah role
runtime. Credential auth tidak mendapat akses ke tabel kursus.

course_member_role adalah satu fungsi SECURITY DEFINER baru dengan owner
maaher_definer NOLOGIN non-superuser yang sudah digunakan LMS-01, fixed search_path
dan tanpa PUBLIC EXECUTE. Fungsi mengikat tenant selector ke identity session
runtime_identity, memeriksa tenant/membership/user aktif dan hanya membolehkan
lookup role diri sendiri atau lookup target oleh admin tenant. Tidak membaca
password/faktor/token. Tidak menambah privilege tabel untuk definer.
course_can_manage adalah SECURITY INVOKER, membaca assignment melalui RLS yang
tidak mereferensikan kembali courses; ini menghindari siklus policy.
GUC user_id atau tenant_id tanpa capability session valid tidak mengotorisasi.

Principal memvalidasi membership pada setiap request. Query menyebut tenant
eksplisit, sementara RLS memeriksa session/MFA/membership/assignment lagi. Tidak
ada role dari email, user_metadata atau marker operator. Revoke assignment atau
membership berlaku untuk request berikutnya pada session yang masih ada.

## Authoring dan publikasi

Admin membuat course draft; guru yang ditugaskan mengelola materi. Setiap
mutation mengunci row course, mencocokkan version, lalu menaikkan version dan
mencatat audit actor/action/target tanpa isi materi. Writer bersamaan: satu menang,
yang memakai version lama mendapat 409. Error child/validation me-rollback seluruh
transaksi, termasuk perubahan state. COMMIT selesai sebelum respons sukses.

Edit metadata, struktur dan materi mengembalikan course ke draft. Assignment/
pencabutan guru mempertahankan state, sambil menaikkan version dan mencatat audit.
Child writes juga membutuhkan parent draft pada policy SQL. Publish memerlukan
minimal satu modul, setiap modul mempunyai lesson, dan semua lesson berisi.
Status published adalah status authoring; belum berarti tersedia untuk siswa
tanpa enrollment. Endpoint siswa tidak dibuka dalam tahap ini.

Kursus memakai arsip/pulihkan. Hapus modul/pelajaran meminta konfirmasi UI dan
menghapus child yang terkait secara permanen pada transaksi authoring; course
kembali draft. FK lesson/course melindungi keterkaitan tenant/parent. Reorder
memerlukan seluruh ID pada parent yang sama tepat satu kali; unique posisi
deferrable memudahkan perpindahan atomik. ID urut untuk pagination list courses;
tree hanya mengirim metadata lesson, content dimuat saat lesson dibuka.

## Content dan batas

Materi memakai react-markdown 10.1.0, skipHtml, tanpa MDX/raw HTML plugin atau
dangerouslySetInnerHTML. URI transform hanya HTTPS, gambar menjadi link manual,
tidak ada request gambar otomatis. React merender judul/label sebagai teks.
Server memeriksa target link/image/autolink/referensi Markdown menggunakan
tokenizer CommonMark markdown-it-py 4.3.0 (bukan renderer). Semua target aktif
memakai kebijakan HTTPS yang sama dengan resources. Contoh literal di code fence,
inline code dan teks URL biasa tidak dianggap tautan aktif. Simpan dan publish
memvalidasi kembali; data lama tidak dihapus atau ditulis ulang saat upgrade.
Resources tambahan maksimum sepuluh link HTTPS dengan validasi format host,
tanpa credential/control character/backslash dan menolak literal IP privat/
localhost/bentuk IPv4 pendek, Unicode kategori Cc/Cf/Cs (mentah maupun encoded),
encoding invalid dan trailing dot setelah IDNA. Host tidak di-resolve, dan tidak di-fetch server;
ini link pengguna, bukan mekanisme upload/proxy berkas. Link tab baru memakai
noopener/noreferrer. File upload/video hosting memerlukan desain tersendiri.

Course cap 500/tenant, module cap 30/course, lesson cap 50/module, teacher cap
50/course, content 30.000
karakter, judul 160, deskripsi 2.000. API dan BFF membatasi POST ke 256 KiB sebelum
parse. Courses list paginated maksimal 50, default 30; tree dibatasi caps tadi.
Version/request extra fields divalidasi server. Origin exact pada setiap mutation,
BFF hanya meneruskan route/metode/query yang diizinkan, cookie opak dan ingress
identity yang sudah diverifikasi. CSP/headers lama tetap berlaku.

POST /courses dan child memiliki budget 60/menit per membership tenant/user
terautentikasi admin/guru. Admission memakai transaksi runtime tersendiri sebelum
parse body; counter tetap commit bila validasi/lookup/version berikutnya gagal.
UPSERT atomik dengan satu row per membership; request anonim/siswa tidak membuat
row. Counter jenuh pada 61; request berikutnya tidak menulis ulang row sampai
window berakhir. 429 membawa Retry-After: 60 melalui BFF; editor tetap utuh.
Retensi existing menghapus budget lebih tua satu hari. Ini budget aplikasi,
bukan pengganti rate limit ingress produksi.

Migration 0007 menambah FORCE RLS budget dan trigger assignment. INSERT mengunci
user dan membership FOR SHARE agar berserial dengan perubahan role/status.
Setiap perubahan aktual role/status membership atau status user menghapus
assignment terkait, sehingga reaktivasi tidak menghidupkan akses lama. Trigger
definer dimiliki maaher_definer, fixed search_path, tanpa PUBLIC EXECUTE; grants
tambahan hanya SELECT/DELETE assignment dan DELETE/SELECT(window_start) budget.
Cleanup tidak mengunci course agar urutan lock tidak terbalik dengan authoring.
Perubahan permission ini tidak mengubah materi/state/version kursus; audit
course.teacher_access_revoked dibuat bila ada actor admin tenant tervalidasi.
SQL maintenance tanpa actor tidak direkayasa menjadi actor aplikasi.

## Migrasi dan gate

Upgrade 0005→0006→0007 mempertahankan akun, binding, secret, session dan materi.
0007 membersihkan assignment yang saat upgrade tidak lagi valid, mempertahankan
assignment aktif yang valid. Siklus role sebelum upgrade tidak bisa disimpulkan
dari schema lama; admin perlu meninjau assignment bila pernah terjadi siklus itu.
Downgrade 0007→0006 mempertahankan materi tetapi menghapus guard/budget baru dan
tidak mengembalikan assignment yang dicabut. Downgrade 0006→0005 **menghapus
seluruh data kursus**; kini diblokir bila ada course, kecuali operator memberikan
`alembic -x allow_course_data_loss=yes ... downgrade ...` setelah backup/review.
Database kosong tetap dapat roundtrip tanpa ack. Tidak ada bypass prefix nama DB.
Tes fixture roundtrip seluruh migration dan preservasi identity auth berjalan
pada DB sintetis kosong baru. Tidak ada migrasi Mac/produksi dari cloud.

UAT utama Mac f38c231 dan review LOW awal dilaporkan pemilik. UAT delta 0007,
re-review independen Claude, review penuh auth parent, CI remote, production MFA/recovery,
SMTP/inbox, backup/restore serta ingress/TLS tetap menunggu bukti/gate masing-masing.
