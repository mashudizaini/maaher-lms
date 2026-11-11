# Respons author F1/F2 pada kelanjutan LMS-04

11 November 2026 WIB, base 4870287 (runtime parent 110c9be). Pemilik meminta
LMS-04; prasyarat F1/F2 ditangani dalam branch feat/LMS-04-student-learning.
Status: **implemented/tested by author, independent re-review pending**.

## F1 — set-based statement-scoped RLS

Policy module/lesson FOR ALL ikut menjadi policy SELECT dan mengevaluasi
course_can_manage/course_student_access/runtime_identity untuk setiap baris.
0009 memisahkan INSERT/UPDATE/DELETE dari SELECT. Read policy memakai helper
uncorrelated scalar subquery/InitPlan, menghasilkan scope dari session capability,
tenant, membership aktif dan role; batasnya per SQL statement, bukan cache antar
request. Beberapa InitPlan dapat memanggil helper berbeda dalam satu statement,
tetapi evaluasi tidak lagi sebanding jumlah lesson. Prepared statement koneksi
sama juga diuji setelah membership dicabut: langsung tidak ada course terlihat.

Empat helper baru dimiliki **maaher_access_reader NOLOGIN/NOBYPASSRLS/NOINHERIT**,
bukan menambah SELECT penuh ke maaher_definer. Role itu mendapat SELECT kolom
minimum pada enam tabel dan policy SELECT khusus; tidak password/session/faktor,
content, progress, atau write. Tidak boleh diasumsikan runtime/auth. Fungsi tanpa
parameter actor/tenant, fixed search_path, PUBLIC EXECUTE dicabut. Owner/grants/
negative tenant/peer/forged-context diuji bersama seluruh suite parent. Empat
helper menambah jumlah definer menjadi 18; 14 lama masih maaher_definer BYPASSRLS,
sehingga LOW auth-role tidak disebut ditutup penuh.

Pengukuran final pada data sama, di DB sintetis baru, ms:

| Kasus SQL | Policy 0008 direkonstruksi | Policy 0009 |
|---|---:|---:|
| Student outline 100 | 2333,96 | 20,15 |
| Student outline 1500 | 26078,94 | 18,08 |
| Admin outline 1500 | 10618,93 | 14,74 |
| Student catalog pada tenant 451 published | 4467,99 | 16,17 |

Endpoint outline baru termasuk progress (ASGI TestClient) **133,03ms** untuk
1500 lesson. Ini bukan latency TCP/browser/TLS produksi. Baseline memulihkan
read policy 0008 + FOR ALL write predicate hanya pada DB test sendiri, bukan
menjalankan binary lama atau mengubah DB pemilik. Catalog menguji 451 course
dengan dua enrollment sah; scope tidak membuka 449 course lain. Plan memakai
InitPlan dan tidak lagi mencantumkan per-row helper lama. API learning memakai
statement_timeout 2s dan admission 120 requests/minute per active tenant/student;
counter terbatas satu row/membership, commit sebelum parse/lookup, retensi sehari.

## F2 — trusted parser process dengan backpressure

CommonMark policy dan URL rules tetap, tetapi tokenisasi dipindahkan ke child
Python process. Satu pekerjaan aktif per API process, tanpa antrean tak terbatas;
request lain mendapat **429 Retry-After: 1**, editor tidak dihapus. Cache hanya
128 digest valid, key di-scope tenant/user dari actor server, bukan isi dokumen
atau cache bersama antar-akun. Child tidak mewarisi DB/Auth0/keyring env.
Ini library parser tepercaya atas teks, **bukan mengeksekusi kode siswa**.

Child memakai CPU profiling timer 120ms per dokumen; parent membatasi wall 1,5s
dengan pipe nonblocking dan membunuh child saat hang/crash, gagal tertutup 503.
Input kompleks ditolak 422 dengan petunjuk menyederhanakan Markdown. Child
memory limit 256MiB bila RLIMIT_AS didukung; Mac perlu verifikasi lokal karena
limit address-space tidak seragam. CPU/wall dan busy tetap diterapkan. Parser
algoritmenya tetap dapat kuadratik; batas kerja/isolasinyalah yang berubah.

Probe HTTP TCP uvicorn sungguhan, 30KB adversarial, tanpa monkeypatch budget
atau Event. Semua 48 save probes dan setup menghasilkan **52 attempts** dari
budget asli 60/min pada satu akun. Hasil health p95:

| Beban | p95 health | Sampel health |
|---|---:|---:|
| Baseline | 1,71ms | 20 |
| 2 concurrent saves | 2,93ms | 607 |
| 8 concurrent saves | 11,31ms | 399 |
| 1 account sequential saves | 2,46ms | 1430 |

Save menghasilkan 422 complexity atau 429 busy sesuai batas, bukan keberhasilan
palsu. Uji child crash/restart, timeout, malformed Unicode, policy URL dan CPU
budget juga lulus. Satu child per API worker bukan kuota CPU cluster; deployment
multi-worker tetap memerlukan sizing/cgroup dan pengukuran staging.

JSON pengukuran: LMS-04-performance.json. Full API **291 passed**, 0 skip,
2 existing deprecation warnings. Browser dan hasil tambahan di handoff.
Hasil cloud bukan klaim production SLO atau bukti Auth0 nyata. N2/N3/N4 dan
catatan tenant pause tetap terbuka. Review auth parent tetap terpisah.
