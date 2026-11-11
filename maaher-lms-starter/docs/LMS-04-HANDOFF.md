# LMS-04 — learning completion dan perbaikan F1/F2 siap review

11 November 2026 WIB. Branch **feat/LMS-04-student-learning**, base **4870287**
(runtime parent 110c9be). Pemilik meminta LMS-04 setelah menyampaikan dua MEDIUM
pada review LMS-03. Verdict formal tidak disampaikan. Lihat relay author
reviews/LMS-03-review-relay-20261111.md; laporan asli tetap di Mac. Tidak ada
klaim LMS-03/auth parent sudah disetujui. F1/F2 implemented/tested author,
menunggu re-review independen.

## Perilaku akhir

/learn kini menyediakan progres completed/total, lanjutkan yang belum selesai,
previous/next lesson, tandai selesai/belum selesai, selesai & lanjutkan dan
persistence setelah reload/API restart. Materi/resources yang berubah menaikkan
lesson revision; completion lama menjadi needs_review, tidak dihitung sampai
siswa membaca dan menandai ulang. Title/reorder saja tidak membatalkan. Completion
adalah self-report, bukan nilai/sertifikat. Hanya siswa pemilik enrollment aktif
pada course terbit; teacher/admin/peer/tenant asing tidak diberi progress access.
Revoke/draft/archive/role/status membatasi akses sesuai LMS-03. Tenant disable
masih pause, bukan revoke permanen. Semua perubahan progress terikat FK tenant/
course/enrollment/student/lesson dan revision; duplikat tidak membuat audit baru.

F1: policy SELECT memakai scope tervalidasi pada InitPlan, bukan memanggil
resolver pada setiap lesson. FOR ALL write policy dipisahkan dari SELECT.
Empat helper memakai dedicated role NOLOGIN/NOBYPASSRLS read-only kolom minimum;
14 definer lama tidak diperluas untuk membaca content/progress. F2: trusted parser
child dengan satu slot per API process, CPU/wall/memory budget, cache digest valid
128 dan busy429. Tidak menjalankan kode learner, tidak memberi child secret env.

File inti: migrations read_scope/0009, learning_progress/0010; learning API/limits,
markdown_parse/service/worker, course_content/courses/ingress; UI /learn, BFF,
CSS, tests/benchmark, scripts checker/browser, CI, ADR-008 dan ticket LMS-04.
Tidak ada dependency baru, auth.py/oidc.py/Action/MFA/session tidak diubah.

## Validasi final cloud

| Pemeriksaan | Hasil |
|---|---|
| `PYTHONPATH=apps/api python -m pytest -s -q -x --tb=short apps/api/tests` | **291 passed**, 0 skip, 2 existing deprecation warnings, 245.23s |
| Parent 272 + tambahan | 9 completion API/SQL + 1 migration + 3 scope/perf + 6 parser/CPU/cache = **19 baru** |
| Subset course/enrollment setelah 0009 | 50 passed, 74.11s |
| Subset completion awal | 8 passed, 28.17s sebelum case SQL tambahan; final full 291 di atas |
| Scope + CPU subset awal | 7 passed, 61.09s sebelum tambahan timeout; final benchmark full di atas |
| Script / Action | **12 / 16 passed**, 0 skip |
| Browser learning / enrollment / courses | **2 / 2 / 2 passed**, 11.1s / 10.0s / 11.0s |
| Browser auth / OIDC FIDO2 / dev-TOTP | **7 / 1 / 1 passed**, 20.0s / 3.0s / 3.1s |
| Browser total | **15 passed**, 0 skip |
| Next build/typecheck / compileall / pip check | PASS |
| npm production audit / PyPI runtime advisory | 0 vulnerabilities / 41 pins, 0 findings/errors |

Python 3.12.14/Linux, Node24.22.1, Next production build, real Chromium,
PostgreSQL16.15; runtime non-owner/non-BYPASSRLS, auth/operator/mail/maintenance
terpisah. Signed synthetic provider, bukan tenant Auth0 nyata atau security key.

F1 final: student SQL 1500 lesson **26078.94→18.08ms**, admin **10618.93→14.74ms**,
student100 **2333.96→20.15ms**, catalog tenant451 **4467.99→16.17ms**. Outline baru
plus progress melalui ASGI TestClient **133.03ms**. Bukan pengukuran TCP/browser/
TLS produksi. Baseline merekonstruksi policy 0008+FOR ALL di DB test yang sama,
bukan binary/API lama. Plan memakai InitPlan, tanpa per-row helper lama. Koneksi
prepared statement yang sama segera kehilangan scope setelah revoke membership.

