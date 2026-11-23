# Lampiran audit tambahan SiWarga - 19 November 2026

Dokumen induk: [PRODUCTION_READINESS.md](../PRODUCTION_READINESS.md).
Status: **backlog tambahan, belum implementasi atau sertifikasi siap live**.
Zona waktu baseline: Asia/Jakarta.

## 1. Asal masukan dan batas verifikasi

Pengguna mengirim laporan audit tambahan beserta daftar `Ran`/`Analyzed`.
Daftar itu dicatat sebagai **cakupan yang dilaporkan oleh audit masukan**,
bukan pernyataan bahwa semua perintah/tes diulang pada pekerjaan ini.
Penambahan ini hanya mengubah dokumentasi. Tidak ada deploy, migrasi, restart,
load/fault test, login/mutasi produksi, atau pemasangan dependency.

Beberapa bagian berisiko tinggi dibaca ulang secara statis: lifecycle backup,
limiter, sesi/header/error, telemetry, query/index deklaratif, penanganan foto,
mutasi akun, serta template Nginx/provisioning. Dua GET metrics loopback tanpa
credential dipakai untuk membedakan perilaku Host aktual. Tidak ada inspeksi
nilai rahasia atau asumsi bahwa file konfigurasi aktif identik dengan template.

Istilah bukti pada lampiran:

- **SOURCE**: terlihat pada source/template yang dibaca, bukan bukti deployment aktif.
- **OBSERVED**: respons baca-saja yang diamati pada pemeriksaan tambahan ini.
- **HISTORICAL**: berasal dari artefak/laporan lama; harus diberi tanggal/versi.
- **VERIFY**: dugaan, pilihan solusi, atau keadaan runtime yang perlu dibuktikan.

Prioritas PR-01 sampai PR-24 mengikuti tabel induk. Label asli "5 blocker P0"
tidak diadopsi sebagai lima kerentanan kritis yang sudah terbukti: kelima area
tetap diprioritaskan sebagai gate data asli sesuai dampak dan bukti. Fondasi
yang baik seperti RBAC, CSRF, session versioning, upload aman, dan idempotensi
tetap dipertahankan; tidak ada jaminan seluruh kemungkinan deadlock/DoS sudah
hilang hanya karena skenario tes terdahulu lulus.

## 2. Pelurusan klaim sebelum dijadikan pekerjaan

| Masukan laporan | Batas bukti / keputusan backlog |
| --- | --- |
| "212 tes dan pip-audit bersih" | HISTORICAL, 10 November 2026. PR-04 memuat advisory yang lebih baru; bukan jaminan audit dependency saat ini bersih. |
| "11 modified + 6 untracked" dan `.local/` sekitar 2,1 GB | Snapshot audit masukan. Jumlah berubah ketika dokumen ditambah; inventaris ulang sebelum rilis, jangan hapus otomatis. |
| ".env bocor" | Mode 0664 menunjukkan risiko baca oleh akun OS lokal. Tidak membuktikan file dapat diunduh via web atau rahasia produksi sudah dicuri. |
| `load_dotenv()` menimpa environment live | SOURCE menunjukkan pemanggilan tanpa override; variabel yang belum ada dapat terisi, yang sudah ada diprioritaskan. Bedakan pencampuran dev/test dari overwrite credential produksi. |
| "Scrape loopback pasti 400" | OBSERVED: GET metrics ke loopback dengan Host bawaan 400, dengan Host domain yang diizinkan 200. Scraper harus diuji memakai konfigurasi Host yang benar. |
| "Email/IP acak pasti memenuhi Redis 64 MB" | VERIFY. Limiter sudah memiliki batas akun/IP dan TTL 900 detik; IP klien dibatasi trust proxy. Ukur cardinality, klien terdistribusi, dan OOM di staging; jangan uji DoS live. |
| "Telemetry terbuka untuk siapa saja" | SOURCE: endpoint memakai login, ukuran <=2048 byte, nama/page allowlist, serta rentang numerik. Yang kurang adalah kontrol frekuensi/reliabilitas data, bukan semua validasi input. |
| "Gzip/HTTP/2/server_tokens tidak ada di vhost berarti tidak aktif" | VERIFY konfigurasi include/global dan negosiasi aktual. Template bukan konfigurasi efektif; HTTP/2 dan Brotli bukan syarat keamanan universal. |
| "HSTS hilang pada seluruh static live" | Template generik memiliki risiko inheritance. Template `.local/deploy/nginx-https.conf` sudah menambahkan HSTS di static; uji respons aktif sebelum menyebut live kehilangan HSTS. |
| "Belum ada consent checkbox berarti terbukti melanggar UU PDP" | Bukan kesimpulan audit teknis. Tetap wajib menyepakati pemberitahuan, dasar pemrosesan, retensi, akses, dan hak pengguna; kebutuhan consent dinilai pengelola/pihak kompeten. |
| "Font 6-10 px berarti otomatis gagal WCAG AA" | SOURCE menunjukkan deklarasi kecil, bukan ukuran hasil cascade. Ukur keterbacaan/kontras dan uji resize/reflow; tidak mengklaim rasio <4,5:1 tanpa pengukuran. |
| "Startup berjarak sekitar 5 detik membuktikan downtime 5 detik" | HISTORICAL timestamp proses saja. Butuh probe eksternal saat cutover staging untuk mengukur error/durasi gangguan. |
| "P95 50 sesi lama membuktikan kandidat sekarang gagal" | HISTORICAL dari validasi terdahulu. Tidak boleh digabung dengan smoke 48 request untuk mengklaim kapasitas versi sekarang; ulangi dengan manifest dan beban yang jelas. |
| "Control socket Gunicorn berarti celah publik" | Log lama menunjukkan socket lokal; perlu cek versi, kebutuhan, owner/mode, serta siapa dapat mengaksesnya. Jangan menyebutnya endpoint internet tanpa bukti. |

