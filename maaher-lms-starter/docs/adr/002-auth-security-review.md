# ADR-002 — trust MFA dan boundary auth setelah review Claude

Status: hardening lokal untuk review ulang. Menggantikan bagian autentikasi
ADR-001 yang bertentangan. **Tidak ada persetujuan produksi/operator trust.**
Laporan independen `reviews/LMS-01-claude.md` tetap utuh dan berstatus
CHANGES_REQUESTED; respons per temuan ada di `reviews/LMS-01-author-response.md`.

## Trust bootstrap dan recovery

Password serta email login/reset dianggap dapat dikuasai penyerang. Keduanya
tidak memberi hak menambahkan faktor, termasuk enrollment pertama. Client
membuat request ID yang terikat pada user, session opak yang sedang dipakai,
purpose bootstrap/recovery dan expiry sepuluh menit. Request ID bukan otorisasi.
Operator harus mengikat verifikasi identitas ke perangkat/session pemilik yang
benar, bukan sekadar menerima UUID dari orang yang mengaku pemilik.

Hanya role terpisah `maaher_mfa_operator` dapat menyetujui request. Otorisasi
acak 256 bit disimpan sebagai SHA-256, sekali pakai, terikat session/purpose,
dan diberikan melalui jalur independen setelah identitas/perangkat diverifikasi.
Tidak pernah melalui email login/reset, trusted header dari browser, atau
boolean `OPERATOR_MFA_VERIFIED`. Audit operator menyimpan LOGIN database,
request ID, purpose, referensi bukti non-PII dan waktu; tetap ada setelah session
ditutup. Role operator tidak mewarisi runtime/auth/definer dan tidak membaca hash.

**Adapter saat ini khusus sintetis.** CLI hanya mengizinkan APP_ENV=local;
helper hanya local/test; fungsi SQL juga menolak database selain
`maaher_test_*`. Ini tidak boleh diakali dengan mengganti nama database nyata.
Pemakaian nyata memerlukan keputusan/prosedur baru yang direview: misalnya
operator dengan MFA host/identity/secret-store memverifikasi langsung identitas
yang telah dikenal/terdaftar, atau IdP/WebAuthn independen yang sudah terdaftar
sebelum kompromi. Perlu root operator pertama, pencabutan hak operator, audit,
emergency access dan penyerahan kode ke perangkat pemilik. Email yang sama
dengan reset password bukan root trust yang sah. Belum ada keputusan atau
integrasi eksternal yang dianggap disetujui oleh diamnya pemilik.

Enrollment mengonsumsi otorisasi sebelum mengeluarkan URI TOTP. Faktor baru
disimpan sebagai pending selama sepuluh menit; faktor aktif tidak diganti dulu.
Recovery juga memerlukan password pengganti minimal 15 karakter. Setelah OTP
baru benar, transaksi mengganti faktor/password, mencabut semua session/reset
token, membuat session baru ter-MFA dan mencatat audit. Gagal/expired sebelum
konfirmasi tidak menghapus faktor lama. Login/reset/recovery memakai lock email
yang sama agar login memakai password lama tidak membuat session setelah revoke.

Faktor warisan dari skema 0002 **tidak otomatis dipercaya**: migrasi menambahkan
`trust_verified=false` dan menghapus status elevasi MFA session lama, tanpa
menghapus ciphertext/identity. OTP faktor warisan tidak dapat menaikkan session.
Pemilik sah memerlukan jalur recovery independen. Faktor baru hanya ditandai
trusted setelah konfirmasi dari enrollment berotorisasi. Admin yang diundang
tetap tidak memperoleh akses tenant sebelum langkah ini selesai.

Batas recovery yang sudah diimplementasikan/diuji: pemilik masih dapat membuat
session dengan password valid, lalu mengganti faktor lewat proof independen.
Jika password dan email sama-sama tidak lagi dapat diakses pemilik, **full
account recovery belum tersedia**. Provider/root trust yang disetujui harus
dapat memverifikasi identitas/perangkat terdaftar tanpa keduanya sebelum
menerbitkan konteks recovery terbatas. Jangan menyebut adapter saat ini sebagai
penyelesaian skenario kehilangan seluruh credential; H1 end-to-end tetap gate.

## Pemisahan privilege database

