# LMS-02 — manajemen kursus siap review development

## Tindak lanjut review LOW — status terbaru 10 November 2026

Bagian ini menggantikan status review pending/head 0006 serta perilaku assignment
pada snapshot historis di bawah. Pemilik menyampaikan review Claude: tujuh LOW,
tanpa BLOCKER/HIGH/MEDIUM. File asli/verdict formal tidak tersedia di cloud;
[relay author](../reviews/LMS-02-review-relay-20261110.md) menjaga provenance.
Respons per item tersedia di [author response](../reviews/LMS-02-author-response.md).

Ketujuh temuan sudah diperbaiki oleh author: assign/cabut menjaga publikasi;
role/status membership/user mencabut assignment tanpa pulih otomatis; guru
tidak membaca arsip/child; server memeriksa link aktif Markdown dan resource;
URL tersembunyi/trailing dot ditolak; rollback data kursus perlu ack; detail
field eksplisit dan budget mutation 60/menit per tenant/user dengan RLS/retensi.
Trigger mengunci membership/user untuk race assignment vs role/status; audit
cleanup hanya memakai actor admin yang benar-benar tervalidasi. Editor tetap
utuh setelah 429 dan BFF meneruskan Retry-After, tanpa memperluas cookie/header.

Head baru **0007_course_review**, parent 0006. Upgrade mempertahankan materi,
state/version, assignment aktif yang valid, akun/binding/session/secret. Assignment
yang saat upgrade tidak valid dibersihkan. Riwayat role yang sudah kembali
teacher sebelum upgrade tidak dapat disimpulkan dari schema lama; admin perlu
meninjau kasus historis yang diketahui. Tidak ada auto-publish draft lama atau
penulisan ulang Markdown. Link legacy diperiksa ulang saat save/publish.

Downgrade 7→6 menjaga materi tetapi melepas guard/budget baru dan tidak
mengembalikan assignment yang telah dicabut. Guard downgrade **0006** dibackport:
bila ada course, menolak downgrade ke 0005 kecuali `-x allow_course_data_loss=yes`.
Ack bukan langkah upgrade/UAT; hanya pengujian disposable atau keputusan
rollback operator setelah backup. Tidak ada bypass nama DB, tidak ada rollback
DB pengguna. Fixture menguji penolakan/rollback transaksi dan ack eksplisit.

### Validasi delta baru oleh author

| Pemeriksaan | Hasil |
|---|---|
| API lengkap Python 3.12.14/Linux + PostgreSQL 16.15 | **244 passed**, 0 skip, 2 deprecation warnings, 119.31s |
| Subset course + review regressions | **74 passed**, 0 skip, 90.80s; termasuk 46 kasus review baru |
| Migration seeded 0006→0007, 7→6→7, guard populated rollback, auth/base roundtrip | PASS pada fixture suite |
| Script tests / Auth0 Action unit tests | **12 / 16 passed**, 0 skip |
| Browser kursus final | **2 passed**, 14.9s; assignment published, link server, editor/Retry-After 429, persist/archive/logout/BFF |
| Browser auth baseline / OIDC FIDO2 sintetis / OIDC dev-TOTP sintetis | **7 / 1 / 1 passed**, 20.9s / 3.2s / 3.3s; total seluruh browser **11**, 0 skip |
| Next production build + typecheck | PASS setelah perbaikan label pemilih pengajar |
| npm production audit / PyPI runtime snapshot | **0 vulnerabilities / 41 pins, 0 findings/errors** |
| pip check, compileall | PASS |

Browser pertama menemukan nama aksesibilitas select pengajar berubah karena
label membungkus option; label kini htmlFor/id eksplisit dan run kursus final
lulus. Tidak ada failure yang disembunyikan dengan SKIP. Runtime SQL/RLS,
dua urutan race koneksi nyata, budget slot terakhir/concurrency/retensi,
field-set dan target CommonMark aktif/literal kode diuji pada test_course_review.
Jumlah definer schema final sebelas, owner non-superuser/ACL/search_path diuji.
CommonMark server menambah markdown-it-py 4.3.0 dan mdurl 0.1.2 pada lock Python.