Koreksi ini mempertahankan tindakan pencegahan tanpa membesar-besarkan exploit,
menutupi blocker operasional, atau mengubah klaim hukum menjadi fakta teknis.

## 3. Pengayaan pekerjaan yang sudah ada

| Masukan tambahan | Masuk ke paket | Detail penerimaan tambahan |
| --- | --- | --- |
| Checkout live kotor, `.env`, `.local/`, file SQL nyasar | PR-05/06/15 | Isolasi release/dev/test, inventaris ownership, traceability, rollback, tanpa menghapus perubahan pengguna |
| Backup lokal 14 salinan penuh, pending tertinggal, pruning corrupt | PR-01/02 | Kapasitas disk dan status fase terpisah; uji korupsi, cleanup aman, tidak kehilangan salinan terakhir yang baik |
| Scrape Host/port, metrics backup lokal, expiry TLS, core units, Redis memory | PR-02 | Konfigurasi scraper aktual berhasil, external probe, alert sungguh diterima dan diakui |
| Register/email enumeration, login 429 menulis DB, akun/vitals/write spam | PR-03 | Batas frekuensi sebelum biaya mahal; audit teragregasi; pertahankan otorisasi/CSRF dan fail-closed |
| Recovery superadmin dan file credential awal | PR-07 | Recovery individual dan disposisi credential diverifikasi, bukan mengandalkan bootstrap |
| Privasi/retensi/kontak tanpa klaim hukum berlebihan | PR-08 | Kebijakan disetujui dan dapat dibaca warga; proses koreksi/hapus aman |
| Riwayat/komentar/lampiran tak terbatas | PR-09 | Pagination dan akses per halaman; tetap tersedia jejak progres yang diperlukan |
| Audit perubahan wilayah/kategori dan akun | PR-10/18 | Actor/target/outcome, transaksi konsisten, data minimum, tidak mengulang amplifikasi audit |
| Banyak teks kecil, fokus sidebar, error field | PR-13/21 | Computed styles, pembaca layar/keyboard, keterbacaan pengguna, form tahan error |
| UAT kosong, smoke login live belum ada, bukti beban/soak belum cukup | PR-11/12/16/24 | Bukti per kandidat dan lingkungan; alur tulis live memerlukan otorisasi tersendiri |

### Catatan backup dan batas penghapusan

`scripts/backup.py` membuat direktori `.pending-*`, menyalin original memakai
`shutil.copyfile()`, memverifikasi, lalu rename snapshot. `prune_local()`
memverifikasi snapshot lama sebelum menghapus dan menolak path di luar batas.
Wrapper lokal memakai `keep=14`; wrapper offsite `deploy/backup.sh` memiliki
fase restic/pruning dan baru menulis marker sukses setelah seluruh rangkaian.

