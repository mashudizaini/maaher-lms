# ADR-003 — rekomendasi identitas produksi untuk admin/operator

Tanggal: 10 November 2026 WIB.
Status: **PILIHAN AUTH0/OIDC DISETUJUI PEMILIK** pada 10 November 2026.
Pemilik belum memiliki tenant/aplikasi Auth0 dan meminta panduan setup.
Implementasi development tahap pertama dijelaskan pada ADR-004. Persetujuan
provider tidak menetapkan paket berbayar atau membuka bootstrap produksi.
H1 tetap terbuka sampai integrasi nyata, recovery dan review selesai.

## Rekomendasi

Gunakan **Auth0 sebagai IdP terkelola melalui OpenID Connect (OIDC)** untuk
admin dan operator, dengan FIDO2/WebAuthn security key. Daftarkan dua kunci
fisik per operator penting: satu dipakai dan satu disimpan terpisah. Untuk root
trust awal, prioritaskan kunci fisik yang tidak bergantung pada pemulihan akun
cloud/email yang sama dengan akun LMS.

Identitas staff IdP harus dibuat dan diverifikasi sebelum akses LMS admin
diberikan. Mengaktifkan MFA pada akun IdP yang dibuat lewat email yang sudah
dikuasai penyerang tidak menyelesaikan first-enrollment takeover. Pendaftaran
root pertama memerlukan tindakan pemilik pada perangkat tepercaya; penambahan
operator berikutnya memerlukan persetujuan operator yang sudah terverifikasi.

Manfaat praktis: faktor, challenge dan lifecycle IdP dikelola layanan khusus;
Maaher tetap mengelola session aplikasi, membership, izin tenant dan audit.
Menjalankan Keycloak sendiri adalah alternatif jika penyimpanan identitas on-prem
merupakan kebutuhan wajib, dengan tambahan tanggung jawab patch, backup,
availability dan recovery. Dengan kebutuhan saat ini, IdP terkelola menjadi
pilihan awal yang direkomendasikan. Tidak perlu memigrasikan seluruh akun siswa
sekaligus untuk mulai mengintegrasikan identitas staff.

Kemampuan konfigurasi Auth0 yang dikonfirmasi dari source resmi provider:
`policy=all-applications`, `webauthn_roaming.enabled`, dan
`webauthn_roaming.user_verification=required`. Contoh dokumentasi juga menyalakan
email, OTP dan SMS; **jangan menyalin contoh itu sebagai kebijakan staff Maaher**.
Metode lemah/fallback yang tidak memenuhi assurance staff harus dinonaktifkan
atau ditolak oleh kebijakan integrasi. Entitlement paket dan dukungan pengelolaan
serta recovery console IdP perlu diperiksa sebelum adopsi; tidak ada asumsi
semua kemampuan tersedia gratis.

Sumber resmi yang diperiksa:
https://github.com/auth0/terraform-provider-auth0/blob/main/docs/resources/guardian.md

## Pemisahan wewenang

| Identitas | Wewenang |
| --- | --- |
| Siswa/pengajar | Membership dan resource tenant sesuai role aplikasi. Alur password/session saat ini dapat dipertahankan untuk development. |
| Tenant admin | Identity IdP yang terikat sebelumnya, assurance MFA yang diwajibkan, dan membership admin aktif pada tenant tersebut. |
| Operator platform | Allowlist operator terpisah, identity IdP dan step-up yang masih baru. Bukan otomatis semua tenant admin atau semua pengguna satu domain email. |
| Administrator console IdP/host/secret-store | MFA dan recovery terpisah juga wajib pada kontrol infrastruktur ini; MFA login aplikasi saja tidak melindungi root trust. |

## Binding identitas dan session

1. Simpan binding unik `(issuer, subject)` ke user/operator internal melalui
   provisioning terkontrol. Email hanya atribut kontak. Jangan auto-link akun,
   mengangkat role, atau memulihkan user berdasarkan kecocokan email saja.
2. Gunakan library OIDC terpelihara dan Authorization Code + PKCE, state dan
   nonce. Validasi signature/JWKS, issuer, audience, expiry, nonce serta kode
   sekali pakai di server. Tidak ada custom crypto atau penerimaan token/header
   identitas dari browser tanpa verifikasi.
3. Definisikan kontrak assurance provider yang eksplisit. Jangan menyimpulkan
   security-key authentication hanya dari string `mfa` generik. Validasi
   kebijakan/metode dan waktu autentikasi sesuai claim provider yang benar-benar
   tersedia serta terverifikasi. Untuk approve/recovery sensitif, minta step-up
   baru; usulan batas freshness lima menit perlu diuji dan disepakati.
4. Setelah verifikasi, rotasi session opak aplikasi. Membership/status user dan
   tenant tetap diperiksa server-side setiap akses. Claim SSO tidak memberi
   akses tenant/global otomatis dan pencabutan membership tetap berlaku.