| Credential/role | Hak dan batas |
|---|---|
| DATABASE_URL / maaher_runtime | Query tenant dengan RLS; tidak SELECT users/hash/session/faktor/auth history, tidak INSERT session true maupun false, tidak memanggil fungsi reset/accept/otorisasi MFA. |
| AUTH_DATABASE_URL / maaher_auth | Boundary verifier password/TOTP. Memiliki akses hash dan session yang dibutuhkan verifier; tidak owner/BYPASSRLS dan tidak mewarisi runtime. Dipakai hanya kode auth berparameter, bukan query course/tenant masa depan. |
| maaher_definer | NOLOGIN, NOSUPERUSER, NOCREATEROLE, BYPASSRLS terbatas untuk fungsi yang melintasi tabel. Hanya grant eksplisit; tidak memiliki tabel, CREATE schema, SELECT password hash/secret MFA atau INSERT session. |
| MFA_OPERATOR_DATABASE_URL / maaher_mfa_operator | Hanya EXECUTE otorisasi request sintetis, bukan auth atau DDL. Tidak diberikan ke proses API/web. |
| MAIL_DATABASE_URL / maaher_mailer | Hanya outbox, tanpa users/session/MFA. |
| MAINTENANCE_DATABASE_URL / maaher_maintenance | Hanya EXECUTE fungsi retensi dengan horizon tetap; bukan akses bebas DELETE tabel. |

Role LOGIN API dan auth harus berbeda dan tidak menjadi anggota kedua grup.
Runtime validator menolak superuser/BYPASSRLS/owner/role bercampur. Fungsi
SECURITY DEFINER dimiliki maaher_definer, bukan migration superuser, memakai
`search_path=pg_catalog,public,pg_temp`, dan tidak dapat di-EXECUTE PUBLIC.
Role definer tidak boleh diberikan kepada LOGIN service. Provision role grup
oleh administrator cluster sebelum migrasi; gunakan password prompt/secret store
untuk LOGIN, bukan password pada command/chat/commit.

Resolver session hanya mengembalikan identitas/status MFA untuk hash capability
session yang valid; runtime tidak dapat mencari seluruh tabel session. RLS
runtime memperoleh identitas dari session capability tersebut, bukan dari GUC
`app.user_id` yang dapat dipalsukan koneksi SQL. Selector tenant tetap harus
memiliki membership aktif. Fungsi list/change membership juga memvalidasi
session MFA secara langsung, tidak percaya GUC admin palsu. Metadata hash tidak
dikirim ke browser. Tidak ada endpoint query SQL arbitrer.

Boundary ini membatasi SQL injection di koneksi tenant; bukan klaim bahwa RCE
proses API atau SQL injection di verifier yang memegang AUTH_DATABASE_URL sudah
aman. Verifier tetap kode sangat tepercaya dan perlu review independen. Secret
auth tidak boleh diberikan ke proses web. Operator dan migration credential
tidak masuk API container. Tidak ada eksekusi kode siswa/akses socket Docker.

## Commit sebelum respons

Semua dependency transaksi FastAPI memakai `scope='function'`. Teardown
psycopg (COMMIT) selesai sebelum response start/cookie. Error database saat
handler/commit menjadi 503 JSON terkontrol, tanpa detail SQL/secret dan tanpa
cookie sukses. Kegagalan ACK commit bisa mempunyai hasil durable yang belum
diketahui; pesan meminta pemeriksaan status, bukan otomatis mengulang mutation.
Tidak ada assertion yang menerima 200 saat commit gagal. Tes memakai uvicorn
nyata, barrier pada COMMIT, observer PostgreSQL terpisah serta commit gagal
pada login dan logout; cookie/header dan state durable diperiksa.

## Pembatasan biaya dan retensi

Sebelum hashing password/token anonim: anggaran PostgreSQL 120 request/menit
global dan 30/menit per identitas jaringan tepercaya. Empat advisory slot
membatasi pekerjaan password bersamaan lintas worker. Counter mempunyai
keyspace tetap lima kind × 4096 bucket; random email/token tidak menambah
keyspace tanpa batas. Login email tak dikenal tidak menulis satu auth event
per permintaan; counters mengagregasi aktivitasnya. Tidak ada key email mentah
baru pada tabel login_attempts lama.

Kegagalan akun diikat email+IP; password benar tetap dapat masuk di bawah
anggaran sumber daya dan mereset counter. Kuota OTP biasa diikat user+IP,
bertahan lintas login; jaringan pemilik lain tidak memakai kuota penyerang.
Enrollment/recovery yang diotorisasi operator mempunyai budget tersendiri.
Keberhasilan OTP mereset kuotanya; replay tetap ditolak oleh counter TOTP.
Ini bukan jaminan anti-DDoS: NAT bersama, collision bucket konservatif dan
global capacity pressure bisa menolak sementara. Edge rate limit/tuning beban
dan verifikasi alamat ingress tetap gate sebelum exposure.

Pool user dibatasi 100 session password-only dan 20 ter-MFA. Login password
tidak mengusir session MFA atau request/pending recovery yang sudah diotorisasi.
Session password-only lama tanpa otorisasi dapat diganti agar credential holder
tidak memenuhi pool lalu memveto setiap login pemilik. Permintaan yang disetujui
operator dilindungi sampai expiry; seluruh pool yang dipin operator merupakan
batas kapasitas administratif, bukan authority yang dapat dibuat email/password.

