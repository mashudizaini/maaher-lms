# ADR-006 — kursus, modul dan pelajaran

Status: implementasi development LMS-02 setelah instruksi lanjut pemilik pada
10 November 2026. Source asli Maaher; perilaku Timedoor belum diverifikasi REA.
Auth0 parent branch belum mendapat signoff produksi; modul ini tidak melewati gate.

## Permission dan database

| Peran | Pengelolaan |
|---|---|
| Admin tenant aktif dengan session/MFA yang sah | Buat kursus, kelola seluruh kursus tenant, assign guru, arsip/pulihkan |
| Guru aktif | Baca/edit/publish hanya kursus yang ditugaskan; tanpa create/assign/arsip |
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

Edit metadata, struktur, materi dan assignment mengembalikan course ke draft.
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
Resources tambahan maksimum sepuluh link HTTPS dengan validasi format host,
tanpa credential/control character/backslash dan menolak literal IP privat/
localhost/bentuk IPv4 pendek. Host tidak di-resolve, dan tidak di-fetch server;
ini link pengguna, bukan mekanisme upload/proxy berkas. Link tab baru memakai
noopener/noreferrer. File upload/video hosting memerlukan desain tersendiri.

Course cap 500/tenant, module cap 30/course, lesson cap 50/module, teacher cap
50/course, content 30.000
karakter, judul 160, deskripsi 2.000. API dan BFF membatasi POST ke 256 KiB sebelum
parse. Courses list paginated maksimal 50, default 30; tree dibatasi caps tadi.
Version/request extra fields divalidasi server. Origin exact pada setiap mutation,
BFF hanya meneruskan route/metode/query yang diizinkan, cookie opak dan ingress
identity yang sudah diverifikasi. CSP/headers lama tetap berlaku.

## Migrasi dan gate

Upgrade 0005→0006 menambah schema/fungsi tanpa mengubah akun, binding, secret atau
session Auth0. Downgrade ke 0005 **menghapus seluruh data kursus** dan fungsi baru,
mempertahankan auth. Backup terlebih dahulu; review rollback sebelum dipakai.
Tes fixture roundtrip seluruh migration dan preservasi identity auth berjalan
pada DB sintetis kosong baru. Tidak ada migrasi Mac/produksi dari cloud.

Review independen Claude, UAT Mac LMS-02, CI remote, production MFA/recovery,
SMTP/inbox, backup/restore serta ingress/TLS tetap menunggu bukti/gate masing-masing.
