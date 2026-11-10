# Mengambil source Auth0 yang benar ke Mac

Hasil Codex lokal yang masih melihat head 0003 menunjukkan folder lokal belum
memuat implementasi Auth0 yang dibuat di cloud. Verifikasi saja tidak memindahkan
source. Branch `feat/LMS-01-auth0-development` menyediakan source yang dapat
diambil melalui Git; tidak perlu mengunduh artefak chat.

Pemilik mengoreksi lokasi proyek menjadi:
`/Users/mashudi/Downloads/AiMZ-Corp Project/maaher-lms-starter`.
Lokasi `govriskid` sebelumnya salah dan tidak digunakan. Domain/Client ID yang
diberikan dikonfirmasi khusus Maaher LMS. `.env` lama tetap merupakan file lokal
di Mac; sesi cloud tidak menerima atau membaca Client Secret-nya.

## Clone baru sambil mempertahankan folder lama

Di Terminal Mac, gunakan folder tujuan baru yang belum ada:

```sh
cd "/Users/mashudi/Downloads/AiMZ-Corp Project"
git clone --branch feat/LMS-01-auth0-development --single-branch https://github.com/mashudizaini/maaher-lms.git maaher-lms-auth0
cd maaher-lms-auth0/maaher-lms-starter
```

Root repository GitHub mempunyai subfolder `maaher-lms-starter`, sehingga
folder kerja aplikasi adalah folder pada command terakhir. Jangan clone ke
folder lama yang berisi perubahan pengguna atau menimpanya. Jika folder tujuan
sudah ada, periksa status Git-nya dahulu dan gunakan nama tujuan baru yang unik.

Periksa file ini ada sebelum menjalankan setup:

```sh
test -f apps/api/migrations/versions/0004_auth0_oidc.py
test -f apps/api/app/oidc.py
test -f scripts/verify-auth0-local.py
```

## Konfigurasi dan validasi

Minta Codex lokal yang berjalan dari folder **baru** membaca AGENTS.md,
AUTH0-SETUP.md dan LMS-01-AUTH0-HANDOFF.md. Periksa keberadaan `.env` pada path
proyek lama yang sudah dikoreksi, tanpa mencetak isinya. Bila belum ditemukan,
periksa nama file `.env*` di folder proyek itu saja, bukan seluruh laptop.

Gunakan parser dotenv untuk mengambil field yang memang milik Maaher LMS,
terutama AUTH0_DOMAIN, AUTH0_CLIENT_ID dan AUTH0_CLIENT_SECRET, tanpa menampilkan
nilainya atau mengeksekusi file sebagai shell. Pertahankan file lama dan semua
nilai konfigurasi lain. `.env` pada clone baru harus lokal/di-ignore, bukan
di-commit. Jangan mengisi secret dummy agar checklist terlihat lengkap.

Audit dahulu tujuan database pada konfigurasi lama. Migrasi/provisioning tahap
Auth0 hanya dijalankan pada database development kosong baru berprefix
`maaher_test_` dengan role terpisah, bukan database pengguna atau database hasil
tes lama. Pertahankan seluruh DB/container yang sudah ada. Port Docker dan
hostname Compose perlu diperiksa dari konteks host/container yang benar.

Setelah dependency dan service lokal siap, jalankan dari root starter baru:

```sh
.venv/bin/python scripts/verify-auth0-local.py --project-root . --start-flow
```

Checker tidak mencetak credential/token/cookie dan tidak melakukan login nyata.
PASS/FAIL/SKIP dibedakan. Setelah prasyarat lulus, pemilik menyelesaikan login
security key pada browser Mac sendiri; tidak memberikan password/PIN ke agent.
Enrollment independen, Action, binding subject, callback dan claim policy tetap
harus dipenuhi sesuai panduan. Tidak auto-link email atau membuka bypass MFA.

## Prompt untuk Codex lokal dari folder baru

```text
Source Auth0 sudah diambil dari branch feat/LMS-01-auth0-development.
Baca docs/MAC-SOURCE-SYNC.md, AUTH0-SETUP.md, dan handoff OIDC.
Folder lama yang benar adalah:
/Users/mashudi/Downloads/AiMZ-Corp Project/maaher-lms-starter
Periksa file .env di sana melalui nama/presence saja. Reuse konfigurasi LMS
yang relevan memakai parser dotenv tanpa mencetak secret, dan pertahankan
file/konfigurasi lama. Siapkan DB development baru yang terpisah; jangan
migrasi DB pengguna atau menimpa source lama. Jalankan setup/service serta
verify-auth0-local.py. Diagnosis FAIL/SKIP dan lanjutkan pekerjaan independen.
Untuk login/key/binding yang memerlukan bukti identitas, minta saya
menyelesaikan langkah pemilik, jangan auto-link email atau melemahkan MFA.
Pisahkan hasil preflight dari login Auth0 nyata. Jangan merge atau deploy.
```

Review independen Claude tetap diperlukan. Branch ini membawa implementasi
development, bukan persetujuan penggunaan produksi atau penutupan seluruh H1.