Ingress produksi wajib disiapkan: proxy tepercaya harus menghapus/mengganti
header dari publik, menetapkan `cf-connecting-ip` asli serta `x-maaher-edge-key`
yang cocok EDGE_SHARED_SECRET. BFF memvalidasi key tersebut, lalu meneruskan IP
canonical dengan BFF_API_SECRET berbeda kepada API. API tidak mempercayai
X-Forwarded-For atau header IP browser tanpa key. Tidak ada fallback produksi
ke IP yang diklaim client; konfigurasi hilang ditolak. Mode local/test memakai
peer socket untuk data sintetis. Kedua secret dibuat acak panjang dan hanya
diberikan pada service terkait. Konfigurasi Cloudflare/proxy nyata belum diuji.

Worker mail menghapus token dan alamat saat sent/dead/expired. Payload tidak
dapat didekripsi atau format rusak dikarantina dengan error code tetap, tanpa
menyimpan secret/exception; loop melanjutkan pesan valid. Retry maksimal lima,
interval sepuluh menit (0,10,20,30,40 dalam TTL satu jam); token tidak diperpanjang.
Scheduler terlambat dapat membuat percobaan aktual lebih sedikit. SMTP nyata
belum dikonfigurasi/dikirim; tes memakai send callback tiruan.

Fungsi retensi menghapus expired session/reset/pending request, counter lama
>1 hari, auth audit >30 hari, tenant/operator audit >365 hari, invitation
>7 hari setelah expiry dan outbox selesai/expired. Identity/membership aktif
tidak dihapus. Angka ini adalah kebijakan sintetis yang diuji, **belum kebijakan
retensi data siswa yang disetujui**. CLI menolak produksi dan database non-test.
Setelah keputusan pemilik, perlu jadwal/monitoring, legal hold/retensi audit,
backup/restore dan proses perubahan kebijakan terpisah. Tidak ada cleanup pada
database/container lama atau data pengguna dalam pekerjaan ini.

## Rotasi key dan web

AUTH_ENCRYPTION_KEYS berupa JSON key-id→Fernet key, AUTH_ACTIVE_KEY_ID menunjuk
key aktif. Ciphertext baru berprefix key-id; ciphertext legacy masih dapat
dibaca dengan key lama yang ditahan MultiFernet. Prosedur sintetis:

1. Backup key terpisah dan database; tambahkan key baru sambil menahan semua
   key lama. Set active ID baru di API/worker secara konsisten.
2. Pada database test dan maintenance window, jalankan `python -m app.key_rotation`
   dengan koneksi administratif MIGRATION_DATABASE_URL dan APP_ENV=local.
   Seluruh factor, pending enrollment dan outbox dienkripsi ulang satu transaksi;
   error satu baris menggagalkan semuanya. Tidak ada secret dicetak.
3. Verifikasi semua ciphertext terbaca hanya oleh key baru, alur OTP dan token
   email tetap berlaku, lalu retire key lama pada konfigurasi setelah persetujuan.
   Jangan membuang key lama sebelum verifikasi. Prosedur produksi tetap menunggu
   trust operator/backup yang direview; jangan mengakali gate local/test.

Web memakai CSP nonce acak per response dan rendering dinamis. Tidak ada
unsafe-inline/unsafe-eval pada script policy produksi; styling pindah ke CSS.
HSTS, frame/referrer/nosniff/permissions headers berlaku seluruh route, termasuk
BFF. HSTS pada HTTP loopback tidak membuktikan TLS deployment. Browser regression
menyisipkan script tanpa nonce pada HTML parser dan mewajibkan violation serta
non-execution; hydration/alur auth tetap lulus. Daftar anggota dipaginasi per
tenant dan menyediakan ubah peran/revoke berdasarkan anggota terdaftar, bukan
input UUID manual. Self-demotion/revoke ditolak; perubahan admin diserialisasi.

CI memakai token contents:read, action SHA terverifikasi, PostgreSQL disposable,
suite API, browser dan audit dependensi. Hasil lokal tidak sama dengan workflow
GitHub yang sudah dijalankan. SMTP/TLS/ingress/IdP/host MFA belum diverifikasi.

## Migrasi dan rollback

0003 menambah auth request/pending/operator-audit/counter dan flag trust faktor,
memisahkan grant serta mengganti fungsi/policy. Legacy identity/ciphertext
dipertahankan; elevasi MFA lama sengaja dibatalkan. Suite menguji 0001→head,
head→0002→head, head→0001→head, dan base→head pada DB kosong disposable dengan
pemeriksaan preservasi identity serta penghapusan tabel setelah base.

Downgrade 0003 membuang tabel/kolom barunya dan mengembalikan grant/fungsi
0002 yang diketahui lebih lemah. Jangan memakai downgrade sebagai rollback
keamanan produksi. Role grup tetap ada. Sebelum perubahan nyata: maintenance,
backup/restore, audit grant/ownership yang sudah ada dan persetujuan manusia.
Tidak ada migrasi database pengguna, merge atau deploy yang dilakukan.