Karena itu, korupsi snapshot lama dapat menggagalkan housekeeping walaupun
snapshot baru sudah terbentuk atau dikirim. Rencana perbaikannya **bukan**
melewati checksum, menghapus semua pending, atau memalsukan sukses. Tetapkan
status per fase, karantina yang aman, alert kegagalan retensi, lock untuk job
aktif, dan tes disk penuh/crash di staging. Verifikasi kebutuhan retensi foto,
kapasitas puncak, dan perlakuan backup sesuai kebijakan privasi.

### Catatan monitoring Host dan sertifikat

Pemeriksaan baca-saja pada 19 November 2026:

| Permintaan | Respons |
| --- | --- |
| GET `http://127.0.0.1:5010/metrics`, Host bawaan | 400 |
| GET alamat yang sama, Host `siwarga.elkyno.com` | 200 |

Ini menjelaskan mengapa metrics dapat sehat pada satu pemeriksaan tetapi
scrape generik gagal. Koreksi konfigurasi dengan trusted Host minimum yang
benar; jangan menambahkan wildcard atau mematikan trusted-host validation.
Audit ini tidak mengubah Host allowlist atau konfigurasi scraper.

Tanggal sertifikat **31 Januari 2027** berasal dari bukti terdahulu dalam
laporan, bukan pembacaan sertifikat terbaru pada pekerjaan ini. PR-02 harus
memantau sertifikat yang benar-benar disajikan serta mekanisme renewal;
jangan bergantung pada tanggal tetap di dokumen.

## 4. Paket pekerjaan tambahan

### PR-17 - Edge Nginx, log aman, dan error di luar Flask

**Dasar:** SOURCE pada `deploy/nginx.conf`, `deploy/nginx-log-format.conf`, dan
`.local/deploy/nginx-https.conf`. Template lokal memakai format access log
default, sedangkan template generik menunjuk format `siwarga` tanpa query string.
Konfigurasi include/global aktif belum dibuktikan sama dengan keduanya.

- [ ] Inventaris versi Nginx, konfigurasi efektif, include, ALPN, dan header
  aktual sebelum memilih sintaks HTTP/2; aktifkan jika cocok dan bermanfaat.
  Evaluasi gzip/Brotli pada teks/aset, biaya CPU, dan sensitivitas respons;
  jangan mengompres seluruh respons sensitif tanpa menilai risiko.
- [ ] Terapkan rate/connection limits bersama PR-03 dengan alamat klien tepercaya,
  pengecualian health yang sempit, respons 429 yang jelas, serta tanpa membuka
  port Gunicorn/DB/Redis atau mengganggu virtual host aplikasi lain.
- [ ] Gunakan access log yang meminimalkan data: hindari query pencarian,
  credential, Referer sensitif, dan retensi IP yang tidak perlu. Verifikasi
  format efektif, permission, rotasi, retensi, dan alur investigasi operator.
- [ ] Periksa inheritance `add_header` pada setiap location/error; pertahankan
  HSTS/nosniff pada status yang diinginkan dengan `always` bila sesuai.
  Periksa versi/konfigurasi inheritance, bukan sekadar menyalin satu snippet.
- [ ] Sediakan error 413/502/503/504 berbahasa Indonesia yang ringan dan tetap
  memakai status benar. Halaman harus tersedia saat upstream mati; jangan
  menjadikannya redirect 200 atau memuat informasi backend/credential.
- [ ] Verifikasi batas ukuran/body timeout dan petunjuk upload konsisten dengan
  Flask; uji request oversized di staging, termasuk error sebelum mencapai app.
  `server_tokens off` boleh jadi hardening tambahan, bukan pengganti patch.

**Lulus:** status/header/cache/log pada respons publik aktual sesuai kebijakan,
error upstream dapat dipahami, dan proteksi edge tidak dapat dilewati lewat
port alternatif. HTTP/2/Brotli diputuskan dari kompatibilitas dan pengukuran,
bukan dijadikan blocker baru secara otomatis.

**Bukti:** versi/config diff yang disanitasi, matriks status/header, sampel log
tanpa data warga, hasil TLS/ALPN, dan uji fault/oversize hanya di staging.

### PR-18 - Security headers, cache, sesi, audit, dan pesan error

**Dasar SOURCE:** `app/__init__.py:141`, `app/auth.py:51`,
`app/auth.py:109`, `app/admin.py:166`, `app/templates/error.html`.
Public login/register belum diberi `no-store` eksplisit oleh hook yang hanya
melakukannya untuk pengguna terautentikasi. Ini risiko konfigurasi cache masa
depan, bukan bukti CDN saat ini membocorkan token. Error 500 menyebut MySQL
dan template belum menampilkan kode referensi request.