F2 menggunakan TCP HTTP uvicorn sungguhan dengan 30KB adversarial, bukan Event.
Health p95 **1.71ms baseline, 2.93ms/2 saves, 11.31ms/8, 2.46ms/sequential**.
Budget asli satu akun **52/60 attempts** untuk setup dan 48 save probes;
422 complexity/429 busy yang disengaja, tanpa cache hasil invalid. Timeout,
child crash/restart, bad Unicode dan policy URL tetap fail-closed. Ini bukti
lokal; parser tetap kuadratik dan multi-worker perlu sizing terpisah. JSON dan
respons per temuan ada pada reviews/LMS-04-performance.json dan author-response.md.

Browser siswa/admin dua sesi menguji completion→next→all done→reload→uncomplete,
edit/publish lesson baru membuat completion stale, confirm lagi, revoke menolak
write dan membersihkan layar. BFF completion hanya menerima route/metode/query/
Origin yang diizinkan. Regresi editor utuh setelah 429 masih dijalankan pada
course browser. Semua old auth/tenant/race/migration tests tetap disertakan.

Masa implementasi awal 0009 sempat menolak INSERT RETURNING course admin karena
scope ID menggunakan snapshot sebelum row baru ada. Clause admin tervalidasi
pada SELECT policy memperbaikinya; subset50 dan full291 kemudian lulus. Run awal290 lulus; satu uji cache-scoping baru
menambah total menjadi291, dengan key validator dipisahkan per tenant/user.
Pengukuran awal bukan source approval dan tidak dipakai sebagai pengganti full.

## Migrasi dan rollback

Head **0010_learning_progress**. Upgrade maju 0008→0009→0010 menjaga data auth/
course/enrollment dan mengisi lesson.revision=1, progress kosong. Dedicated reader
role perlu provision/ownership oleh DBA migration credential, tanpa membership
ke role API/auth dan tanpa superuser/BYPASS/CREATE. Aplikasi tidak memakai
credential migrasi. Counter learning120/min tenant/student di-retain satu hari.

Downgrade 0010→0009 menghapus progress/counter/revision; data progress berisi
menuntut `-x allow_progress_data_loss=yes` setelah ACCESS EXCLUSIVE guard lock.
Downgrade0009→0008 memulihkan policy/grants lama tanpa menghapus course/enrollment.
Seeded test menjaga identity/material/enrollment; default rollback gagal menjaga
head/progress; ack hanya di DB disposable lalu re-upgrade tidak menghidupkan data
progress yang sudah dihapus. Offline SQL0010 memuat lock/guard. N2 offline0006
belum diperbaiki. Restore checkpoint tetap keputusan operator setelah backup.

DB baru final maaher_test_lms04_release_20261111; full awal
maaher_test_lms04_full_20261111 juga dipertahankan; scope_v2, learning, perf dan scope
awal yang gagal juga dipertahankan. Browser DB terpisah:
maaher_test_lms04_learning_release_20261111, enrollment_release, courses_release,
auth_release, fido_release, totp_release (semua prefix maaher_test_lms04_ dan
suffix _20261111). Enam DB *_browser_20261111 pada run awal juga dipertahankan. Seeded migration membuat maaher_test_lms04_migration_<random>
dan legacy enrollment migration juga DB acak baru, semuanya dipertahankan.
Container cloud maaher-cloud-review-20261109, port tes127.0.0.1:32775, dihentikan
setelah validasi tanpa menghapus DB. Tidak menyentuh container/DB/config Mac.

## Langkah berikut

Ikuti LMS-04-MAC-SETUP.md: source branch baru, backup DB sintetis existing,
upgrade0008→0010 dengan migration credential, rebuild API/web, pertahankan .env/
keyring/binding/dev-TOTP/Action. Owner login sendiri, uji siswa sintetis terpisah
completion/reload/next/material revision/revoke. Jangan menjalankan pytest pada
DB UAT yang berisi atau melakukan downgrade untuk setup. Suite/benchmark hanya
pada DB kosong baru yang memang disposable; test F1 mengubah policy sementara.

Re-review F1/F2 bersama delta learning melalui reviews/LMS-04-review-request.md.
Mac UAT baru, real Auth0 staff/student, CI remote, image Docker dan full auth
review 8941a79..4733526 belum diverifikasi di sini. N2/N3/N4, LOW definer lama,
ASGI notes yang tidak dirinci dan tenant pause tidak dinyatakan CLOSED.
Tidak ada merge/deploy atau learner runner. Laporan Claude LMS-01 historis utuh.
