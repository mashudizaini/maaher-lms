# LMS-05 — tugas berversi, draf dan immutable submissions

11 November2026 WIB. Pemilik meminta LMS-05 setelah review5b675e6 APPROVED_WITH_NOTES
untuk development/UAT sintetis kecil–menengah. Base54543a8; auth parent terpisah.
F1 CLOSED, F2 health CLOSED; residualF5 MEDIUM dan F6/F7 LOW ditangani dalam scope.

Prasyarat: lesson validasi tersimpan sebagai bukti Fernet yang mengikat policy,
tenant/lesson/revision dan digest content/resources. Save menandatangani setelah
validasi; publish hanya memverifikasi, tidak memakai parser. Legacy/invalid bukti
mendapat409 dan batch validasi terpisah, bukan parsing80detik di publish. Dua slot
interactive+maintenance lane terpisah; kontrol terlarang422 sebelumIPC, frame
bounded, capability memory tidak diam diabaikan. CPU250ms/wall2s untuk margin
valid30KB; produksi menolak bila memory cap tidak aktif. Synthetic Mac diberi WARN.

Feature: admin/assigned teacher create/edit immutable assignment versions dengan
rubric(total100), language python/javascript/text, starter code, max attempts1–20,
optional aware UTC deadline yang UI tampil/masukkan sebagai WIB, allow-late.
Draft version baru tidak mengubah published version sampai publish eksplisit.
Archive/unpublish tidak menghapus histori. 100 assignments/course,100versions/task.

Siswa enrollment aktif pada course terbit hanya tugas published. Draf save memakai
optimistic revision; publish versi baru memerlukan konfirmasi simpan ulang ke
versi baru. Submit mengambil snapshot draf tersimpan dengan UUID idempotency,
terikat assignment version, attempt number dan server timestamp/late status.
History append-only, tanpa UPDATE/DELETE grant; retries sama tidak menambah attempt.
Student tidak melihat peer; staff hanya course authorized. History versi lama
milik sendiri tetap dapat dibaca ketika tugas tidak terbit, selama course/enrollment
masih sah. Revoke/archive course menutup read/write; regrant eksplisit sesuaiparent.

RLS+FK komposit sebelumAPI, check authority sebelumlock, serialized attempt/deadline
pada DB trigger, budgets120/min learner dan60/min staff tetap. Source code hanya
teks escaped, tidak dieksekusi. UI staff /assignments, student /work, link dari/learn.

Tes: seluruhparent; peer/tenant/FK/version/stale-draft; concurrent/idempotent submit,
server deadline+late/maxattempt; immutability/direct runtimeSQL; published pointer;
keyring/bukti stale/tamper; 1500×29KB publish bersamaan writer/health; controls/memory
cap reporting/CPU; guarded seeded rollback preserving parent; realbrowser dua sesi.
Schema0011 validation +0012 assignments; hanya DB test kosong baru untukfixtures.
Tidak merge/deploy, grading LMS06, uploads atau learner runner pada scope ini.

## Tindak lanjut review LMS-05 — 11 November 2026 WIB

Pemilik meminta kelanjutan setelah verdict APPROVED_WITH_NOTES pada4a450d5.
F5 publish/legacy, F6 dan F7 Linux CLOSED menurut ringkasan reviewer; F9/F10
MEDIUM dan F11 LOW menjadi scope perbaikan. F12 tetap batas operasional terbuka.

Perubahan: antrean parser bounded dengan giliran tenant dan akun tervalidasi,
max satu validation aktif/menunggu per akun per lane, dua interactive workers dan
satu maintenance worker. Tidak ada proses per tenant/account atau antrean tak
terbatas. Validasi harus selesai dalam deadline antrean/proses, overload tidak
menghabiskan seluruh thread API. CPU hard budget1000ms (review valid266ms),
wall3000ms, capability memory tetap256MiB/Linux dan WARN local Mac/fail outside.
Kalibrasi diagnostik mengukur korpus valid berulang tanpa cache; tidak menonaktifkan
budget atau mengubahnya tanpa batas. Hanya tes kemampuan memori memakai skipif
Linux; kontrol/frame/valid-Markdown/CPU selalu berjalan, tidak ada --deselect.

Deadline UTC overflow menjadi validation422. Handler422 menghapus input/ctx dan
menormalkan teks error agar surrogate tidak memicu kegagalan encoding respons;
parent lesson dan draf termasuk cakupan. Bukti validasi lama tetap sah karena
aturan URL/Markdown/kontrol tidak dilonggarkan; kenaikan budget tidak memaksa
revalidasi/menerbitkan semua tugas ulang.

Tes: regresi penuh, korpus dense valid30k berulang, CPU timer nyata, memory tests
terpisah, bounded queue/same-actor/fair tenant/cancellation, HTTP/TCP beberapa sesi
2/4/8 attacker plus penulis biasa lintas/sama tenant (bukan hanya model thread),
Unicode mentah dan date-boundary menghasilkan422, parent proof/key/tenant suite,
browser lama dan baru. Tidak mengubah schema/auth provider/runner/deploy.