DB uji baru: maaher_test_course_review_target_20261110 (subset),
maaher_test_course_review_full_20261110 (full API),
maaher_test_course_review_courses_browser_final_20261110 (browser final).
Browser auth/OIDC memakai DB terpisah maaher_test_course_review_auth_browser_20261110,
maaher_test_course_review_fido_browser_20261110 dan
maaher_test_course_review_totp_browser_20261110, seluruhnya dipertahankan.
DB probe/course browser awal juga dipertahankan. Role runtime non-owner tanpa
BYPASSRLS; auth/operator/mail/maintenance terpisah. Semuanya milik sesi cloud,
bukan DB UAT Mac. Container maaher-cloud-review-20261109, binding tes
127.0.0.1:32773; jangan memakai port historis di bawah bila dijalankan kembali.
Container tes dihentikan setelah validasi, tidak dihapus; seluruh DB tetap ada.

Source base delta **f4f9cf7**; branch tetap feat/LMS-02-course-management. Patch/
manifest baru review-fixes terpisah dari artifact LMS-02 awal, yang tetap utuh.
Laporan Claude LMS-01 historis tetap SHA256 yang dicatat di bawah.

### Langkah Mac dan review

Ikuti [panduan Mac yang diperbarui](LMS-02-MAC-SETUP.md): ambil source tanpa
menimpa perubahan lokal, backup **DB development sintetis yang benar**, upgrade
maju **0006→0007** dengan credential migrasi, install lock/rebuild API dan web.
Pertahankan .env/keyring/Auth0/binding/MFA yang sudah berhasil; user melakukan
login sendiri. UAT khusus assignment published, role cycle, arsip guru, link
Markdown dan alur utama. Hasil UAT f38c231 tidak dianggap menguji delta ini.

Minta Claude re-review menggunakan [review request](../reviews/LMS-02-review-request.md).
Auth parent tetap perlu review penuh terpisah; pemeriksaan terarah sebelumnya
bukan persetujuan auth. Signed synthetic IdP tidak menguji tenant Auth0 nyata,
inbox SMTP atau security key fisik. Mac UAT baru, re-review, CI remote dan build
image aplikasi belum terverifikasi oleh cloud. Enrollment LMS-03 belum dimulai.
Tidak ada perubahan Auth0/.env/DB Mac, merge atau deploy.

## Snapshot historis LMS-02 f38c231 dan laporan UAT awal

**Pembaruan UAT Mac:** pemilik kini melaporkan backup/upgrade 0006, validasi lokal
198 API + 12 scripts + 16 Action + 2 browser, preflight Auth0 13 PASS, serta
keberhasilan UAT manual alur utama. Lihat [catatan UAT](LMS-02-DEV-UAT-20261110.md)
dan [checklist](LMS-02-CHECKLIST.md). Pernyataan UAT Mac pending pada snapshot
di bawah telah digantikan laporan tersebut. Review Claude dan CI remote tetap
pending/unverified. Source runtime yang diuji tetap f38c231.

10 November 2026. Branch `feat/LMS-02-course-management`, parent `4733526`
(catatan UAT Auth0 yang dilaporkan pemilik). Branch auth/main tidak digabungkan.
Pemilik mengizinkan kelanjutan setelah login→organisasi→logout Mac berhasil.
Hasil itu tercatat di LMS-01-DEV-UAT-20261110.md sebagai laporan Mac, bukan
pengujian live cloud. Implementasi LMS-02 memakai spesifikasi Maaher asli;
perilaku Timedoor yang belum diamati tetap UNKNOWN.

## Perilaku yang tersedia

- Admin tenant: buat/edit kursus, assign/cabut pengajar aktif, arsip/pulihkan.
- Admin dan guru yang ditugaskan: modul/pelajaran berurutan, edit judul/materi,
  pratinjau Markdown, tautan HTTPS, publish/unpublish dan hapus child eksplisit.
