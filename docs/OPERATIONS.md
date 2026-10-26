# Operasional staging dan produksi

## Prasyarat dan pemasangan

Template deploy/ adalah bahan pemasangan, bukan bukti server sudah tersedia.
Acuan: Ubuntu LTS dengan Python 3.12, MySQL 8/InnoDB, Redis mandiri dengan
password/ACL, Nginx, systemd, restic, SSH client, Prometheus, Alertmanager, dan
node exporter. Sediakan domain, sertifikat, SMTP operasional, dan repository
backup di mesin lain sebelum menerima data warga.

1. Buat pengguna sistem siwarga dengan home /var/lib/siwarga. Tempatkan setiap
   release beserta .venv-nya di /srv/siwarga/releases/<commit>; current adalah
   symlink menuju release aktif. Source dan dependency dimiliki operator/root,
   tidak writable oleh pengguna aplikasi.
2. Buat /var/lib/siwarga/uploads, backups, metrics; pemilik siwarga. Direktori
   foto dan backup privat. metrics harus dapat dibaca user node exporter;
   gunakan group khusus dan setgid pada direktori, bukan membuat foto publik.
3. Pasang runtime dari requirements.lock ke .venv milik release. Jangan
   menyalin virtual environment Windows ke Linux.
4. Salin deploy/app.env.example ke /etc/siwarga/app.env, isi seluruh placeholder,
   mode 0600. Staging memakai database, folder, Redis namespace, dan SECRET_KEY
   berbeda dari produksi. Pengecualian konfigurasi bersama hanya untuk lokal.
5. Buat database kosong utf8mb4. Runtime mendapat hak CRUD yang diperlukan;
   jalankan migrasi dengan kredensial migrator yang memiliki hak DDL. Akses
   MySQL dan Redis hanya loopback/private network, tidak port publik.
6. Muat environment tanpa mencetak nilainya, lalu jalankan flask --app run.py
   upgrade-safe dan backfill-photos. BACKUP_LOCK dan MAINTENANCE_LOCK wajib
   menunjuk /var/lib/siwarga/maintenance.lock yang sama. Semua migrasi/purge
   berkas harus menghormati lock tersebut; jangan menjalankan DDL manual saat backup.
7. Pasang siwarga.service. Unit menggunakan .venv dalam release aktif, direktori
   runtime untuk histogram multiprocess, restart otomatis, dan kode read-only.
8. Konfigurasikan domain/cert pada nginx.conf. Pasang log_format dari
   nginx-log-format.conf pada konteks http sebelum virtual host. Jalankan nginx
   -t sebelum reload. Headers forwarded harus ditimpa Nginx, bukan diteruskan
   dari klien. Jangan mengekspos bind Gunicorn 8000 atau uploads.
9. Verifikasi HTTPS, secure/HttpOnly/SameSite cookie, login setiap role, akses
   foto, restart aplikasi, reboot host, serta persistensi data/foto.

Jangan memakai --preload pada Gunicorn tanpa menguji ulang konfigurasi metrics.
Prometheus multiprocess directory harus kosong saat service baru mulai; systemd
menghapus RuntimeDirectory saat service berhenti. Batasi ukuran/retensi journal.
Access log aplikasi/proxy tidak memasukkan query string, cookie, atau body form.

## Backup tanpa menghentikan layanan

File foto committed adalah immutable. Tidak ada penghapusan fisik foto melalui
UI. Jika menambah fitur penghapusan/retensi, operasi fisiknya WAJIB menggunakan
maintenance lock yang sama; penulisan file baru tetap boleh berjalan.

Alur backup:

1. Ambil lock agar tidak berbarengan dengan migrasi atau penghapusan fisik.
2. Pastikan tabel aplikasi memakai InnoDB, ambil mysqldump single-transaction.
3. Import dump ke schema khusus berakhiran _restore_test, tidak boleh sama
   namanya dengan database aplikasi meskipun host/alias berbeda.
4. Ambil daftar lampiran dari schema hasil restore tersebut, bukan query live.
   Salin hanya original yang dirujuk snapshot; verifikasi checksum sumber/salinan.
   Upload yang commit setelah snapshot tidak merusak konsistensi backup.
5. Tulis manifest dan checksum dump. Snapshot gagal tetap bernama .pending-*;
   jangan menandainya sebagai berhasil atau mengunggahnya sebagai backup valid.
6. Kirim snapshot tervalidasi ke restic SFTP di luar server; periksa repository,
   terapkan retensi 14 harian/empat mingguan, simpan dua snapshot lokal terakhir.
7. Tulis success marker hanya setelah seluruh langkah berhasil. Umur backup
   dihitung dari waktu snapshot database, bukan waktu upload remote selesai.

Buat schema verifikasi dan kredensial khusus; jangan menjalankan aplikasi pada
schema itu. Salin backup.env.example ke /etc/siwarga/backup.env dan isi nilainya.
Sediakan kunci SSH/known_hosts pada home pengguna service /var/lib/siwarga/.ssh,
pin host key dan aktifkan StrictHostKeyChecking; jangan menggunakan accept-any.
Kunci restic disimpan di RESTIC_PASSWORD_FILE dengan mode 0600 dan salinan aman
di luar server. Siapkan kebijakan immutable/versioned backup di penyedia jika
tersedia; kredensial pada server aplikasi bukan perlindungan terhadap kompromi
host total. Jangan menyimpan password/kunci dalam Git.

