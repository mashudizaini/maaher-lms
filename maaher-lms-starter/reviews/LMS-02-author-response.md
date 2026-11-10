# LMS-02 — respons author atas tujuh LOW

**Koreksi re-review:** pemilik kemudian menyampaikan delapan bullet LOW pada
laporan asli, tujuh FIXED dan request._body OPEN pada fe54142, dengan verdict
APPROVED_WITH_NOTES untuk delta kursus. Ringkasan di bawah memetakan tujuh yang
tersedia pada pesan awal; ia bukan hitungan lengkap laporan asli. Lihat relay
re-review 20261111 dan handoff LMS-03 untuk tindak lanjut ASGI/worker serta N1–N4.

10 November 2026. Author Codex; base perbaikan **f4f9cf7**, branch
feat/LMS-02-course-management. Laporan yang disampaikan pemilik dicatat di
[review relay](LMS-02-review-relay-20261110.md); label berikut dibuat author.
Status setiap item: **diimplementasikan dan diuji author, menunggu re-review
independen**. Bukan deklarasi CLOSED/approval oleh Claude. Auth parent hanya
ditinjau terarah pada review sebelumnya dan tetap memerlukan review penuh.

| ID lokal | Temuan dan perubahan | Bukti regresi |
|---|---|---|
| L2-01 | Assignment/cabut mempertahankan state kursus; version/audit tetap naik. Edit materi tetap draft. | API published add/revoke + content preservation; browser memeriksa Tarik publikasi tetap ada pada kedua aksi. |
| L2-02 | Trigger menghapus assignment pada setiap perubahan aktual role/status membership atau status user. INSERT mengunci user/membership FOR SHARE sehingga tidak balapan dengan perubahan role/status. Tidak otomatis kembali setelah reaktivasi. | Role cycle melalui API; revoke/reactivate membership/user; dua urutan race SQL pada koneksi nyata; assignment eksplisit baru mengembalikan akses. |
| L2-03 | RLS parent/child menyembunyikan arsip dari guru. Admin tetap dapat baca/pulihkan; assignment valid tidak dihapus karena archive saja. Checkbox arsip hanya admin. | API list/detail/lesson dan SELECT runtime langsung ke module/lesson kosong; admin read dan restore berhasil. |
| L2-04 | Tokenizer CommonMark memvalidasi semua target link/image/autolink/referensi di server saat simpan; publish memeriksa legacy material/resources lagi. Tidak merender HTML atau fetch aset. | HTTP/relative/mailto/javascript/data/ref/autolink ditolak, contoh literal kode sah; request 422 dan legacy publish 409 tidak mengubah state/version; browser editor dapat diperbaiki lalu disimpan. |
| L2-05 | URL menolak Cc/Cf/Cs raw/percent-encoded, encoding invalid, serta trailing dot setelah IDNA. Filter frontend juga menolak karakter tersembunyi/trailing dot. | Resource dan Markdown: bidi/zero-width/BOM/C0/invalid UTF-8/trailing dot termasuk ideographic dot; kebijakan host/IP lama tetap diuji. |
| L2-06 | Downgrade 0006 yang berisi course menolak berjalan tanpa `-x allow_course_data_loss=yes`. Tidak ada bypass prefix DB. Upgrade 0006 tidak ditulis ulang; guard downgrade dibackport. | Fixture seeded 0006→0007 menjaga materi/state/version/valid assignment; 7→6→7 menjaga materi; downgrade tanpa ack gagal dan transaksi mempertahankan head/data; ack hanya dipakai pada DB sintetis disposable. |
| L2-07 | Detail/lock memakai daftar field SQL eksplisit. POST kursus dibatasi 60/menit per tenant/user terautentikasi, counter commit sebelum parse; RLS/retensi dan header Retry-After BFF. | Field set response tepat; invalid body tetap terhitung; slot terakhir dua koneksi hanya satu lolos; actor lain/window baru lolos; anonim/siswa tak membuat row; RLS/retensi; browser 429 mempertahankan editor. |

## Bukti dan batas

API lengkap **244 passed, 0 skip, 2 warning deprecation** (119.31s), termasuk
**46 kasus baru** pada test_course_review.py dan seluruh 198 tes sebelumnya.
Subset course+review **74 passed** (90.80s). Fixture juga menguji rollback auth
lama hingga base dan upgrade kembali. Python 3.12.14/Linux, PostgreSQL 16.15
dengan runtime non-owner/non-BYPASSRLS, role auth/operator/mail/maintenance
terpisah. **11 tes browser lulus, 0 skip**: kursus 2, auth baseline 7, OIDC
FIDO2 sintetis 1 dan dev-TOTP sintetis 1. Build/typecheck, 12 tes scripts,
16 tes Action, pip check dan snapshot
PyPI **41 pin, 0 findings/errors**, npm production audit **0 vulnerabilities**.
Hasil browser final dan DB evidence tercantum pada handoff; signed synthetic
provider tidak membuktikan konfigurasi Auth0 tenant nyata atau security key fisik.

Upgrade 0007 hanya membersihkan assignment yang **saat upgrade** tidak valid.
Schema sebelumnya tidak merekam waktu assignment, sehingga siklus role yang
sudah kembali teacher sebelum upgrade tidak bisa disimpulkan. Pertahankan
assignment valid dan minta admin meninjau riwayat yang diketahui; tidak
menghapus semua assignment secara spekulatif. Trigger selanjutnya mencegah
pengulangan. Cleanup tidak mengubah version/state kursus agar tidak membalik
urutan lock parent-course→membership; otorisasi/RLS diperiksa pada request baru.

Materi legacy tidak ditulis ulang saat migrasi; bila link melanggar, perbaiki
sebelum save/publish. Kursus yang telanjur draft oleh bug lama tidak otomatis
dipublikasikan. Downgrade 7→6 tidak mengembalikan assignment yang dicabut dan
menonaktifkan guard/budget baru. Downgrade 6→5 tetap destruktif bila operator
memberi ack; backup/review wajib. Tidak ada rollback pada DB UAT pengguna.

UAT Mac pada delta baru, re-review, CI remote, build image aplikasi dan gate
produksi belum terverifikasi. Tidak ada merge/deploy atau enrollment LMS-03.
Laporan Claude LMS-01 historis dan artifact awal LMS-02 dipertahankan.
