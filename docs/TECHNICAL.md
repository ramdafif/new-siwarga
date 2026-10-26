# Penguatan teknis SiWarga

## Status dan batas klaim

Perubahan kode berada di Capstone copy. Konfigurasi .env lokal tetap dipakai,
termasuk database aplikasi yang sama. Migrasi bbb234424314 bersifat aditif:
kolom lama tidak dihapus dan laporan lama tetap valid. Riwayat Alembic database
bersama ikut berubah; jalankan startup/migrasi dari versi copy, bukan checkout
lama yang belum mengenal revision baru. Cookie lama perlu login ulang.

Ini bukan sertifikat siap produksi. VPS, domain/TLS, Redis produksi, repository
backup remote, penerima alert, beban jangka panjang, dan penerimaan warga masih
memerlukan konfigurasi serta pembuktian di lingkungan tujuan.

## Arsitektur dan aliran data

Browser -> Nginx HTTPS -> Gunicorn -> Flask/Jinja -> MySQL 8.
Redis menyimpan reservasi/kegagalan login bersama antar-worker. Foto berada di
direktori privat persisten; route Flask memeriksa izin sebelum mengirim berkas.
Prometheus mengumpulkan histogram aplikasi dan node exporter. Alertmanager
mengirim notifikasi operasional, bukan notifikasi laporan warga.

Lokal tetap satu proses dengan LOGIN_RATE_LIMIT_BACKEND=memory secara default.
Tanpa mengubah .env yang ada, aplikasi tetap berjalan. Ini sengaja bukan mode
multi-worker: staging/production menolak startup bila Redis, secure cookie,
atau trusted hosts belum dikonfigurasi.

## Foto

- Maksimal tiga foto per pengiriman, masing-masing 3 MiB; pemeriksaan format,
  MIME, resolusi, orientasi, dan pembersihan metadata tetap berlaku.
- File penuh adalah hasil validasi/pembersihan yang sebelumnya disimpan,
  bukan salinan mentah kamera. Nama UUID lama tetap dipakai untuk file ini.
- Thumbnail WebP: sisi terpanjang <=480 px, budget <=60.000 byte.
- Display WebP: sisi terpanjang <=1.280 px, budget <=220.000 byte.
- Encoder menurunkan kualitas, lalu resolusi bila perlu; foto kecil tidak
  diperbesar. Original dan turunannya ditulis atomik sebelum commit MySQL.
- Turunan menggunakan nama <uuid>.thumbnail.webp dan <uuid>.display.webp.
  File lama tidak ditimpa oleh backfill; hanya varian yang belum ada dibuat.
- Varian hilang menghasilkan 404, bukan fallback diam-diam ke foto penuh.
  Jalankan backfill sebelum membuka halaman dengan foto lama.
- Semua varian tetap private, no-store; tidak boleh dibuat alias Nginx publik.

~~~powershell
./.venv/Scripts/python.exe -m flask --app run.py upgrade-safe
./.venv/Scripts/python.exe -m flask --app run.py backfill-photos --batch-size 100
~~~

Backfill dapat diulang atau dilanjutkan dengan --after-id. Bila ada sumber
rusak, command keluar nonzero dan mencetak ID terkait tanpa isi fotonya.

## Interface HTTP tambahan/perubahan

- GET /lampiran/<id>?variant=original|thumbnail|display: autentikasi dan izin
  tiket tetap wajib. Default original mempertahankan perilaku URL lama.
  Unknown variant: 400; file/tiket di luar akses: 404.
- GET /pengaduan/baru menerbitkan submission_token bertanda tangan untuk
  pemilik formulir, berlaku 24 jam. POST /pengaduan wajib mengirim token ini
  dan CSRF. Token invalid/kedaluwarsa: 400. Retry token yang sama: 302 menuju
  laporan pertama, bukan membuat laporan kedua; isi retry tidak mengganti data.
- GET /health/live: proses tersedia, tanpa ketergantungan database.
- GET /health/ready: MySQL, backend login, akses direktori, dan ruang minimal
  upload tersedia; kegagalan dependency menghasilkan 503 tanpa detail rahasia.
- GET /metrics: hanya alamat loopback; Nginx menolaknya dari publik.
- POST /telemetry/vitals: sesi dan CSRF wajib, JSON maksimum 2 KiB, hanya name,
  value, page. Nama LCP/INP/CLS; page berupa enum endpoint, bukan URL/ID laporan.
  Nilai harus numerik finite nonnegatif. Sukses 204, invalid 400, terlalu besar
  413. Library web-vitals 5.1.0 disajikan lokal dengan lisensi dan integrity npm.

## Akun, audit, dan konkurensi

- Reservasi login atomik memperhitungkan request yang masih berjalan sehingga
  request paralel tidak melewati batas lima per akun dan 30 per IP/15 menit.
  Keberhasilan menghapus kegagalan akun dan reservasi IP untuk request itu;
  kegagalan/reservasi worker yang terputus kedaluwarsa setelah 15 menit.
- Redis unavailable: login 503, tidak fallback ke memori. Redis harus tunggal
  per lingkungan; implementasi ini tidak menargetkan Redis Cluster.
- Alamat email/IP untuk key rate limit di-HMAC, bukan disimpan mentah.
- session_version dicatat dalam cookie sesi bertanda tangan. Reset/ganti
  password, perubahan akun, dan perubahan status warga mencabut sesi lama.
  Password mandiri yang berhasil mempertahankan hanya sesi saat ini. Masa cookie
  tidak digeser oleh GET biasa; respons telemetry tidak pernah menulis cookie
  sesi, termasuk ketika datang terlambat sesudah logout.
