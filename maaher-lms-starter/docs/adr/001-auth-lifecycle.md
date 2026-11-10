# ADR-001 — session, invitation, reset dan MFA LMS-01

**Diperbarui oleh [ADR-002](002-auth-security-review.md) setelah review Claude.**
Enrollment/recovery sekarang memerlukan trust operator independen; privilege
auth terpisah, commit sebelum respons, retensi dan keyring mengikuti ADR-002.
Uraian lama di bawah adalah konteks historis bila bertentangan dengan ADR-002.

Status: implementasi lokal untuk diuji/review; pilihan penyedia email dan
kontrol operator belum disetujui/terverifikasi. Bukan persetujuan release.

## Keputusan implementasi

Auth memakai opaque session 256 bit dalam PostgreSQL. Hanya SHA-256 token
disimpan pada tabel session/invitation/reset. Cookie HttpOnly, Secure,
SameSite=Lax, lifetime delapan jam; mutation memerlukan Origin persis
`APP_ORIGIN`. Pengecualian HTTP hanya dengan `APP_ENV=local` dan
`LOCAL_INSECURE_COOKIES=true` secara eksplisit. Password memakai pwdlib/Argon2.
MFA memakai [PyOTP](https://pyauth.github.io/pyotp/); secret memakai
[Fernet](https://cryptography.io/en/latest/fernet/), bukan kriptografi buatan.

Semua akses tenant berasal dari session aktif dan membership aktif pada tenant
aktif. Header X-Tenant-ID hanya selector. Tenant admin harus enroll dan verify
TOTP; session baru selalu belum diverifikasi. Setelah verify, token session
dirotasi tanpa memperpanjang expiry. Kode yang sudah diterima ditolak kembali,
termasuk dari session/proses lain. Batas lima percobaan per user per 15 menit
mencakup enroll/verify dan bertahan melewati login/restart; pending enrollment
berlaku sepuluh menit. Jendela kode ± satu langkah 30 detik; sinkronisasi waktu
host wajib. Jika user sudah enroll, akses tenant non-admin juga memerlukan MFA.
Endpoint pemulihan/metadata akun sendiri tetap tersedia tanpa elevasi MFA.

Undangan dibuat admin yang lolos MFA untuk tenant tervalidasi, role allowlist,
email dan masa berlaku satu jam. Pengiriman ulang membatalkan undangan lama.
Penerimaan memeriksa kembali tenant dan admin pengundang; pencabutan membership
admin membatalkan otoritas undangannya. Akun baru memilih password minimal 15
karakter; akun lama harus punya session dengan email penerima yang cocok.
Undangan tidak mengubah password/role membership lama dan tidak mengaktifkan
ulang membership revoked. Tidak ada login otomatis melalui token undangan.

Request reset memberi respons generik 202 untuk akun ada/tidak ada/terbatas.
Maksimal lima email per alamat per 15 menit; token baru membatalkan yang lama.
Konfirmasi satu kali, satu jam, mengganti hash dan mencabut seluruh session
serta token reset user secara atomik. MFA tidak dihapus. Lock transaksi
mencegah dua konsumsi token dan login bersamaan dengan reset menghidupkan
kembali password lama. Login memiliki batas sepuluh percobaan per email/15 menit;
edge rate limit global tetap wajib sebelum akses publik.

Audit tenant menyimpan actor/action/target/waktu, hanya admin tenant aktif
dengan MFA yang dapat membaca. Lifecycle login/logout/reset/MFA disimpan pada
`auth_events` global dan user hanya membaca riwayat sendiri; unknown login dan
throttle tidak menyimpan email mentah. Keduanya append-only bagi role API.
Token, password, kode dan URI MFA tidak dicatat dalam audit.

Operasi acceptance/reset/revoke yang perlu hak melebihi role API menggunakan
fungsi database terbatas, SECURITY DEFINER dengan search_path tetap dan
EXECUTE dicabut dari PUBLIC. Fungsi memvalidasi token atau konteks actor dan
membership sendiri; parameter tenant tetap divalidasi. Tenant tables dan
invitation memakai ENABLE/FORCE RLS. Migration owner harus dipercaya dan
memiliki BYPASSRLS/superuser; credential tersebut tidak masuk API/worker.
Global auth tables (users/sessions/reset/throttle) bukan resource satu tenant;
runtime hanya memperoleh grant yang diperlukan. RLS context adalah kontrak
backend tepercaya, bukan cara mengamankan koneksi SQL arbitrer milik pengguna.

## Email dan batas proses

API memasukkan token terenkripsi ke `auth_mail_outbox` dalam transaksi yang
sama dengan invitation/reset. API hanya INSERT, tidak boleh membaca antrean.
Worker terpisah memakai LOGIN yang mewarisi `maaher_mailer`, tanpa role API,
superuser, BYPASSRLS atau ownership tabel. Worker menolak credential owner/API.
Worker tidak punya SELECT atas users/session/MFA. Tidak ada socket Docker,
subprocess atau eksekusi kode siswa dalam request API/worker.

Worker memakai SMTP over TLS terverifikasi (port default 465), maksimum lima
percobaan, retry tertunda 15 menit dan SKIP LOCKED. Setelah SMTP menerima,
payload token dihapus. Payload kedaluwarsa dihapus saat worker berikutnya
berjalan. Crash setelah pengiriman tetapi sebelum commit bisa menyebabkan
email duplikat; token tetap sekali pakai. Operator perlu memonitor attempts,
expiry dan antrean belum terkirim. Test memakai send callback tiruan, bukan
SMTP nyata. Tautan memakai `/auth#invitation=...` atau
`/auth#password-reset=...`; fragmen tidak masuk access log HTTP dan segera
dihapus dari address bar. Jangan memasang analytics pihak ketiga pada auth.

Halaman `/auth` dan BFF hanya meneruskan route allowlist, cookie session dan
selector tenant; API tetap otoritas. Browser tidak membaca token session
HttpOnly. BFF tidak menerima destination URL dari client. API port tidak
dipublikasikan oleh Compose.

## Konfigurasi konkret yang belum tersedia

1. Audit server dan pilih penyedia SMTP transaksional. Siapkan domain pengirim
   terverifikasi beserta SPF/DKIM/DMARC, akun SMTP, `SMTP_HOST`, `SMTP_PORT`,
   `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`. Pastikan outbound TLS tersedia;
   atur scheduler untuk `python -m app.mail_worker` dan monitoring retry/expiry.
   Verifikasi invitation dan reset sampai inbox UAT dengan persetujuan pemilik.
   Belum ada SMTP account/domain yang dikonfigurasi atau email nyata dikirim.
2. Simpan `AUTH_ENCRYPTION_KEY` Fernet stabil dalam secret store; generate
   melalui `Fernet.generate_key()` secara lokal, jangan kirim dalam chat/commit.
   Berikan hanya ke API dan worker; web hanya memerlukan APP_ORIGIN/API_BASE_URL.
   Backup key terpisah dari database. Kehilangan key membuat MFA/outbox tidak
   terbaca. Rotasi membutuhkan re-enkripsi data melalui prosedur administratif
   teruji; jangan sekadar mengganti nilai environment.
3. Buat role migration, API dan mail terpisah. Untuk cluster baru jalankan
   `infra/development-roles.sql` pada database tujuan. Untuk cluster tahap 1
   yang sudah punya `maaher_runtime`, buat hanya `maaher_mailer` sekali sebelum
   upgrade; jangan menjalankan ulang CREATE ROLE yang sudah ada. Buat LOGIN
   API mewarisi hanya maaher_runtime dan LOGIN email hanya maaher_mailer;
   password ditentukan lewat prompt `createuser --pwprompt`, bukan argumen/chat.
   Isi MIGRATION_DATABASE_URL/DATABASE_URL/MAIL_DATABASE_URL secara terpisah.
   Semua URL harus menunjuk database tujuan yang sama; schema/grant per database.
4. Konfigurasi origin HTTPS tunggal tepat tanpa trailing slash, TLS, sinkronisasi
   jam dan edge rate limit. Next memakai `API_BASE_URL` internal; role owner
   tidak lagi otomatis diberikan Compose kepada API. Jangan gunakan Compose
   starter lama sebelum mengisi konfigurasi baru. Tidak ada migrasi otomatis
   saat API startup: migration job dipanggil terpisah oleh manusia.
5. **MFA operator belum terverifikasi.** Tidak ada endpoint atau role operator
   global di aplikasi. CLI provision hanya untuk pengembangan sintetis lokal.
   Sebelum operator menangani host/DB/secret nyata, pilih dan uji MFA untuk
   akses administratif (identity/host/secret store), least privilege, audit,
   prosedur emergency dan pemulihan identitas. TOTP tenant admin tidak memenuhi
   persyaratan operator tersebut. Jangan menambah trusted-header bypass.
6. **Pemulihan perangkat MFA belum tersedia sebagai layanan pengguna.** Tidak
   ada reset/disable faktor via password atau token email. Dibutuhkan kebijakan
   verifikasi identitas, persetujuan operator bermfa, audit dan uji pemulihan
   sebelum menerima admin nyata. Jangan menghapus faktor/menandai session
   verified lewat SQL sebagai alur pengguna. OIDC/WebAuthn dapat dievaluasi
   setelah audit tanpa mengubah prinsip session dan tenant isolation.

## Migrasi dan rollback

`0002_auth_lifecycle` menambah tabel tanpa menghapus user/membership/session
tahap 1; session lama diberi mfa_verified=false. Suite menguji upgrade data lama,
downgrade ke 0001 lalu upgrade, serta downgrade base lalu upgrade. Perbaikan
rollback 0001 tetap ada: policy member_tenants dihapus sebelum memberships.

Downgrade 0002 menghapus invitations, reset, faktor MFA, outbox dan auth audit,
beserta data/kolom barunya; user/membership/session tahap 1 tetap ada. Downgrade
base menghapus seluruh identity dan datanya. Keduanya hanya dijalankan pada DB
disposable dalam validasi ini. Rollback nyata perlu backup/restore drill,
maintenance, kecocokan versi kode/schema dan keputusan manusia; menjalankan
kode lama tanpa MFA bukan rollback aman untuk admin produksi. Role grup tetap
ada setelah rollback. Tidak ada merge/deploy/SMTP nyata dalam pekerjaan ini.
