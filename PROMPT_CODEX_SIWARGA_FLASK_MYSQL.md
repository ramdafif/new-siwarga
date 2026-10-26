# PROMPT CODEX — SiWarga Capstone (Python Flask + MySQL)

Kamu adalah senior Python Flask developer. Kerjakan aplikasi web **SiWarga — Sistem Informasi Pengaduan Masyarakat RT/RW** sebagai capstone mahasiswa Sistem Informasi. Hasil wajib **berjalan dari awal sampai akhir**, mudah dipahami mahasiswa, dengan UI modern, bahasa Indonesia, dan MySQL. Jangan overengineering dan jangan mengklaim fitur sudah selesai jika belum diuji.

## 1. Batasan stack dan kualitas
- Backend: Python 3.11+ dan Flask (server-rendered), Jinja2, Flask-Login, Flask-SQLAlchemy, Flask-Migrate, Flask-WTF/CSRF, PyMySQL, Werkzeug password hashing, python-dotenv.
- Database: **MySQL 8**; buat migrasi Alembic/Flask-Migrate. Jangan SQLite sebagai database utama, jangan PostgreSQL.
- Frontend: HTML biasa + CSS responsif + JavaScript vanilla seperlunya; Bootstrap 5 boleh dipakai, ditambah CSS custom. Desain **mobile-first**, profesional tetapi simpel. Jangan React, Vue, Next.js, SPA, microservices, Docker/Kubernetes, machine learning, atau integrasi eksternal berbayar.
- Struktur proyek sederhana; pakai app factory bila membantu, blueprint jika memang perlu, tidak perlu repository/service layer berlebihan. Berikan komentar kode singkat di bagian yang tidak intuitif.
- Nama database default `siwarga_db`; seluruh variabel rahasia melalui `.env` dan `.env.example`. Jangan menyimpan password dalam plaintext.

## 2. Tujuan dan ruang lingkup
Sistem membantu warga membuat pengaduan fasilitas umum/lingkungan, pengurus RT melakukan verifikasi, RW memantau pengaduan di wilayahnya, dan **Karang Taruna membantu menangani pengaduan bila ditugaskan** oleh RT/RW. Sistem bisa menyimpan beberapa RW dan RT, tetapi seed/demo cukup satu RW dan dua RT.

Contoh kategori: Jalan & Infrastruktur; Sampah & Kebersihan; Drainase; Penerangan Jalan; Fasilitas Umum; Lainnya.

## 3. Lima role dan akses wajib
1. `SUPERADMIN`: kelola RW/RT, kategori, akun pengurus RW/RT/Karang Taruna, aktif/nonaktif akun, pantau semua pengaduan dan statistik; bukan pelaksana biasa.
2. `RW`: lihat semua pengaduan **dalam RW miliknya**; pantau status, bantu tindak lanjut, tugaskan anggota Karang Taruna satu RW, dan tandai selesai. Tidak bisa mengakses RW lain.
3. `RT`: verifikasi akun warga RT-nya; lihat dan verifikasi pengaduan **RT sendiri** (terima/tolak dengan alasan); catat tindak lanjut, tugaskan Karang Taruna dalam RW yang sama, dan tandai selesai.
4. `KARANG_TARUNA`: anggota Karang Taruna terikat ke **satu RW**; hanya melihat **pengaduan yang ditugaskan kepadanya**, menambah progres/catatan serta foto bukti. **Tidak boleh** verifikasi warga, menerima/menolak pengaduan, mengubah data wilayah/pengurus, atau menandai pengaduan selesai.
5. `WARGA`: registrasi mandiri dengan memilih RW dan RT, status akun `PENDING`; setelah RT memverifikasi akun menjadi `ACTIVE`, warga dapat membuat pengaduan, mengunggah foto, melihat status/riwayat, memberi komentar, dan melihat notifikasi **milik sendiri**.

**Aturan wilayah penting**: `users.rw_id` wajib untuk semua selain SUPERADMIN; `users.rt_id` wajib untuk WARGA dan RT, nullable untuk RW dan KARANG_TARUNA. Pastikan `users.rt_id` yang dipilih memang berada dalam `users.rw_id`. Penyaringan scope dan izin **wajib di backend pada tiap query/action**, bukan hanya menyembunyikan tombol.

