# SiWarga

Sistem Informasi Pengaduan Masyarakat RT/RW. Aplikasi capstone berbahasa
Indonesia dengan Flask server-rendered, Jinja, CSS responsif, JavaScript vanilla,
dan **MySQL 8**. Tidak menggunakan React, API eksternal berbayar, atau SQLite.

## Menjalankan hasil yang sudah disiapkan di komputer ini

Proyek ini dilengkapi virtual environment, konfigurasi lokal, migrasi, data
demo, dan MySQL 8 portabel di folder `.local` yang diabaikan Git. Database lokal
menggunakan `127.0.0.1:13308`, terpisah dari server database lain di komputer ini.

~~~powershell
cd D:/Projects/Capstone
./start.ps1
~~~

Buka `http://127.0.0.1:5000`. Jika port tersebut digunakan, jalankan
`./start.ps1 -Port 5055`. Tambahkan `-Seed` untuk menjalankan seed idempotent,
atau `-DebugMode` untuk pengembangan. Hentikan Flask dengan Ctrl+C; MySQL lokal
tetap berjalan dan datanya tetap disimpan. Skrip tidak mengubah layanan MySQL
atau MariaDB lain dan tidak mereset database.

Untuk pengembangan sehari-hari, gunakan `./start.ps1 -DebugMode`. Jika ingin
memastikan akun dan data demo tersedia, jalankan `./start.ps1 -Seed -DebugMode`.
Password akun demo mengikuti `DEMO_PASSWORD` pada `.env` lokal Anda.
Tidak perlu menjalankan npm atau mengaktifkan virtual environment secara
manual: `start.ps1` sudah memakai Python dari `.venv` proyek.

Jika PowerShell menolak skrip karena execution policy, jalankan perintah ini
untuk proses tersebut saja, tanpa mengubah kebijakan PowerShell permanen:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1 -DebugMode
~~~

Jika tampilan lama masih tersimpan di browser, lakukan hard refresh dengan
Ctrl+F5 setelah aplikasi berjalan.

## Identitas visual

Tampilan menggunakan warna biru, teal, dan hijau dari
`app/static/branding/SiWarga-Logo.png`. Logo asli tidak diubah;
`SiWarga-Mark.webp` dan `SiWarga-Icon.png` adalah turunan simbol untuk navigasi
dan favicon, dengan latar transparan dan ukuran lebih ringan.

Token warna dan penyempurnaan komponen ada di `app/static/css/branding.css`,
yang dimuat setelah stylesheet struktur/responsif. Tema berlaku pada landing,
autentikasi, dashboard semua role, pengaduan, notifikasi, dan administrasi.
Amber/merah tetap dipakai untuk status menunggu, peringatan, dan penolakan.
Font Plus Jakarta Sans tetap disajikan lokal; tidak ada dependensi CDN baru.

## Instalasi dari awal

Prasyarat: Python 3.11+, MySQL 8.0/8.4 yang sudah berjalan, dan akses untuk
membuat database. Instruksi berikut memakai PowerShell; di Linux/macOS gunakan
`python3` dan `source .venv/bin/activate` untuk aktivasi.

~~~powershell
python -m venv .venv
./.venv/Scripts/Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
~~~

Masukkan hasil terakhir sebagai `SECRET_KEY` di `.env`. Atur `DATABASE_URL`
sesuai kredensial MySQL lokal. Driver harus `mysql+pymysql`, bukan SQLite.
Karakter khusus pada username/password URL harus di-URL-encode.

Di konsol MySQL milik instalasi Anda, buat database dan pengguna aplikasi.
Ganti password contoh sebelum menjalankan SQL:

~~~sql
CREATE DATABASE siwarga_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'siwarga'@'localhost' IDENTIFIED BY 'GANTI_DENGAN_PASSWORD_ACAK';
GRANT ALL PRIVILEGES ON siwarga_db.* TO 'siwarga'@'localhost';
~~~

Contoh konfigurasi (bukan kredensial siap pakai):

~~~dotenv
SECRET_KEY=ISI_DENGAN_RAHASIA_ACAK_MINIMAL_32_KARAKTER
DATABASE_URL=mysql+pymysql://siwarga:PASSWORD_ANDA@127.0.0.1:3306/siwarga_db?charset=utf8mb4
DEMO_PASSWORD=ISI_PASSWORD_DEMO_MINIMAL_10_KARAKTER
SESSION_COOKIE_SECURE=false
~~~

Pastikan host akun MySQL cocok dengan koneksi Anda: beberapa instalasi
memerlukan pengguna `'siwarga'@'127.0.0.1'`, bukan `'localhost'`.

~~~powershell
flask --app run.py db upgrade
flask --app run.py seed-demo
flask --app run.py run --debug
~~~

`SECRET_KEY` wajib diisi; aplikasi menolak secret kosong atau placeholder.
Jangan mengaktifkan debug pada jaringan publik. `DEMO_PASSWORD` hanya untuk
seed pengembangan. Semua password akun disimpan sebagai hash Werkzeug.