- [ ] Tetapkan kebijakan cache untuk form ber-CSRF, sesi, foto privat, dan
  respons error, termasuk pengguna anonim; verifikasi browser/proxy/CDN tidak
  membagikan token/isi pengguna lain. Aset berversi memakai kebijakan terpisah.
- [ ] Hapus inline styles yang tidak perlu sebelum memperketat `style-src`;
  evaluasi `Permissions-Policy`, COOP, dan CORP sesuai kebutuhan aplikasi.
  Uji upload/kamera, tab/window, font, dan integrasi agar header tidak merusak alur.
- [ ] Selaraskan kebijakan sesi saat registrasi/login; perbedaan
  `session.permanent` perlu keputusan eksplisit. Rotasi state sesi/CSRF setelah
  perubahan password/tindakan kritis harus tetap menjaga `session_version`,
  pencabutan sesi lama, dan kebutuhan concurrent request yang sah.
- [ ] Tambah audit registrasi dan kegagalan perubahan password yang dibatasi;
  tinjau perubahan email/hak/status dengan data minimum atau fingerprint.
  Jangan menyimpan password, seluruh form, atau email mentah tanpa kebutuhan.
- [ ] Gunakan pesan 500 generik dan request/reference ID yang aman bagi warga;
  detail exception hanya di log privat. Pastikan ID dapat dicari operator dan
  tidak dapat dipakai untuk injeksi log atau menebak data pengguna lain.
- [ ] Tambahkan `Retry-After` pada penolakan yang memiliki waktu pemulihan
  diketahui, terutama rate limit; jangan menjanjikan waktu pulih 503 sembarang.
  Jaga status/outcome audit sesuai transaksi yang benar-benar berhasil.

**Lulus:** token/sesi tidak bocor lewat cache/log, perubahan credential
tercatat dan mencabut sesi sesuai kebijakan, error memberi petunjuk yang aman,
dan header tambahan tidak memutus fitur. Tidak ada audit failure yang justru
mengulangi amplifikasi database yang ditangani PR-03.

**Bukti:** regresi anonim/terautentikasi dan dua pengguna, pemeriksaan cache/
header, tes rotasi/pencabutan sesi, serta contoh event/request ID sintetis.

### PR-19 - Transaksi singkat, foto, dan anggaran worker

**Dasar SOURCE:** `app/tickets.py:202`, `app/tickets.py:217`, `app/uploads.py`,
`app/image_variants.py`, `deploy/gunicorn.conf.py`. Progres/penyelesaian mengambil
lock tiket sebelum validasi/render/persist foto. Default konfigurasi dua worker
dan dua thread adalah anggaran awal, bukan kapasitas terukur atau bukti saturasi.

- [ ] Ukur lock wait/durasi transaksi, CPU/memori Pillow, I/O/fsync, dan respons
  saat beberapa petugas serta pembaca foto bekerja bersamaan di staging.
- [ ] Rancang persiapan gambar/temp file di luar lock panjang, setelah pemeriksaan
  akses awal dan pembatasan biaya; lakukan pemeriksaan ulang akses, penugasan,
  versi/status tiket saat lock diperoleh sebelum menyimpan mutasi final.
- [ ] Pertahankan atomisitas aplikasi, cleanup file sementara/orphan, urutan
  commit, dan idempotensi saat render gagal, lock timeout, worker mati, atau
  request bersamaan. Jangan sekadar memindahkan validasi lalu membuka TOCTOU.
- [ ] Evaluasi `X-Accel-Redirect` sebagai pilihan offload foto setelah otorisasi
  Flask, dengan location `internal`, path server-terkontrol, MIME/disposition
  benar, dan penolakan akses langsung. Tetap pertahankan privasi/no-store;
  jangan menggantinya dengan cache publik atau folder uploads publik.
- [ ] Sesuaikan worker/thread dengan RAM, CPU, budget koneksi DB, batas pixel,
  dan beban foto hasil PR-11; jangan hanya menambah worker hingga RAM habis.
- [ ] Ukur cutover/reload di staging menggunakan probe eksternal dan metrik
  request hilang. Pilih reload/draining yang didukung bila perlu; target
  downtime disepakati, bukan klaim zero-downtime dari log startup saja.