Inisialisasi repository satu kali dengan restic init menggunakan environment
backup. Uji service siwarga-backup.service secara manual, periksa hasil remote,
baru aktifkan timer. Jadwal 03.00/15.00 WIB memberi margin terhadap RPO 24 jam.
Snapshot .pending-* perlu ditinjau dan dibersihkan operator setelah masalahnya
teridentifikasi; alert disk harus aktif agar kegagalan tidak memenuhi server.

## Restore dan latihan pemulihan

1. Operator mengambil snapshot dari repository remote ke mesin baru memakai
   kredensial/kunci cadangan. Mulai stopwatch dari insiden/keputusan pemulihan,
   bukan hanya waktu import SQL.
2. Jalankan python scripts/backup.py verify SNAPSHOT. Jangan mengeksekusi SQL
   dari arsip yang tidak dikenal atau gagal checksum.
3. Buat database pemulihan kosong dengan nama berbeda dari database aplikasi;
   siapkan direktori foto baru yang kosong. RESTORE_DATABASE_URL menunjuk DB ini.
4. Muat environment aplikasi yang menunjuk database lama hanya sebagai acuan
   proteksi. Jalankan python scripts/backup.py restore SNAPSHOT --uploads NEW_DIR.
   Script menolak target aplikasi, database berisi tabel, dan folder foto berisi
   data. Original dipulihkan dan turunan WebP dibuat ulang.
5. Jalankan versi aplikasi yang cocok dengan snapshot terhadap database/folder
   baru. Uji login individual, scope RT/RW, dashboard, detail, dan foto privat.
6. Catat waktu snapshot, waktu pulih, laporan terakhir yang kembali, serta
   kehilangan data. Target RPO <=24 jam dan RTO <=4 jam baru terbukti setelah
   latihan lengkap, termasuk akses repository dan provisioning.
7. Pengalihan database/domain dilakukan operator setelah verifikasi; jangan
   menimpa database lama atau menghapus snapshot untuk mempercepat cutover.

Tes otomatis membuktikan dump/manifest/restore, upload setelah snapshot, login,
dan pembukaan foto pada MySQL lokal. Tes itu bukan pembuktian restore remote
atau RTO server produksi. Lakukan latihan sebelum pilot dan berkala setelah rilis.

## Monitoring dan alert

Pasang prometheus.yml, alerts.yml, dan konfigurasi Alertmanager yang sudah diisi.
Semua UI/port monitoring bind ke loopback atau jaringan admin. Node exporter
memakai --collector.textfile.directory=/var/lib/siwarga/metrics serta
--collector.systemd --collector.systemd.unit-include=siwarga.*; pastikan mode
file .prom dan group direktori mengizinkan pembacaan tanpa akses ke foto.

Pantau latency/p95 per endpoint dan metode, HTTP 5xx, throughput, CPU, memori,
disk, koneksi MySQL, kesiapan Redis, dan umur/status backup. Alert bawaan memakai
p95 GET satu detik, error 0,1%, pemakaian CPU/memori/koneksi 80%, disk bebas 20%,
dan umur backup 18 jam. Sesuaikan evaluasi hanya melalui perubahan terdokumentasi.

Sebelum pilot: hentikan Redis sementara di staging, simulasikan backup gagal,
ubah threshold disk untuk pengujian, dan pastikan email diterima admin utama
serta cadangan. Pulihkan kondisi dan threshold sesudahnya. Jangan melakukan
fault injection di database warga. Laporan Web Vitals p75 memerlukan sampel
penggunaan cukup; histogram kasar bukan pengganti analisis sampel log asli.

## Runbook gangguan singkat

- Login 503: periksa Redis, koneksi/ACL, namespace, dan journal; jangan mematikan
  limiter atau mengubahnya menjadi memory di produksi.
- Aplikasi 5xx: catat X-Request-ID, periksa journal, health/ready, MySQL, kapasitas
  koneksi dan disk. Jangan menyalin cookie/password pengguna ke tiket bantuan.
- Foto 404: verifikasi scope dulu, lalu keberadaan original/varian. Backfill
  hanya varian yang hilang; sumber hilang memerlukan restore, bukan thumbnail palsu.
- Disk rendah: hentikan perluasan penggunaan, periksa snapshot gagal dan retensi
  log, lalu tambah kapasitas. Jangan menghapus original dari uploads sembarangan.
- Backup gagal: periksa koneksi SFTP, kunci, ruang disk, schema verifikasi dan
  checksum. Jalankan ulang; marker sukses tidak boleh dipalsukan.

## Rilis dan rollback

Catat commit, hasil CI/audit, migrasi, dan persetujuan pengurus. Backup remote
harus berhasil sebelum migrasi. Tunggu backup aktif selesai sebelum pergantian
release; jangan menginterupsinya. Siapkan .venv tiap release dari lockfile,
jalankan migrasi aditif via upgrade-safe, arahkan current, restart, lalu smoke test.

Rollback rutin hanya mengembalikan release aplikasi yang telah diuji kompatibel
dengan schema saat ini; jangan downgrade DB atau restore backup di atas laporan
baru. Bila rilis tidak kompatibel, hentikan penulisan dan lakukan prosedur insiden
terencana. Versi MVP lama tidak mengenal revision Alembic baru, sehingga skrip
startup/migrasinya bukan jalur rollback otomatis. Pengujian kompatibilitas wajib
mendahului persetujuan setiap rilis berikutnya.