## 4. Alur bisnis sederhana, tidak perlu proses rumit
A. SUPERADMIN membuat data RW, RT, akun Ketua RW, Ketua RT, dan anggota Karang Taruna (password awal di-set aman; dipaksa ganti saat login pertama bila mudah). 
B. WARGA mendaftar dengan nama, email, nomor HP (opsional), password, RW, dan RT. Akun menunggu persetujuan RT. Jangan minta NIK atau foto KTP di MVP.
C. RT memverifikasi akun warga RT-nya. Warga ACTIVE login dan mengajukan laporan: judul, kategori, deskripsi, lokasi teks, maksimal 3 foto JPG/PNG/WebP per pengaduan, masing-masing maksimal 3 MB.
D. Sistem membuat `nomor_tiket` unik (`SW-YYYYMM-XXXXXX` atau format sebanding), status `MENUNGGU_VERIFIKASI`, tanggal otomatis, dan riwayat status.
E. RT menerima pengaduan -> status `DIPROSES`; atau menolak -> `DITOLAK` dengan alasan yang wajib. RT/RW dapat mencatat tindak lanjut dan menugaskan 1 anggota KARANG_TARUNA dalam RW yang sama saat status DIPROSES.
F. Karang Taruna hanya melihat tiket assigned dan menambahkan catatan progres + foto jika perlu. RT/RW melihat progres dan boleh menandai tiket `SELESAI` dengan catatan penyelesaian. Karang Taruna tidak dapat mengubah status final.
G. Warga melihat timeline dan dapat menambahkan komentar; pemberitahuan tampil di inbox notifikasi internal. Tidak perlu email/SMS/WhatsApp/push.

State machine minimal: `MENUNGGU_VERIFIKASI` -> `DIPROSES` atau `DITOLAK`; `DIPROSES` -> `SELESAI`. Tolak perubahan status ilegal. Tiket selesai/ditolak tidak dapat diedit sembarangan. Semuanya tulis audit pada `riwayat_status`.

## 5. ERD MySQL — 10 tabel inti (gunakan nama tepat ini)
1. `rw`: `id` PK, `nomor` VARCHAR, `nama_wilayah` VARCHAR, `created_at` DATETIME.
2. `rt`: `id` PK, `rw_id` FK -> rw.id, `nomor` VARCHAR, `created_at`; UNIQUE(`rw_id`,`nomor`).
3. `users`: `id` PK, `rw_id` FK nullable -> rw.id, `rt_id` FK nullable -> rt.id, `nama`, `email` UNIQUE, `no_hp` nullable, `password_hash`, `role` (SUPERADMIN/RW/RT/KARANG_TARUNA/WARGA), `status` (PENDING/ACTIVE/INACTIVE), `created_at`.
4. `kategori_pengaduan`: `id` PK, `nama` UNIQUE, `deskripsi` nullable, `aktif` BOOL.
5. `pengaduan`: `id` PK, `nomor_tiket` UNIQUE, `pelapor_id` FK -> users.id, `rt_id` FK -> rt.id, `kategori_id` FK -> kategori_pengaduan.id, `ditugaskan_ke_id` FK nullable -> users.id, `judul`, `deskripsi`, `lokasi_teks`, `status`, `alasan_penolakan` nullable, `created_at`, `updated_at`, `selesai_at` nullable.
6. `lampiran`: `id` PK, `pengaduan_id` FK -> pengaduan.id, `uploader_id` FK -> users.id, `nama_asli`, `nama_tersimpan`, `jenis` (LAPORAN/PROGRES/PENYELESAIAN), `created_at`.
7. `tindak_lanjut`: `id` PK, `pengaduan_id` FK -> pengaduan.id, `petugas_id` FK -> users.id, `catatan`, `created_at`.
8. `riwayat_status`: `id` PK, `pengaduan_id` FK -> pengaduan.id, `aktor_id` FK -> users.id, `status_lama` nullable, `status_baru`, `catatan` nullable, `created_at`.
9. `komentar`: `id` PK, `pengaduan_id` FK -> pengaduan.id, `user_id` FK -> users.id, `isi`, `created_at`.
10. `notifikasi`: `id` PK, `user_id` FK -> users.id, `pengaduan_id` FK nullable -> pengaduan.id, `pesan`, `sudah_dibaca` BOOL, `created_at`.

