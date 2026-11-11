# LMS-06 — diagnosis fairness pada suite Mac

11 November 2026, Asia/Jakarta. Branch feat/LMS-06-teacher-grading, baseline
6d834748f68e32df443b3bb413b8fedc147bfe09. Pemilik melaporkan suite380 kasus:
378 PASS,1 capability SKIP,1 FAIL fairness (503 bersama422), rerun terisolasi PASS.
[Relay](../reviews/LMS-06-mac-validation-relay-20261111.md) mempertahankan batas bukti.
Penyebab503 **belum dipastikan**; ini bukan patch perbaikan runtime.

## Perubahan diagnostik

Hanya `apps/api/tests/test_parser_fairness.py` dan dokumentasi/evidence berubah.
Episode metrik kini dimulai sebelum assertion, dicetak pada finally sehingga
pytest menyimpannya saat FAIL. Status penulis/student/penekan, latency, penekan
aktif, budget, p95 health dan ringkasan permintaan tetap tercatat. Maks128 record
per episode; identitas/tenant/course/URL/body/input/header/cookie/token tidak dicetak.
Kategori error berasal dari pesan yang persis di-allowlist; pesan asing dicatat
sebagai `unclassified`. Retry-After hanya bilangan ASCII pendek. Transport error
hanya mencatat nama kelas, tanpa pesan/URL mentah.

Assertions tetap: seluruh simpanan normal/student200, penekan422, beban penekan
aktif, latensi penulis<10s dan budget<=60.503 tetap FAIL. CPU1000ms,wall3s,queue8s,
jumlah worker/budget/proof/assurance/RLS/grade schema tidak berubah. Tidak ada
skip/xfail/retry-otomatis atau penerimaan503 agar angka menjadi hijau. Satu tes
redaksi ditambahkan, sehingga koleksi final menjadi381 (sebelumnya380).

## Hasil author cloud

Pada DB kosong baru `maaher_test_lms06_fairnessdiagnostics_20261111`, file fairness
**6 PASS**,0 SKIP,2 warning deprecation existing,78,50s. Koleksi seluruh API381;
suite penuh tidak diulang karena runtime aplikasi tidak berubah. Tes redaksi
sendiri juga1 PASS (kasus yang sama diulang, bukan tambahan kasus unik).

HTTP nyata2/4/8 akun tenant sama/berbeda:36 simpanan penulis normal dan36 draf
student seluruhnya200; seluruh penekan422. Maks penulis3767,46ms, student220,37ms,
health p958,59ms. Ini keberhasilan terisolasi Linux cloud, bukan reproduksi atau
penutupan kegagalan suite Mac.

Verifikasi failure-capture memakai DB kosong lain
`maaher_test_lms06_fairnessfaultcapture_20261111`. Plugin sementara pada klien tes
mengganti satu respons422 yang sudah diterima menjadi503, tanpa mengubah server
atau resource caps. Assertion tetap FAIL seperti yang diharapkan, exit1, dan
episode parsial aman tercatat dengan completed:false. Ini **substitusi terkontrol
pada klien tes**, bukan503 asli dari API atau reproduksi root cause Mac. Plugin
berada di/tmp, tidak menjadi bagian runtime/repo.

[Verification tambahan](../reviews/LMS-06-fairness-diagnostics-verification.json)
menyimpan command/metrik/hash log dan batas bukti. Tidak ada build/browser/audit
ulang karena source runtime/dependency tidak berubah. DB uji dipertahankan,
hanya kontainer cloud milik author dihentikan setelah selesai.

## Pemeriksaan Mac

1. Baca laporan asli dan raw traceback lokal untuk nama node/parameter/assertion
   yang gagal; jangan mengasumsikan same/different tenant atau assert tertentu.
   Pertahankan file asli dan hasil suite FAIL. Catat HEAD, schema, platform/
   arsitektur/Python, host vs container, kapasitas CPU/RAM yang tersedia dan apakah
   ada beban lain. Jangan mencetak environment atau process command line rahasia.
2. Ambil source diagnostik tanpa menimpa perubahan/laporan lokal. Ini tidak
   memerlukan migrasi, restart API UAT, perubahan Auth0 atau keyring. Source
   aplikasi tetap6d83474 dan schema0013; cek aktual secara read-only.
3. Jalankan parser preflight/calibration pada hardware/profil yang sama untuk
   mencatat memory capability dan CPU margin. Native Mac WARN bukan cap aktif.
   Kalibrasi tidak menyesuaikan budget. Jangan menambah limit atau melemahkan MFA.
4. Buat **DB uji kosong baru** dengan prefixmaaher_test_, role URL terpisah ke DB
   yang sama, melalui workflow lokal aman. Jangan gunakan DB UAT atau DB lama.
   Jalankan file fairness dengan output tersimpan lokal:

   ```bash
   python -m pytest -q -s apps/api/tests/test_parser_fairness.py
   ```

   Ada enam kasus (tiga queue, dua HTTP, satu redaksi). Endpoint dan fixture
   memakai provider/session sintetis; ini bukan login Auth0 nyata.