- Edit mengembalikan kursus ke draft. Publikasi menolak struktur/pelajaran kosong.
  Dua writer dengan versi sama tidak saling menimpa: satu sukses, satu 409.
- Data tersimpan pada PostgreSQL, bertahan setelah reload. Session Auth0 yang
  sudah tersedia dipakai lewat BFF; Origin, membership/MFA, role dan RLS wajib.
- /courses, navigasi dari /auth dan beranda baru berbahasa Indonesia. Akun yang
  tidak berhak tidak memperoleh materi lewat API. Kursus terbit belum menjadi
  katalog publik/siswa; enrollment berikutnya menentukan akses belajar.

File inti: apps/api/app/courses.py; migration 0006_courses.py/courses.sql;
apps/web/app/courses/page.tsx dan api/courses/[[...path]]/route.ts; auth/home/
layout/globals.css; react-markdown 10.1.0 + package-lock; tests, browser wrapper,
checker kompatibilitas head 0006, workflow CI dan dokumentasi.
Detail contract ada pada ADR-006 dan ticket LMS-02.

## Validasi cloud

| Pemeriksaan | Hasil |
|---|---|
| `PYTHONPATH=apps/api python -m pytest -q -x --tb=short apps/api/tests` | **198 passed**, 0 skip, 92.64s pada source final |
| `python -m pytest -q scripts/tests` | **12 passed**, 0 skip |
| `node --test infra/auth0/*.test.cjs` | **16 passed**, 0 skip |
| Browser LMS-02 `test-lms01-browser.py --oidc --dev-totp --courses` | **2 passed**, real Chromium + signed synthetic IdP |
| Browser auth baseline | **7 passed** |
| Browser OIDC FIDO2 sintetis / dev-TOTP sintetis | **1 + 1 passed** |
| `npm run typecheck`, `npm run build` | **PASS** |
| `npm audit --omit=dev` | **0 vulnerabilities** |
| compileall API/migrations, git diff whitespace, reviewer artifact baseline | **PASS** |

Total browser yang dijalankan: **11**, tanpa skip. API menambah 28 kasus LMS-02:
13 URL berbahaya dan 15 flow/permission/database/concurrency/resource cases,
di samping 170 kasus auth/unit sebelumnya. Termasuk actor/session GUC palsu,
tenant asing, role siswa/guru tanpa assignment, assignment/membership dicabut,
FK tenant, immutable tenant/owner grants, runtime child write pada published
course, rollback error child, pagination, caps, urutan dan audit. Definer baru
memiliki role/ACL/search_path minimum dan jumlah tepat sepuluh fungsi definer
di schema final; function course_can_manage tetap INVOKER.

Browser menjalankan login OIDC→pilih organisasi→buat course/module/lesson→
save→reload→publish→edit draft→arsip/restore→logout. Konten script/javascript
tidak dieksekusi, elemen script/img berbahaya tidak dibuat, gambar eksternal
tidak di-request, dan resource HTTPS tersimpan. BFF diuji Origin, route asing,
query ganda/invalid serta payload berlebih. HTTPS IdP pada browser/API memakai
transport sintetis dengan JWT RSA; ini bukan UAT tenant Auth0 nyata untuk LMS-02.

Browser awal menemukan label textarea setelah reload tidak stabil karena
label membungkus content textarea. Label Markdown/deskripsi diubah menjadi
htmlFor/id eksplisit; run final seluruh browser lulus. Review batas resource
juga menambah cap 50 pengajar/course dan menolak bentuk host localhost/IPv4
pendek. Full API dijalankan ulang setelah perbaikan terakhir. Tidak ada skip
untuk menutupi failure. Dua deprecation httpx/Authlib tetap ada.

Node dependency baru diaudit. Python lockfile tidak berubah; audit Python
tidak diulang pada delta ini. Remote GitHub CI disiapkan untuk branch dan
browser baru tetapi hasil remote **belum diverifikasi**. Build/image Docker
aplikasi dan UAT Mac LMS-02 belum dilakukan cloud; browser memakai Next build
production lokal, API uvicorn dan PostgreSQL 16.15 pada container milik sesi.

