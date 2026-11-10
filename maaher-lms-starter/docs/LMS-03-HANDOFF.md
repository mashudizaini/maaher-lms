# LMS-03 — cohort dan enrollment siap review development

11 November 2026 WIB. Branch `feat/LMS-03-enrollment`, base **fe54142**,
bertumpu pada branch LMS-02 yang belum di-merge. Instruksi pemilik: lanjut setelah
re-review LMS-02 APPROVED_WITH_NOTES. Delapan temuan LOW lama kini dipetakan;
request._body yang masih OPEN diganti ASGI receive/replay. Laporan asli Claude
berada di Mac; cloud hanya mencatat [relay](../reviews/LMS-02-rereview-relay-20261111.md).
Verdict itu tidak diperluas menjadi approval auth parent atau source LMS-03.

## Perilaku yang tersedia

- /enrollments: admin tenant membuat/mengganti nama/archive/restore cohort,
  mendaftarkan siswa aktif, memindahkan cohort, revoke dan reactivate eksplisit.
  Course/cohort/student harus pada tenant dan parent yang sama. Duplikat 409,
  optimistic version mencegah update lama menimpa perubahan baru.
- Guru hanya membaca cohort/roster aktif pada kursus tugasnya. Tidak ada grant
  email lookup baru; teacher melihat ID siswa singkat. Admin memilih siswa lewat
  list anggota tenant existing, dengan pagination.
- /learn: siswa mempunyai katalog/outline/lesson READ-ONLY, tanpa progress atau
  runner. Materi hanya course published dengan enrollment dan cohort aktif.
  Siswa tidak membaca roster peer atau cohort siswa lain.
- Unpublish/edit draft menjeda read sampai publish berikutnya. Archive course/
  cohort dan role/status membership/user mencabut enrollment permanen. Restore
  atau role kembali student tidak mengaktifkan lagi; perlu tindakan admin.
  Cleanup membership tidak menghapus enrollment tenant lain.
- Course.version/state tidak diubah oleh perubahan roster. Budget mutation
  60/menit per tenant/user dibagi dengan course writes; 429/Retry-After BFF tetap.
  Header/cookie/query/Origin/body allowlist, no-store dan preview Markdown aman.

ADR kontrak dan grants: [ADR-007](adr/007-enrollment-access.md); acceptance dan
batas: [ticket](tickets/LMS-03.md). Asset tidak di-fetch server/gambar tidak
otomatis dimuat; tidak ada eksekusi kode learner. React/Next/Python lock tidak
berubah dari fe54142; tidak ada dependency baru.

## Perubahan dan migrasi

File inti: enrollment.py, learning.py, course_ingress.py; migration
0008_enrollment.py/enrollment.sql; BFF api/enrollment; UI /enrollments, /learn,
components; navigasi auth/courses/home; fixtures/API/migration/browser tests,
script checker head 0008 dan CI branch/browser job baru. courses.py memindahkan
CommonMark validation dari model ke sync endpoint agar bekerja di worker;
publicasi tetap memvalidasi legacy content. auth.py/oidc.py/session/MFA/Action
Auth0 tidak diubah oleh delta ini.

0007→**0008_enrollment** menambah dua FORCE RLS tables, FK komposit, tiga definer
terbatas dan trigger lifecycle. Data auth/course/content/assignment dipertahankan;
tidak ada auto-enroll. Helper student hanya membuka SELECT pada published course
dengan enrollment aktif; grants authoring write tetap staff-only. Total definer
14, owner non-superuser/no-login, fixed search_path dan tanpa PUBLIC EXECUTE.

Downgrade 8→7 menghapus **seluruh cohort/enrollment**, menjaga course/auth;
guard menolak tabel berisi tanpa `-x allow_enrollment_data_loss=yes`. Ack hanya
setelah backup/keputusan rollback operator, bukan langkah UAT. SQL guard 0008
bisa dihasilkan offline. Guard 0006 offline masih OPEN; online tetap fail-closed.
Fixture baru melakukan seeded 7→8→penolakan downgrade→ack pada DB disposable→7→8
serta memeriksa auth/course utuh dan enrollment tidak muncul kembali. Fixture
lama juga melakukan auth/base roundtrip pada DB tes kosong lain.

## Hasil nyata cloud

| Pemeriksaan | Hasil |
|---|---|
| `PYTHONPATH=apps/api python -m pytest -q -x --tb=short apps/api/tests` | **272 passed**, 0 skip, 2 deprecation warning, 185.31s |
| Subset enrollment awal sebelum probe tambahan | 13 passed, 0 skip, 36.56s; hasil final menggunakan full 272 |
| Tambahan dari parent 244 | 22 enrollment API/SQL/concurrency + 1 seeded migration + 5 ASGI/worker = **28** |
| `python -m pytest -q scripts/tests` | **12 passed**, 0 skip |
| `node --test infra/auth0/*.test.cjs` | **16 passed**, 0 skip |
| Browser enrollment `--oidc --dev-totp --enrollment` | **2 passed**, 14.2s |
| Browser courses `--oidc --dev-totp --courses` | **2 passed**, 17.0s |
| Browser auth / OIDC FIDO2 sintetis / dev-TOTP sintetis | **7 / 1 / 1 passed**, 20.1s / 3.2s / 3.0s |
| `npm run typecheck`, `npm run build` | PASS, Next production build |
| npm production audit / PyPI runtime snapshot | **0 vulnerabilities / 41 pins, 0 findings/errors** |
| compileall API/migrations; CI YAML parse; git whitespace | PASS |