5. Suite penuh harus dijalankan pada **DB kosong baru lainnya**, bukan DB dari
   langkah4 karena fixture menolak schema yang sudah terisi. Pertahankan seluruh
   modul rollback. Koleksi381; native Mac diperkirakan hanya satu capability SKIP,
   tetapi laporkan hasil nyata tanpa deselect:

   ```bash
   python -m pytest --collect-only -q apps/api/tests
   python -m pytest -q -s apps/api/tests
   ```

   Tes HTTP memakai TCP/session/RLS/CPU nyata. Jangan menambahkan beban buatan
   yang tidak dicatat atau menghentikan layanan pemilik untuk mengejar PASS.
   Jika hanya ada waktu untuk run terisolasi, tandai full-suite NOT RUN dan
   pertahankan kegagalan penuh sebelumnya sebagai OPEN.
6. Simpan laporan tambahan `reviews/LMS-06-fairness-mac-diagnostic-20261111.md`:
   command, HEAD/schema/node IDs/counts, kondisi hardware, hasil preflight,
   FAIL/assertion asli, hasil rerun, metrik terstruktur seluruh episode yang ada.
   Raw log lokal boleh disimpan aman; periksa/redaksi sebelum diunggah karena
   traceback dari dependency/fixture lain tidak termasuk allowlist diagnostik.
   Jangan menimpa laporan lama atau menyatakan sebab selesai dari satu rerun PASS.

## Membaca kategori503

| Kategori | Yang diketahui / langkah lanjut |
|---|---|
| queue_expired /queue_capacity /caller_timeout |Jalur antrean/admission. Periksa latency dan jumlah penekan; jangan naikkan queue/timeout tanpa evaluasi dampak |
| worker_unavailable |Worker/IPC tidak mengembalikan hasil sah; bisa wall deadline, crash atau protocol failure. Kategori ini belum membedakan penyebab tersebut |
| memory_capability_unavailable |Profil menolak cap memori yang tidak aktif; verifikasi host/profil, jangan menonaktifkan gate produksi |
| storage_unavailable |Ingress DB gagal, bukan otomatis masalah fairness parser; periksa konektivitas/pool/DB pada run uji |
| stopping /transport_error /unclassified |Kumpulkan bukti proses/runtime terbatas yang relevan; jangan anggap normal atau meluluskan |

Jika penulis/student mendapat503 pada2/4/8 akun, selidiki regresi ketersediaan F10.
Jika hanya penekan mendapat503 sementara semua penulis/student200, tetap pisahkan
penolakan konten422 dari kegagalan resource503: mungkin fail-closed tetapi bukan
bukti bahwa acceptance tes saat ini lulus. Perlu menilai resource/hardware dan
memverifikasi tidak ada penulisan/konten tidak tervalidasi, sebelum reviewer
memutuskan perubahan kontrak yang eksplisit. Tidak ada perubahan kontrak di sini.

## Prompt Codex CLI

```text
Lanjutkan diagnosis LMS-06 pada branch feat/LMS-06-teacher-grading.
Baca docs/LMS-06-FAIRNESS-DIAGNOSTIC.md dan laporan Mac asli. Pertahankan FAIL
suite378 PASS/1 SKIP/1 FAIL; rerun terisolasi PASS tidak menutupnya. Ambil source
diagnostik tanpa menimpa perubahan/laporan/.env/keyring/binding atau DB lama.
Catat node ID dan assertion gagal, kategori503/phase/latency/health/normal/student,
profil hardware dan parser calibration. Semua tes hanya pada DB kosong BARU;
file fairness dan full suite masing-masing DB baru, semua modul rollback ikut.
Koleksi kini381 karena satu tes redaksi. Jangan melonggarkan assertion menjadi
422/503, menaikkan resource cap, skip/xfail/deselect atau retry sampai hijau.
Tidak perlu migrasi/restart API UAT atau perubahan Auth0. Simpan laporan tambahan
reviews/LMS-06-fairness-mac-diagnostic-20261111.md dengan hasil actual dan
NOT TESTED. Jangan cetak secret, reset/downgrade DB lama, hapus container,
merge/deploy. Jika penyebab belum terbukti, tetap OPEN dan berikan diagnosis
berbasis bukti untuk AUTHOR; bukan klaim perbaikan selesai.
```

Independent review LMS-06 dapat memeriksa source dan kegagalan ini sebagai isu
terbuka; belum ada verdict grading. Real Auth0/manual UAT dan full auth parent
tetap terpisah. Hasil cloud diagnostik disimpan pada verification tambahan,
tanpa mengganti manifest/patch/verifikasi LMS-06 awal pada6d83474.