Buat relasi SQLAlchemy, FK/index untuk scope dan status (`rt_id`, `pelapor_id`, `status`, `created_at`, `ditugaskan_ke_id`), NOT NULL sesuai aturan, constraint email/tiket unique, dan hubungan pengaduan ke user yang berbeda (pelapor/assignee) dengan `foreign_keys` eksplisit agar tidak ambigu. Jangan menambah tabel yang tidak perlu.

## 6. Halaman minimal yang benar-benar dapat digunakan
- Halaman publik landing/beranda, login, registrasi warga, status akun menunggu persetujuan.
- Dashboard terpisah berdasarkan peran, dengan angka yang **diquery dari DB**, bukan data mock permanen.
- WARGA: daftar pengaduan saya, tambah pengaduan dengan upload foto, detail/status + timeline + komentar, notifikasi.
- RT: daftar warga pending + terima/nonaktifkan bila perlu, daftar tiket wilayah, verifikasi tiket, assign Karang Taruna, tindak lanjut, selesai.
- RW: overview tiket dalam RW, filter RT/status, assign Karang Taruna, tindak lanjut dan selesai.
- KARANG_TARUNA: tiket tugas saya, detail tiket dan form catatan progres + upload bukti.
- SUPERADMIN: kelola RW, RT, kategori, dan akun pengurus; dashboard global.
- UI berbahasa Indonesia, layout jelas; warna navy, biru terang, hijau mint, latar putih; sidebar desktop dan navigasi ringkas mobile. Sediakan empty state, validasi, notifikasi sukses/error, dan tabel responsif.

## 7. Route Flask minimal
`GET /`, `GET/POST /register`, `GET/POST /login`, `POST /logout`, `GET /dashboard`.
`GET /pengaduan`, `GET /pengaduan/baru`, `POST /pengaduan`, `GET /pengaduan/<int:id>`.
`POST /pengaduan/<int:id>/verifikasi`, `POST /pengaduan/<int:id>/tugaskan`, `POST /pengaduan/<int:id>/tindak-lanjut`, `POST /pengaduan/<int:id>/selesai`, `POST /pengaduan/<int:id>/komentar`.
`GET /notifikasi`, `POST /notifikasi/<int:id>/baca`.
`GET /admin/wilayah`, route POST seperlunya untuk CRUD wilayah/kategori/pengurus, `GET /rt/verifikasi-warga`, `POST /rt/verifikasi-warga/<int:id>`.
`GET /lampiran/<int:id>` mengirim file **hanya setelah izin mengakses tiket dicek** (jangan simpan foto sensitif di folder publik `/static`).
Nama route tambahan boleh asal konsisten. Ini web server-rendered, **tidak perlu API JSON eksternal**.

## 8. Keamanan dan kualitas praktis
- `SECRET_KEY` wajib dari env, password `generate_password_hash`/`check_password_hash`; CSRF pada semua POST; batasi percobaan login sederhana; validasi input server-side; parameter ORM, jangan raw SQL terinterpolasi.
- Upload maksimal 3 MB/file, total maksimal 3 foto untuk laporan; cek ekstensi dan tipe konten secara masuk akal, nama file acak UUID, cegah traversal, akses melalui route berizin.
- Segala aksi RT/RW/Karang Taruna harus terikat wilayah/penugasan, termasuk akses langsung ke URL detail. Warga hanya boleh membaca laporan sendiri; superadmin global.
- Catat perubahan status dan aktor. Jika transaksi berisi operasi terkait (status + audit + notifikasi) lakukan commit atomik.
- Halaman error 403/404/500 informatif. Periksa potensi N+1 seperlunya. Sediakan pencarian/filter status, kategori, dan tanggal sederhana.
- Jangan mengklaim fitur real-time, integrasi instansi pemerintah, atau kesiapan produksi tanpa implementasi nyata. Tidak perlu peta/GPS, AI, email, WA, KTP, tanda tangan digital atau payment.