**Lulus:** lock tidak mencakup kerja mahal yang dapat dipersiapkan lebih dulu,
konkurensi tidak merusak data/izin, dan anggaran resource memenuhi target.
Offload Nginx bukan kewajiban jika cara yang ada terbukti memenuhi target.

**Bukti:** distribusi lock wait/latency, skenario konkurensi/failure, pemeriksaan
file orphan/otorisasi, konfigurasi worker, dan rekaman probe cutover staging.

### PR-20 - Query yang diperlukan, index, timeout, dan koneksi

**Dasar SOURCE:** `app/models.py:119`, `app/routes.py:47`,
`app/tickets.py:94`, `app/__init__.py:34`. Detail eager-load `progres`, dashboard
menghitung `category_counts`, dan daftar mengambil RT pada role yang tidak
memakai filter itu. Verifikasi pemakaian sebelum menghilangkan data/query.
Index model bukan inventaris definitif index yang sudah terpasang di live.

- [ ] Hapus/lazy-load query atau relasi yang tidak dipakai pada jalur tersebut;
  bila progres dibutuhkan warga, putuskan menampilkannya secara bounded alih-alih
  menghapus bukti penanganan. Jangan melemahkan scope atau kebijakan akses.
- [ ] Gunakan query plan dan dataset representatif untuk menilai kandidat:
  `notifikasi(user_id, sudah_dibaca)`, `(user_id, created_at, id)`,
  `pengaduan(rt_id, status, created_at)`, `audit_event(request_id)`, dan
  `audit_event(target_id, created_at)`. Catat index existing/implicit agar tidak
  membuat duplikat atau menambah biaya write tanpa manfaat.
- [ ] Nilai index riwayat sesuai query: kandidat `(created_at, id)` untuk feed
  lintas tiket berbeda dari `(pengaduan_id, created_at, id)` untuk detail tiket.
  Urutan kolom/arah dan strategi pagination harus mengikuti query sebenarnya.
- [ ] Sepakati connect/read/write timeout driver dan budget pool/overflow per
  worker termasuk job/migrator. Hitung total terhadap `max_connections` dan
  cadangan operasi; jangan membuat semua thread menggantung tanpa batas.
- [ ] Uji timeout/rollback dan hasil commit tak pasti; retry mutasi hanya jika
  idempotensi/hasil awal diketahui. Uji migrasi index serta rollback aplikasi
  terhadap schema yang sudah diperbarui, tanpa downgrade DB sembarangan.
- [ ] Tetapkan retensi/arsip notifikasi dan audit bersama PR-08/10, termasuk
  pagination, kapasitas, serta penghapusan yang tidak merusak jejak wajib.

**Lulus:** jumlah query dan response size dibatasi, plan/index dibenarkan data,
tidak ada drift schema, timeout tidak menimbulkan duplikasi, dan koneksi total
tetap di bawah budget saat beban puncak/backup. Tidak wajib menambah semua
index usulan bila hasil pengukuran menunjukkan tidak diperlukan.

**Bukti:** query count/plan sebelum-sesudah, index/migrasi, perhitungan koneksi,
tes timeout/konkurensi, dan perbandingan latency pada kandidat rilis yang sama.

### PR-21 - Foto HP, formulir tahan error, dan keterbacaan

**Dasar SOURCE:** batas foto 3 MB, format JPEG/PNG/WebP dan pencocokan MIME di
`app/uploads.py`; CSRF 1 jam dibanding sesi permanen 8 jam; form error terpisah
dan belum ada pencegahan submit/loading yang menyeluruh di `app/static/js/app.js`.
Deklarasi font kecil perlu diperiksa sebagai computed styles bersama PR-13.

- [ ] Uji foto Android/iPhone/WebView/file picker aktual: format, orientasi,
  nama file, MIME kosong/generik, pixel besar, dan jaringan lambat. Tentukan
  dukungan HEIC/HEIF atau panduan konversi yang jelas; dukungan semua format
  bukan syarat otomatis dan tidak boleh melewati pemeriksaan decoder/magic.
- [ ] Evaluasi resize/kompresi sisi klien yang terbatas memori dan dilakukan
  bertahap sebelum upload; pertahankan kualitas/orientasi serta batas ukuran.
  Server tetap memvalidasi ukuran/pixel/format dan membersihkan metadata.
  Pelonggaran MIME, bila diperlukan, wajib disertai tes file berbahaya.