## Akun demo dan alur lima role

Semua akun seed menggunakan **nilai `DEMO_PASSWORD` di `.env`**, bukan password
yang ditulis di source code. Seed tidak mengubah password/status/data yang
sudah ada. Akun pengurus yang dibuat lewat UI wajib mengganti kata sandi awal;
akun seed tidak dipaksa mengganti agar mudah dipakai berulang untuk demo.

1. **SUPERADMIN:** `admin@siwarga.id`. Buka Kelola wilayah untuk membuat RW/RT,
   Pengurus & akun untuk membuat RW/RT/Karang Taruna, dan Kategori pengaduan.
   Admin dapat melihat seluruh tiket tetapi bukan pelaksana verifikasi/progres.
2. **WARGA:** `warga@siwarga.id` (RT 01/RW 05). Buat pengaduan, pilih kategori,
   isi lokasi dan deskripsi, unggah foto, lalu catat nomor tiket. Atau daftar
   akun baru melalui `/register`; akun baru menunggu persetujuan RT.
3. **RT:** `rt@siwarga.id`. Verifikasi warga baru melalui Verifikasi warga.
   Buka tiket tadi, terima laporan, lalu tugaskan `Rizky Ramadhan`.
   Akun `rt02@siwarga.id` hanya melihat RT 02 pada RW yang sama.
4. **KARANG_TARUNA:** `karangtaruna@siwarga.id`. Buka Tugas saya, tambahkan
   catatan progres dan foto bukti. Akun ini tidak dapat menerima/menolak
   laporan atau menandai pengaduan selesai.
5. **RW:** `rw@siwarga.id`. Pantau tiket RT 01/02 dalam RW 05, lihat progres,
   lalu konfirmasi selesai dengan catatan. Masuk kembali sebagai warga untuk
   melihat timeline, notifikasi, dan memberikan komentar.

Akun tambahan: `warga02@siwarga.id` di RT 02, serta `pending@siwarga.id` yang
menunggu verifikasi RT 01. Seed menambahkan satu RW, dua RT, enam kategori,
delapan akun, dan sembilan contoh tiket beserta audit/progres/notifikasi.
Tiket seed memiliki awalan `SW-DEMO`; tiket baru memakai `SW-YYYYMM-<acak>`.

## Fitur dan aturan

- Dashboard menggunakan agregat MySQL sesuai pemilik, RT, RW, atau penugasan;
  grafik tujuh hari, daftar terbaru, dan aktivitas tidak memakai data mock.
- Daftar pengaduan memiliki pencarian judul/nomor, filter status, kategori,
  tanggal, RT untuk pengurus RW/admin, serta pagination.
- State machine: `MENUNGGU_VERIFIKASI -> DIPROSES -> SELESAI` atau
  `MENUNGGU_VERIFIKASI -> DITOLAK`. Perubahan ilegal menghasilkan HTTP 409.
- Hanya RT wilayah tiket yang menerima/menolak. RT/RW dapat menugaskan satu
  anggota Karang Taruna aktif dalam RW yang sama. Penugasan ulang mencabut
  akses petugas lama; anggota nonaktif tidak dapat masuk.
- Karang Taruna hanya mengakses tiket yang ditugaskan kepadanya dalam RW-nya.
  Warga hanya mengakses tiket/notifikasi sendiri. Semua izin diperiksa backend,
  termasuk URL langsung, unggahan, dan setiap POST.
- Maksimal tiga foto awal per tiket, masing-masing 3 MB. Catatan progres dan
  penyelesaian menerima maksimal tiga foto per pengiriman, juga 3 MB/foto.
  Ekstensi, MIME, format nyata dan resolusi diperiksa dengan Pillow; gambar
  ditulis ulang tanpa metadata sumber. Berkas rusak atau tidak cocok ditolak.
- Foto disimpan di `instance/uploads`, bukan `/static`; route `/lampiran/<id>`
  memeriksa akses tiket dan memberikan respons privat tanpa cache.
- Status, audit, dan notifikasi disimpan dalam satu transaksi. Foto yang sudah
  ditulis dibersihkan jika transaksi gagal. Mutasi tiket memakai row lock.
- Tiket selesai/ditolak tidak dapat dibuka ulang, diubah, ditugaskan, atau
  diberi progres baru; komentar tetap dapat ditambahkan sebagai diskusi.
- Admin dapat mengubah/menghapus wilayah dan kategori yang belum digunakan.
  Data yang sudah direferensikan dilindungi; kategori bisa dinonaktifkan dan
  akun dinonaktifkan, bukan dihapus, demi menjaga riwayat.
- Login dibatasi lima percobaan gagal per email dan 30 per IP selama 15 menit,
  dengan penyimpanan memori proses. Semua POST dilindungi CSRF.
- Waktu disimpan dalam UTC dan ditampilkan sebagai WIB. Aset font disimpan
  lokal sehingga UI tidak bergantung pada Google Fonts/CDN saat dibuka.

## Pengujian MySQL