## 9. Struktur contoh (boleh disederhanakan)
```
siwarga/
  app/
    __init__.py
    models.py
    auth.py
    routes.py
    permissions.py
    forms.py
    templates/
      base.html
      auth/
      warga/
      rt/
      rw/
      karang_taruna/
      admin/
      pengaduan/
    static/css/style.css
  migrations/
  tests/
  .env.example
  .gitignore
  requirements.txt
  run.py
  README.md
  ERD.md
```
Bila file `routes.py` terlalu panjang, pecah menjadi blueprint per modul. Jangan membuat puluhan file kosong atau framework internal.

## 10. Data seed, setup, dan tes wajib
- Buat perintah `flask --app run.py seed-demo` yang idempotent untuk 1 RW, 2 RT, kategori dan masing-masing 1 akun SUPERADMIN, RW, RT, KARANG_TARUNA, WARGA ACTIVE; serta contoh tiket yang realistis. Password demo diset lewat env `DEMO_PASSWORD` (dev only), tidak hardcoded di production. Dokumentasikan email demo dan cara reset database lokal.
- `README.md` berisi syarat instalasi Python/MySQL, pembuatan venv, `pip install -r requirements.txt`, konfigurasi `.env`, `CREATE DATABASE siwarga_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci`, `flask --app run.py db upgrade`, seed, `flask --app run.py run --debug`, dan alur uji tiap role.
- `ERD.md` menjelaskan semua tabel, PK/FK, relasi 1:N dan alasan desain sederhana.
- Buat tes pytest untuk: password/login, isolasi tiket warga, isolasi RT/RW, Karang Taruna tidak boleh melihat tiket yang tidak ditugaskan serta tidak boleh menutup tiket, perubahan status ilegal ditolak, CSRF/otorisasi aksi penting, dan upload invalid ditolak. Bila MySQL test DB belum tersedia, gunakan konfigurasi DB khusus test dan dokumentasikan cara menjalankannya, jangan mengaku tes lulus tanpa menjalankannya.

## 11. Cara kerja yang diminta kepada Codex
1. Periksa direktori/repository aktif lebih dulu. Jangan menimpa pekerjaan user tanpa izin. Bila proyek sudah ada, sesuaikan dengan basis kode terbaru, usahakan reuse dan migrasi aman.
2. Tuliskan rencana implementasi singkat, lalu implementasikan **MVP paling kecil yang benar-benar terhubung ke MySQL**. Tidak boleh menggunakan data hardcoded untuk alur utama.
3. Jalankan pengecekan sintaks/tes dan perbaiki error yang ditemukan. Jelaskan jika tidak dapat menjalankan tes karena MySQL/env belum tersedia.
4. Pada akhir pekerjaan laporkan file yang dibuat/diubah, migrasi yang harus dijalankan, fitur yang benar-benar berfungsi, batasan yang tersisa, dan langkah demo lima role.
5. **Jangan push/deploy** atau menyentuh proyek lain tanpa instruksi.

## Kriteria selesai (acceptance demo)
- Superadmin login lalu membuat RW, RT, dan akun pengurus.
- Warga registrasi, RT memverifikasi akun, warga bisa login.
- Warga membuat tiket + foto dan memperoleh nomor tiket.
- RT memverifikasi laporan, mengubah status menjadi DIPROSES, lalu menugaskan Karang Taruna.
- Karang Taruna hanya melihat tugasnya dan mengisi progres.
- RW melihat progres di wilayahnya, RT/RW menandai selesai, warga bisa memantau timeline/notifikasi.
- Pengguna tidak bisa membaca/mengubah laporan di luar hak aksesnya.
- Semua data tetap tersimpan di MySQL setelah restart aplikasi.

**Utamakan tugas capstone selesai dan bisa didemokan.** Jangan menambahkan fitur 'keren' yang tidak diperlukan sebelum semua acceptance demo berjalan.