- [ ] Pertahankan isian aman pada error validasi, CSRF kedaluwarsa, 400/413,
  dan gangguan koneksi; sediakan cara memperoleh form/token baru tanpa
  otomatis mengulang mutasi. Jangan memperpanjang lifetime CSRF hanya untuk
  menyembunyikan masalah pemulihan formulir.
- [ ] Jika memakai draft, tentukan opt-in, lokasi, masa hidup, dan pembersihan
  saat logout di perangkat bersama. Jangan menyimpan password, token, foto,
  atau isi sensitif tanpa kebijakan privasi dan mekanisme penghapusan.
- [ ] Tambahkan status loading/disable submit yang aksesibel setelah validasi
  dan konfirmasi berhasil; pulihkan saat gagal. Uji double-click, kembali
  browser, retry komentar/progres/admin, dan duplicate mutation di server;
  tombol disabled bukan pengganti idempotensi.
- [ ] Sepakati ukuran teks yang nyaman, misalnya body 14-16 px dan caption
  >=12 px sebagai target desain awal, lalu uji dengan warga. Ukur kontras
  sesuai kategori teks serta resize/reflow; ini bukan aturan minimum font WCAG.

**Lulus:** foto didukung berhasil dikirim atau ditolak dengan bantuan jelas,
ketikan tidak hilang tanpa jalur pemulihan yang disepakati, dan submit tidak
menggandakan tindakan. Form tetap ber-CSRF, scope aman, dan dapat dipakai
keyboard/pembaca layar serta pengguna HP kecil.

**Bukti:** matriks perangkat/format, hasil uji CSRF/413/retry/double-submit,
pengukuran computed font/kontras, dan hasil UAT peserta.

### PR-22 - Aset statis, identitas publik, dan berbagi tautan

**Dasar SOURCE:** `app/templates/base.html` belum memuat metadata Open Graph
dan canonical; URL aset belum berversi. Template Nginx memakai cache satu jam;
logo PNG sekitar 1,5 MB ada di static. File besar yang tidak direferensikan
tidak otomatis menambah transfer halaman dan bukan kebocoran rahasia.

- [ ] Tambah cache-busting hash/versi yang cocok dengan release immutable;
  uji upgrade saat cache lama masih ada. Pilih kebijakan cache immutable hanya
  untuk URL konten berversi, bukan form ber-CSRF atau foto privat.
- [ ] Inventaris font/aset yang benar-benar dipakai; evaluasi WOFF2/optimasi
  gambar dengan lisensi dan fallback yang sesuai. Hapus/pindahkan aset tak
  terpakai hanya setelah ownership/dependensi dikonfirmasi, bukan otomatis.
- [ ] Sediakan favicon/touch icon dan putuskan `robots.txt` untuk halaman publik
  agar respons jelas tanpa noise 404 yang tidak perlu. Robots bukan kontrol
  akses dan tidak boleh menggantikan login atau menyingkap URL privat.
- [ ] Tambahkan OG title/description/image/url dan canonical pada landing publik
  jika dibutuhkan untuk share grup; jangan menaruh judul/foto/identitas tiket
  privat pada preview, cache bot, atau halaman anonim.
- [ ] Bahas ekspor rekap CSV dan stylesheet print sebagai fitur opsional yang
  memerlukan persetujuan scope. Jika dipilih, pertahankan role/scope, minimasi
  data, serta mitigasi formula injection CSV dan kebocoran hasil cetak.

**Lulus:** rilis tidak menyisakan campuran aset lama/baru, identitas publik
konsisten, dan optimasi terbukti pada transfer yang diukur. OG/print/ekspor
bukan blocker keamanan atau kewajiban MVP baru.

**Bukti:** manifest aset, pengujian cache versi, network transfer, preview
publik tanpa data warga, serta keputusan fitur opsional.

### PR-23 - Konsistensi tiket, akun, dan navigasi pengurus

**Dasar SOURCE:** `app/tickets.py:121`, `app/admin.py:166`,
`app/routes.py:93`, template registrasi/pengelolaan akun. Nomor tiket memakai
bulan UTC; mutasi pengurus tidak mencakup semua notifikasi/penanganan penugasan
yang dipertimbangkan pada laporan tambahan.

- [ ] Sepakati apakah bulan nomor tiket mengikuti UTC atau Asia/Jakarta;
  jika WIB, konversi hanya bagian representasi sesuai kebijakan, pertahankan
  timestamp/keunikan, dan uji pergantian bulan pukul 00:00-06:59 WIB.
  Perbedaan zona waktu bukan cacat bila format UTC memang disepakati.