DB final API `maaher_test_courses_release_20261110` (namanya tetap DB test),
browser `maaher_test_courses_browser_final_20261110`, baseline auth
`maaher_test_courses_auth_browser_20261110`, OIDC
`maaher_test_courses_fido_browser_20261110` dan
`maaher_test_courses_dev_browser_20261110`. DB percobaan courses/full/final dan
browser awal juga dipertahankan. Container maaher-cloud-review-20261109, port
tes 127.0.0.1:32772, dihentikan setelah validasi; tidak dihapus. Tidak ada
akses atau perubahan database/container/.env Mac oleh sesi cloud.

## Migrasi, batas dan langkah lokal

Head **0006_courses**, upgrade dari 0005 menambah empat tabel/fungsi/policy dan
tidak mengubah akun, keyring, session atau binding Auth0. Fixture memeriksa
head→0005→head, serta seluruh rollback auth lama/base; data identity fixture
dipertahankan. Downgrade ke 0005 menghapus **semua data kursus**; backup dan
review dahulu. Tidak ada downgrade/migrasi data pengguna dijalankan cloud.

Asset hanya link HTTPS; belum upload/video hosting. Siswa/enrollment/cohort,
submission/grading dan eksekusi kode tidak diimplementasikan pada tiket ini.
Caps development terdokumentasi: 500 course/tenant, 30 module/course,
50 lesson/module, 50 teacher/course, 10 link/lesson dan body 256 KiB. Hapus
module/lesson permanen setelah konfirmasi; arsip course menjaga data child.
Teacher Auth0 enrollment/binding tidak diperluas; gunakan identity yang sudah
diotorisasi dan jangan memakai marker operator sebagai pengganti role tenant.

Pemilik/Codex Mac mengikuti [LMS-02-MAC-SETUP](LMS-02-MAC-SETUP.md): source baru,
backup DB sintetis yang benar, upgrade 0006 dengan role migrasi, pertahankan
seluruh konfigurasi Auth0 yang sudah berhasil, install lockfile dan rebuild
API/web development. Owner login sendiri lalu UAT /courses. Matikan diagnostic
lokal setelah selesai. Tidak ada merge/deploy atau promosi dev trust produksi.

## Review independen

Laporan Claude awal tetap utuh (SHA256
004a19183409b152d0947ab6f5b99af2000d9dd3324c9a2c77ea66a4106032ce).
Patch/manifest historis auth tidak ditulis ulang. Snapshot LMS-02 dibuat untuk
delta ini, tetapi diff Git tetap sumber review utama. Auth parent sendiri masih
memerlukan review atas update Auth0/dev-TOTP/diagnostics; UAT Mac bukan signoff
produksi. FIDO2/root trust/recovery, SMTP/inbox, TLS/ingress, backup/restore dan
persetujuan manusia tetap gate release terpisah.

```text
Review READ-ONLY branch feat/LMS-02-course-management di mashudizaini/maaher-lms.
Root aplikasi maaher-lms-starter/. Baca CLAUDE.md/AGENTS.md, skill security review,
ticket LMS-02, ADR-006 dan handoff ini. Periksa delta 4733526..HEAD untuk kursus;
periksa main...HEAD untuk seluruh auth yang belum direview/merge.
Uji pada DB kosong baru maaher_test_* dengan role terpisah milik review sendiri.
Fokus RLS/tenant/FK, session capability/MFA, definer ACL, teacher assignment/
revoke, optimistic version dan publication atomicity, XSS/HTTPS/asset handling,
BFF Origin/body/query ingress, dan migration rollback data loss.
Bedakan signed synthetic IdP dari UAT Auth0 nyata. Jangan ubah source/Auth0/
data pemilik. Simpan temuan di reviews/LMS-02-claude.md, pertahankan laporan lama.
Jangan merge/deploy. Catat setiap tes yang tidak dijalankan.
```
