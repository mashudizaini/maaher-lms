# LMS-01 — tahap 1: session dan batas tenant

Disetujui oleh permintaan pemilik 2026-11-09 dan backlog LMS-01.

Lingkup tahap ini: API login/logout dengan opaque session PostgreSQL, daftar
membership sendiri, pemilihan tenant tervalidasi, role check, audit dan RLS.
Akun awal diprovisi operator melalui terminal, bukan registrasi publik.

File terdampak: apps/api/app, apps/api/migrations, dependensi API,
apps/api/tests, dokumentasi handoff. UI dan Compose belum dihubungkan ke auth.

Acceptance: cookie HttpOnly/Secure/SameSite; hash password Argon2; token hanya
disimpan sebagai SHA-256; expiry/revocation diperiksa setiap request; Origin
diwajibkan pada mutation; tenant selector hanya diterima setelah membership aktif
terverifikasi; runtime DB role tidak superuser/BYPASSRLS/pemilik tabel;
RLS gagal tertutup tanpa konteks dan menolak akses antar-tenant.

Tes: unit authorization dan token; integration PostgreSQL untuk login,
logout, expiry, revocation, selector tenant palsu, role dan RLS langsung;
upgrade/downgrade/upgrade database disposable.

Asumsi: database pengembangan khusus, TLS pada deployment, Origin tunggal yang
dikonfigurasi, migration role terpisah dari runtime role.

## Perluasan disetujui pemilik — penyelesaian LMS-01, 2026-11-09

Permintaan lanjutan pemilik mencakup invitation, reset password, audit auth,
MFA sesuai arsitektur, checklist bukti dan diff terbaru. Lingkup implementasi
ditambah API lifecycle auth, migrasi `0002_auth_lifecycle`, mail worker terpisah,
halaman `/auth` dan BFF, konfigurasi role/Compose/CI, lock dan audit dependensi,
tes PostgreSQL serta browser. Ini menggantikan pembatasan tahap 1 di atas.

Acceptance tambahan: undangan admin terikat tenant/role/email, sekali pakai,
berkedaluwarsa; akun lama wajib login sendiri dan password/role lama tidak
diubah; reset respons generik, token sekali pakai, semua session lama dicabut;
reset tidak menonaktifkan MFA; admin wajib MFA setiap login; kode tidak dapat
di-replay dan percobaan dibatasi lintas session; audit append-only tanpa token/
password; pencabutan membership menghentikan akses tenant tersebut tanpa
menghapus akses tenant lain. Pengiriman email memakai outbox terenkripsi dan
role worker terpisah, bukan pengiriman dari request API.

Asumsi: HTTPS origin tunggal; secret encryption stabil dan dibackup terpisah;
waktu server sinkron; role migration/API/mail terpisah; semua validasi memakai
data sintetis. Tidak ada registrasi publik, operator API, course, enrollment,
grading atau runner. Operator MFA, provider email dan pemulihan faktor tetap
membutuhkan konfigurasi/verifikasi eksternal, bukan bypass lokal.

Status dan bukti aktual: `docs/LMS-01-CHECKLIST.md` dan handoff. Jangan menyatakan
selesai sampai acceptance yang bergantung eksternal serta review terpenuhi.

## Perbaikan review Claude — disetujui permintaan pemilik

Lingkup tambahan terbatas pada seluruh temuan H1/M1–M6/L1–L7 dalam
`reviews/LMS-01-claude.md`: trust dan recovery MFA, pemisahan privilege auth,
commit ordering, bounded traffic/retention, throttle, poison outbox, keyring,
CI, CSP/header dan workflow anggota yang dapat digunakan. Migrasi baru 0003;
tes regresi memakai SQL runtime aktual, uvicorn nyata dengan barrier/failure
commit, database kosong terpisah, serta browser. Tidak mengubah laporan Claude.
Tidak mengaktifkan produksi, meng-apply patch historis, menghapus database/
container lama, menyentuh data pengguna, merge atau deploy. Trust operator
produksi tetap memerlukan keputusan/config independen dan review ulang.