- [ ] Selaraskan aktivasi akun pending dari RT/superadmin: notifikasi, audit,
  dan pencabutan sesi sesuai transisi; jangan mengirim notifikasi duplikat
  pada toggle yang tidak merupakan verifikasi warga.
- [ ] Tangani perubahan role/wilayah/status petugas yang masih ditugaskan:
  tentukan reassignment/penanda butuh tindak lanjut, cek eligibility sebelum
  mutasi tiket, dan pertahankan histori. Jangan menghapus penugasan lama
  tanpa keputusan agar tampilan seolah konsisten.
- [ ] Tambahkan pencarian nama/email yang scoped dan terpaginasikan pada akun/
  verifikasi warga jika diperlukan; pertahankan filter/tab/halaman valid
  setelah aksi tanpa membawa redirect atau parameter tidak aman.
- [ ] Tambah bantuan lupa password/kontak yang sesuai SOP PR-07 pada login;
  tidak perlu membangun email reset mandiri baru untuk meluluskan MVP.
- [ ] Pada DB tanpa RW/RT, tampilkan petunjuk setup yang aman dan hentikan
  registrasi yang mustahil dengan pesan jelas; jangan otomatis men-seed data
  demo atau memberi akses admin kepada pengunjung.

**Lulus:** role/wilayah/penugasan tidak membuat akses atau status menyesatkan,
notifikasi mencerminkan transisi sebenarnya, format tiket sesuai kebijakan,
serta pengurus/warga dapat menyelesaikan alur bantuan. Fitur search boleh
diprioritaskan dari hasil UAT, bukan dianggap celah keamanan dengan sendirinya.

**Bukti:** tes batas waktu, matriks transisi role/status/wilayah, uji scope,
skenario DB kosong, serta penerimaan alur harian pengurus.

### PR-24 - Bukti CI lengkap dan drift operasional terkendali

**Dasar SOURCE/HISTORICAL:** `.github/workflows/ci.yml` memakai MySQL 8.4,
audit runtime pada push/PR, dan belum menambahkan pemeriksaan schema/secret
yang diminta. Versi DB aktif, konfigurasi log, serta socket Gunicorn perlu
inventaris runtime terpisah; jangan menyimpulkan dari template/log lama saja.

- [ ] Tambah pemeriksaan model/migration drift, misalnya `flask db check`
  bila didukung versi tool, serta uji upgrade dari revision sebelumnya dan
  database kosong. CI harus memakai dependency terkunci dan database sintetis.
- [ ] Putuskan versi MySQL yang didukung berdasarkan inventaris aktual;
  selaraskan CI dengan produksi atau uji matriks versi yang memang didukung.
  Bedakan mismatch yang terlihat di artefak lama dari versi live terbaru.
- [ ] Tambah secret scan dan analisis statis terarah sesuai risiko; pilih
  alat seperti Ruff/Bandit atau setara tanpa reformat massal di luar scope.
  Temuan dibuktikan/ditriage, bukan dibungkam seluruh kategorinya.
- [ ] Lengkapi audit terjadwal kedua lock dan penyimpanan artifact PR-04/15;
  hasil gagal harus dikirim ke pemilik. Retensi artifact tidak boleh
  mempublikasikan env, SQL, cookie, atau foto warga.
- [ ] Inventaris profiling, journald/logrotate, batas disk/retensi, dan volume
  log telemetry/audit. Pastikan pengurangan log tetap menjaga bukti insiden;
  pengaturan host dapat berada di luar repo dan perlu diverifikasi.
- [ ] Inventaris control socket Gunicorn yang tercatat di log lama: versi,
  kebutuhan, owner/mode, dan akses. Nonaktifkan jika tidak dipakai dan opsi
  versi terpasang mendukung `control_socket_disable`; bila dipakai, batasi
  hak dan dokumentasikan. Tidak ada klaim socket lokal otomatis terekspos web.
- [ ] Ikat seluruh bukti ke SHA, dependency, schema, dan konfigurasi release.
  Smoke autentikasi setelah cutover belum dibuktikan oleh GET anonim; lakukan
  di staging, atau gunakan akun/skenario live yang diotorisasi terpisah,
  tanpa memodifikasi laporan warga sebagai bahan tes.