5. Approval operator harus terikat target user, session/perangkat pemilik yang
   telah diverifikasi, request ID, purpose, expiry dan satu kali pakai. Mengetahui
   UUID request atau mengendalikan email pemilik bukan bukti identitas target.
6. Operator/migration credential dan Management API credential IdP tidak masuk
   browser/web atau koneksi tenant. Role SQL yang mengeluarkan approval tetap
   minimal dan terpisah dari API tenant. Tidak ada flag environment yang bisa
   menggantikan autentikasi operator.

## Recovery yang disarankan

| Kondisi | Jalur |
| --- | --- |
| Kunci utama hilang, kunci cadangan tersedia | Autentikasi dengan kunci cadangan, cabut kunci yang hilang dan daftarkan pengganti melalui assurance yang sama. |
| Password/email LMS hilang, identity IdP staff masih dapat digunakan | Verifikasi `(issuer, subject)` yang telah diikat sebelumnya, step-up, terbitkan konteks recovery terbatas, ganti credential/faktor yang diperlukan dan cabut session lama. |
| Seluruh faktor IdP hilang | Prosedur manual dengan operator lain yang sudah dipercaya dan bukti identitas terdaftar. Usulan: persetujuan dua pihak, pemberitahuan melalui kontak yang sudah didaftarkan dan penundaan sesuai risiko. Tidak memberikan akses penuh hanya dari email reset. |
| Semua operator kehilangan seluruh faktor | Emergency process dan recovery console IdP harus diuji sebelum produksi; tidak mengandalkan password database atau SQL manual yang menandai session sebagai ter-MFA. |
| Siswa/pengajar belum mempunyai binding independen | Recovery ketika password dan email sama-sama hilang tetap tidak dapat diklaim tersedia. Perlu binding faktor/identitas yang didaftarkan sebelumnya atau prosedur verifikasi lembaga yang dirancang terpisah. |

Recovery code hanya relevan jika diterbitkan melalui enrollment tepercaya,
disimpan offline terpisah dari akun yang dilindungi dan diverifikasi sekali
pakai. Untuk operasi privilege tertinggi, jangan menganggap recovery code
tunggal otomatis memenuhi semua syarat step-up/approval. Kebijakan override,
pencabutan dan emergency access harus jelas serta diaudit.

## Tahap implementasi

1. Buat spike di tenant IdP development dengan akun sintetis dan domain/callback
   yang pasti. Periksa metode MFA, entitlement paket, session/claim assurance,
   kebijakan recovery dan akses console. Tidak memakai identitas siswa nyata.
2. Buat provisioning binding `(issuer, subject)` dan callback OIDC teruji tanpa
   membuka privilege admin. Kredensial diisi melalui secret store/settings;
   dokumentasi menyimpan nama variabel, bukan nilainya.
3. Integrasikan admin login dan operator approval/recovery ke boundary auth
   terkontrol. Tambahkan migrasi baru dan rollback plan; jangan menulis ulang
   migration 0003 yang sudah direview atau membuka adapter test lewat nama DB.
4. Uji bootstrap, recovery, perubahan role, revokasi dan gangguan IdP. Pertahankan
   fail-closed jika provider, signature atau assurance tidak dapat diverifikasi.
5. Claude meninjau integrasi, threat model serta bukti tes. UAT terbatas di HTTPS;
   lanjutkan SMTP/inbox, ingress, backup/restore dan gate operasional lain.
   Pemilik menentukan release setelah gate yang relevan terpenuhi.

## Acceptance yang diperlukan untuk menutup H1

- Password/email LMS yang dicuri tidak dapat mendaftarkan atau mengganti faktor,
  mengaitkan identity IdP baru atau memberi role admin/operator.
- Identity provider sah tetapi `(issuer, subject)` berbeda tetap ditolak,
  termasuk alamat email yang sama.
- Callback dengan signature/issuer/audience/nonce salah, replay code, session
  fixation, assurance terlalu lemah atau step-up terlalu lama ditolak.
- Password/email LMS hilang dapat dipulihkan menggunakan identity independen
  yang telah terdaftar tanpa mengakses inbox LMS. Session lama dan request/reset
  grant yang relevan dicabut; audit tersimpan tanpa secret.
- Hilangnya security key, revokasi operator, emergency recovery dan kegagalan
  IdP diuji. User tidak dapat menyetujui request milik orang lain hanya dengan
  mengirim UUID atau screenshot request.
- Root/operator pertama, pemisahan role SQL, secret-store/console MFA, operator
  cadangan dan backup/restore dapat dijalankan oleh pemilik sesuai runbook.
- Cakupan recovery siswa/pengajar yang belum memiliki binding independen tetap
  ditandai belum tersedia; jangan mengubah status seluruh H1 menjadi CLOSED
  berdasarkan pengujian staff saja.

Pilihan Auth0/OIDC telah disetujui dan implementasi development ada pada ADR-004.
Belum ada tenant/provider dikonfigurasi, biaya disetujui atau uji IdP nyata.