- AuditEvent mencatat event, outcome, actor/target ID, request ID, detail terbatas,
  dan waktu UTC. Mutasi administratif dan audit berada dalam transaksi sama.
  Log sukses baru diterbitkan setelah commit; rollback membuang antrean log.
  Referensi actor/target sengaja bukan FK agar jejak tidak bergantung pada
  keberadaan akun. Tidak ada endpoint publik untuk membaca audit.
- Gunakan SELECT kolom audit seperlunya atau jurnal service untuk penelusuran.
  Jangan mengaktifkan logging body form/cookie. Parameter SQL disembunyikan
  pada exception engine untuk mencegah password hash ikut tercetak.
- Unique constraint (pelapor_id, submission_token) menangani retry bersamaan;
  NULL pada laporan lama tetap diperbolehkan. Status tiket tetap memakai row lock.
- Lock mutasi hanya mengambil baris tiket, tanpa eager join yang ikut mengunci
  akun/wilayah. Scope pemilik, penugasan, dan wilayah tetap diperiksa pada SELECT
  pengunci yang sama. Ini menghindari deadlock dengan FK upload/notifikasi;
  regresi menguji kelima role dan memastikan parent RT/akun dapat dikunci terpisah.

## Query dan pengukuran

Daftar/dashboard mengambil kolom ringkasan dan relasi yang dipakai komponen,
bukan deskripsi panjang, akun pelapor beserta seluruh wilayah, atau koleksi
lampiran/komentar/progres/riwayat. Scope akses tetap berasal dari scoped_tickets.
Profiling tidak menemukan kebutuhan indeks tambahan untuk gate lokal setelah
pengurangan over-fetch; evaluasi ulang EXPLAIN pada data server tujuan.

scripts/prepare_benchmark.py menyiapkan 10.009 laporan sintetis, dua RW, dan
halaman tiga foto di database khusus yang berakhiran _benchmark_test. Jangan
mengarahkannya ke database warga. BENCHMARK_DATABASE_URL dan BENCHMARK_PASSWORD
harus ada di environment proses, bukan di berkas tracked.

~~~text
python scripts/prepare_benchmark.py
python scripts/profile_queries.py --project ../Capstone --output test-results/benchmark/queries-before.json
python scripts/profile_queries.py --output test-results/benchmark/queries-after.json
python scripts/serve_benchmark.py --project ../Capstone --port 5057
python scripts/serve_benchmark.py --port 5056
python scripts/benchmark_mobile.py --base-url http://127.0.0.1:5057 --ticket-id 10 --output test-results/benchmark/mobile-before.json
python scripts/benchmark_mobile.py --base-url http://127.0.0.1:5056 --ticket-id 10 --output test-results/benchmark/mobile-after.json
~~~

Browser profile eksplisit: 390x844, DPR 1, download 200.000 byte/s, upload
93.750 byte/s, RTT simulasi 150 ms, CPU 4x, cache nonaktif. Transfer awal dan
seluruh foto setelah scroll dicatat terpisah. Ini baseline baru, bukan pengulangan
identik audit lama karena konfigurasi audit tersebut tidak tersedia di repo.

~~~text
python scripts/load_test.py --base-url http://127.0.0.1:5056 --ticket-id 10 --allow-writes --sessions 1,10,25,50 --seconds-per-stage 1800 --output test-results/benchmark/load.json
python scripts/load_test.py --base-url https://STAGING_HOST --ticket-id STAGING_TICKET --allow-writes --sessions 20 --seconds-per-stage 7200 --output test-results/benchmark/soak.json
~~~

Driver hanya untuk staging/sintetis dan benar-benar menambah komentar/laporan/
foto. Rasio 70/20/10 mengacu operasi, bukan jumlah HTTP request, karena POST
memerlukan GET formulir. Setup login tidak dihitung sebagai beban; rate limit
produksi tidak dinonaktifkan. Hasil lokal tidak membuktikan kapasitas VPS.

## Tes, lock dependency, dan CI

Gunakan Python 3.12 dan pip install -r requirements-dev.lock. requirements.lock
berisi runtime Windows/Linux; requirements-dev.lock menambah alat pengembangan.
Regenerasi setelah pembaruan disengaja dengan scripts/lock_dependencies.py,
lalu jalankan tes dan pip-audit lagi. Gunicorn dipakai hanya pada Linux.

Selain TEST_DATABASE_URL, pengujian restore memerlukan dua schema khusus.
Contoh jika database tes bernama siwarga_test:

~~~sql
CREATE DATABASE siwarga_restore_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE siwarga_recovery_drill_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON siwarga_restore_test.* TO 'siwarga_test'@'127.0.0.1';
GRANT ALL PRIVILEGES ON siwarga_recovery_drill_test.* TO 'siwarga_test'@'127.0.0.1';
~~~

Nama diturunkan dari prefix TEST_DATABASE_URL. Schema recovery_drill_test
memang dikosongkan oleh tes, tidak boleh dipakai untuk aplikasi atau data penting.
MySQL client 8 diperlukan; portabel .local diprioritaskan daripada XAMPP/MariaDB.
MYSQL_BIN_DIR dapat memilih instalasi eksplisit.

~~~text
python -m pytest --junitxml=test-results/pytest.xml
python -m pip_audit -r requirements.lock --format json --output test-results/dependency-audit.json
~~~

Redis diuji menggunakan fakeredis+Lua secara lokal. Jika TEST_REDIS_URL tersedia,
tes atomik memakai Redis nyata. CI menyediakan MySQL dan Redis, menolak tes
yang skipped, menjalankan browser Chromium, dan menyimpan artefak per commit.