**Gunakan database khusus yang namanya berakhiran `_test`.** Fixture menghapus
data di database test sebelum setiap kasus, tetapi tidak menghapus database
aplikasi. Test menolak nama database yang sama dengan database aplikasi dan
menolak MariaDB/non-MySQL-8. Tidak ada fallback SQLite.

~~~sql
CREATE DATABASE siwarga_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'siwarga_test'@'localhost' IDENTIFIED BY 'PASSWORD_TEST_ACAK';
GRANT ALL PRIVILEGES ON siwarga_test.* TO 'siwarga_test'@'localhost';
~~~

Isi `TEST_DATABASE_URL` di `.env`, sesuai contoh berikut dengan password Anda:

~~~dotenv
TEST_DATABASE_URL=mysql+pymysql://siwarga_test:PASSWORD_TEST@127.0.0.1:3306/siwarga_test?charset=utf8mb4
~~~

~~~powershell
./.venv/Scripts/python.exe -m compileall -q app run.py tests scripts
./.venv/Scripts/python.exe -m pytest -q
flask --app run.py db check
~~~

Test memakai migrasi asli dan MySQL 8. Cakupan meliputi hashing/login,
registrasi dan verifikasi, isolasi warga/RT/RW, pembatasan Karang Taruna,
CSRF/otorisasi, state machine, admin CRUD, unggahan invalid, foto privat,
notifikasi personal, dan workflow warga -> RT -> Karang Taruna -> RW -> warga.
Jika `TEST_DATABASE_URL` belum diisi, tes integrasi **dilewati**, bukan dianggap
berhasil. Jika diisi tetapi server tidak tersedia, tes gagal secara eksplisit.

### Pemeriksaan browser opsional

Jalankan aplikasi dan seed terlebih dahulu. Chrome diperlukan untuk skrip ini.

~~~powershell
pip install -r requirements-dev.txt
python scripts/smoke_browser.py
~~~

Skrip memeriksa lima role, pemuatan logo/tema branding, JavaScript, navigasi
mobile, dan overflow halaman pada desktop 1440px, tablet 768px/820px/1024px,
serta mobile 390px dan 320px, termasuk pratinjau foto. Screenshot dan laporan disimpan di
`test-results/browser` (diabaikan Git). Skrip browser menggunakan akun demo dan
tidak membuat/mengubah pengaduan. Jangan jalankan pada server produksi.

## Struktur proyek

~~~text
app/
  __init__.py        Factory, konfigurasi, CSRF, session, error handler
  models.py         Sepuluh tabel inti dan relasi SQLAlchemy
  auth.py           Login, registrasi, status pending, ganti password
  permissions.py    Scope tiket dan pembatasan role
  tickets.py        Pengaduan, verifikasi, penugasan, progres, komentar
  uploads.py        Validasi dan penyimpanan foto privat
  routes.py         Landing, dashboard, notifikasi, verifikasi warga
  admin.py          Pengelolaan wilayah, kategori, dan akun
  seed.py           Perintah seed idempotent
  templates/        Jinja, shell, dan halaman role
  static/           CSS, JS vanilla, font, favicon
migrations/         Alembic / Flask-Migrate
tests/              Tes integrasi MySQL dengan pytest
scripts/            Pemeriksaan database dan browser, setup lokal satu kali
start.ps1           Menjalankan hasil lokal tanpa mengubah layanan lain
run.py              Entry point Flask
ERD.md              Relasi, PK/FK, dan alasan desain
~~~

## Reset database demo lokal

**Destruktif: hanya lakukan bila semua data demo boleh dihapus.** Hentikan
Flask terlebih dahulu, pastikan `DATABASE_URL` menunjuk `siwarga_db` lokal,
lalu pada konsol MySQL yang benar jalankan:

~~~sql
DROP DATABASE siwarga_db;
CREATE DATABASE siwarga_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
~~~

Kemudian jalankan `flask --app run.py db upgrade` dan
`flask --app run.py seed-demo`. Bersihkan foto lama di `instance/uploads`
secara manual hanya jika yakin tidak ada laporan yang masih menggunakannya.
Untuk MySQL portabel proyek ini, kredensial administratif disimpan di
`.local/mysql.env`; jangan memakainya pada server lain atau memasukkannya Git.

## Batasan yang disengaja

Ini MVP capstone untuk demo lokal, **bukan klaim siap produksi**. Tidak ada
email/SMS/WhatsApp/push, fitur real-time, peta/GPS, NIK/KTP, integrasi pemerintah,
atau reset password melalui email. Notifikasi diperbarui saat halaman dimuat.
Reset password dilakukan admin. Rate limit masih per proses dan hilang saat
restart; belum ada antivirus, penyimpanan objek, audit login, atau backup
otomatis. Row lock melindungi mutasi status, tetapi server Flask bawaan bukan
server deployment produksi. Sebelum penggunaan publik diperlukan HTTPS,
`SESSION_COOKIE_SECURE=true`, server WSGI, rate limit bersama, backup, dan
peninjauan keamanan/operasional lanjutan.