Total browser **13**, tanpa skip. Node 24.22.1, Python 3.12.14/Linux, Chromium
nyata, PostgreSQL 16.15 dengan runtime non-owner/non-BYPASSRLS; auth/operator/
mail/maintenance terpisah. OIDC memakai provider uji bertanda tangan sintetis,
bukan tenant Auth0 user atau security key fisik.

Kasus penting: duplicate INSERT dan activation bersamaan; API activation menunggu
perubahan membership lalu ditolak; INSERT lebih dulu menahan membership lalu
role update mencabut setelah menunggu; versi lama/parent asing; peer cohort/
roster tidak terbaca; forged context; RLS SQL langsung student; grants immutable
columns/FK; audit; pagination tanpa duplikat; archive/restore/role cycles dan
revoke pada session yang sama. Validasi parser pada worker ditahan oleh Event;
health async tetap dijawab sebelum parser dilepas, membuktikan thread isolation.
Bukan klaim biaya parser telah menjadi linear atau benchmark end-to-end adversarial.

Browser enrollment memakai **dua context/session**: admin OIDC membuat cohort,
enroll siswa; siswa lokal sintetis login dan membaca materi; revoke membuat
list kosong dan request lesson 404; reactivate membuka lagi; archive/restore
cohort tetap revoked; logout membuat request 401. BFF menolak path/metode/query/
Origin/body ilegal. UI 429 editor kursus tetap diuji oleh regresi courses lama.

Full suite awal lulus 270 kasus. Dua probe tambahan memeriksa scoping sebelum
lock. Guard awal tambahan terlalu luas karena PostgreSQL menganggap superuser
member semua role; cleanup oleh owner pada fixture ditolak (81 pass/1 fail).
Guard diperbaiki agar owner tabel tetap memakai otoritas DB yang sudah dimiliki,
sementara runtime wajib admin tenant sebelum menyentuh parent/user. Full final
272 dan seluruh browser dijalankan ulang setelah koreksi; tanpa SKIP.

Satu percobaan orkestrasi browser dijalankan sebelum file env tes selesai dibuat;
gagal sebelum koneksi DB. Setelah prasyarat siap, dua tes final lulus pada DB
kosong yang sama. Tidak ada skip untuk menutupi kegagalan aplikasi.

DB **final**: maaher_test_lms03_release_20261111 (API),
maaher_test_lms03_enrollment_release_20261111, maaher_test_lms03_courses_release_20261111,
maaher_test_lms03_auth_release_20261111, maaher_test_lms03_fido_release_20261111,
maaher_test_lms03_totp_release_20261111. DB tahap final-sebelum-koreksi,
maaher_test_lms03_final_20261111, juga dipertahankan.
DB awal lain yang dipertahankan: maaher_test_lms03_target_20261111 (subset),
maaher_test_lms03_api_20261111 (full), maaher_test_lms03_enrollment_browser_20261111,
maaher_test_lms03_courses_browser_20261111, maaher_test_lms03_auth_browser_20261111,
maaher_test_lms03_fido_browser_20261111 dan maaher_test_lms03_totp_browser_20261111.
Tes migration membuat satu DB maaher_test_lms03_migration_<random> tersendiri dan
mempertahankannya. Semua ini DB cloud milik sesi. Container
maaher-cloud-review-20261109 port 127.0.0.1:32774 dihentikan setelah validasi,
tidak dihapus; jangan memakai port snapshot sebelumnya saat container restart.

## Gate dan langkah lokal

[Mac setup](LMS-03-MAC-SETUP.md): ambil branch tanpa overwrite perubahan lokal,
backup DB development sintetis yang benar, upgrade **0007→0008** memakai role
migrasi terpisah, rebuild API/web. .env, keyring, binding, domain/client/Action
Auth0 dan profil dev-TOTP yang sudah berhasil dipertahankan. Tidak perlu setup
IdP ulang. Jangan menjalankan pytest pada DB UAT yang berisi; fixture menuntut
DB tes kosong baru dan melakukan rollback destruktif ber-ack pada DB itu.

Owner melakukan login sendiri. UAT baru pada /enrollments dan /learn belum
terjadi di Mac; cloud tidak mengakses localhost Mac. Provision siswa sintetis
baru melalui alur undangan existing pada tenant tes; kredensial/token hanya
lokal, jangan di chat. Tidak membuat role admin atau binding berdasarkan email.

Minta review independen sesuai [review request](../reviews/LMS-03-review-request.md).
Auth parent full review **8941a79..4733526** tetap terbuka; LMS-02 approved with
notes tidak mengesahkannya. Ref main dapat di-fetch tanpa mengubah source untuk
review origin/main...HEAD. N1 biaya parsing, N2 offline0006, N3 extra-invisible/
NAT64 dan N4 audit cleanup historis tetap OPEN/mitigated, dicatat pada relay.
CI remote, build image aplikasi, Auth0 nyata/student-teacher, SMTP/inbox dan gate
produksi belum diverifikasi. Tidak ada merge/deploy atau perubahan DB/config Mac.