**Lulus:** schema, toolchain, dukungan versi DB, akses rahasia/socket, dan
retensi log diketahui serta diuji; tidak ada asumsi "repo punya konfigurasi"
sama dengan "service memakai konfigurasi itu". CI tidak men-deploy otomatis
hanya karena jadwal audit, dan tidak mengklaim seluruh runtime aman dari SAST.

**Bukti:** konfigurasi/matriks CI, hasil schema/secret/static checks yang
disanitasi, inventaris versi/permission, artifact manifest, dan smoke report
dengan lingkungan serta otorisasi yang jelas.

## 5. Cakupan yang dilaporkan oleh audit masukan

Berikut ringkasan inventaris dari daftar `Ran`/`Analyzed` yang dikirim pengguna.
Rentang baris dalam laporan asal adalah referensi versi saat itu, bukan bukti
bahwa tiap baris/artefak diuji ulang atau masih identik pada rilis mendatang.

| Kelompok | Berkas/aktivitas yang disebut dalam laporan masukan |
| --- | --- |
| Inventaris | Daftar root/file rekursif/source/config, git status/recent commits/diff, disk footprint, ukuran aset, direktori local/instance, nama key env tanpa nilai |
| Backend | `app/__init__.py`, `models.py`, `security.py`, `permissions.py`, `constants.py`, `observability.py`, `auth.py`, `routes.py`, `tickets.py`, `admin.py`, `forms.py`, `uploads.py`, `commands.py`, `image_variants.py`, `navigation.py`, `query_options.py`, `seed.py`, `run.py` |
| Schema/root | Dua migration revision `aaa123313203`/`bbb234424314`, migration `env.py`, `.env.example`, `.gitignore`, requirements/lockfiles, `ERD.md`, dan file SQL nyasar di root |
| Deploy generik | Nginx/log format, Gunicorn, systemd aplikasi/backup/timer, env aplikasi/backup, `backup.sh`, Prometheus/alerts/Alertmanager |
| Deploy lokal | Nginx HTTPS/pending, unit aplikasi/Redis/backup lokal/timer, wrapper backup/manage/activate HTTPS, `provision.py`, `bootstrap-admin.py`, `smoke.py` |
| UI | Base/components, dashboard/landing/error/notifikasi, auth login/register/account/waiting, pengaduan create/detail/index/upload, admin residents/regions/categories/users/user_fields/panel |
| Aset | `app.js`, `vitals.js`, style/layout/branding CSS, deklarasi inline style dan penggunaan variabel template |
| Otomasi/tes | Backup/load/smoke browser, CI, test release regressions/operational guards/hardening/auth, dependency audit dan load smoke |
| Bukti | Checks/readiness/service/restart/startup live, verification summary, local metrics, serta artefak historis pengujian |
| Dokumen | README, AUDIT-2026-10-27, OPERATIONS, TECHNICAL, EVIDENCE, PILOT, REQUIREMENTS, HTTP, VALIDATION, DEPLOYMENT_ELKYNO, RELEASE-2026-11-10 |

Inventaris ini membantu penelusuran cakupan, **bukan sertifikat audit total tanpa
celah**. Klaim pengujian aktif harus tetap disertai hasil, tanggal, lingkungan,
otorisasi, dan versi source seperti yang diwajibkan dokumen induk.

## 6. Referensi primer untuk keputusan yang mudah disalahartikan

Referensi berikut dibaca untuk memisahkan aturan platform dari asumsi laporan;
versi terpasang dan konfigurasi efektif tetap harus diuji saat implementasi.

- Nginx `add_header`, inheritance dan `always`:
  `https://nginx.org/en/docs/http/ngx_http_headers_module.html`.
- Nginx penanganan header upstream, termasuk `X-Accel-Redirect`:
  `https://nginx.org/en/docs/http/ngx_http_proxy_module.html`.
- python-dotenv, prioritas environment pada `load_dotenv(override=False)`:
  `https://bbc2.github.io/python-dotenv/`.
- W3C penjelasan resize teks hingga 200 persen tanpa kehilangan fungsi:
  `https://www.w3.org/WAI/WCAG22/Understanding/resize-text.html`.
- W3C penjelasan kontras minimum menurut kategori teks:
  `https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html`.

Penilaian UU No. 27 Tahun 2022 dan kewajiban lain bukan hasil dari referensi
teknis tersebut. Pengurus perlu menilai kewajiban yang berlaku dengan pihak
kompeten; jangan menyatakan kepatuhan atau pelanggaran hanya dari checkbox.
