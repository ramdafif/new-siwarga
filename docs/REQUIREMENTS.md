# Kebutuhan dan kriteria penerimaan

## Tujuan dan pengguna

SiWarga membantu warga satu RW mengirim dan memantau pengaduan, RT memverifikasi
warga/laporan, RW mengoordinasikan wilayah, Karang Taruna menangani tugas, dan
superadmin mengelola akun serta master data. Alur peran dan batas wilayah MVP
harus dipertahankan. Pilot dimulai dari satu RT sebelum perluasan satu RW.

## Kebutuhan fungsional

- RF-01: registrasi mandiri berstatus pending, verifikasi RT sesuai wilayah,
  login/logout, perubahan password dan reset oleh admin tanpa akun bersama.
- RF-02: laporan bertiket unik, lokasi/deskripsi/kategori, maksimal tiga foto
  opsional per pengiriman, serta retry formulir yang tidak menggandakan laporan.
- RF-03: daftar/filter/pagination, dashboard dan detail sesuai scope; alur
  verifikasi, penugasan, progres, penyelesaian/penolakan, komentar dan notifikasi.
- RF-04: original/thumbnail/display privat, validasi upload, pembersihan metadata,
  serta backfill foto lama tanpa melemahkan otorisasi.
- RF-05: audit autentikasi/perubahan akun, pencabutan sesi dan pembatasan login
  lintas-worker yang tetap melindungi sistem saat Redis tidak tersedia.
- RF-06: backup online database/foto yang konsisten, checksum, salinan remote,
  restore pada lingkungan baru, health/metrics dan alert operasional.

## Kebutuhan nonfungsional

Angka berikut merupakan usulan gate awal, bukan hasil produksi atau kesepakatan
pengurus yang sudah disahkan. Tetapkan beban dan persetujuan sebelum uji ulang.

- RNF-01: tidak ada kebocoran lintas pengguna/RT/RW, seluruh POST memakai CSRF,
  tidak ada password/cookie/token autentikasi dalam log atau artefak benchmark.
- RNF-02: rata-rata HTML <=300 ms, p95 GET utama <=1 detik, p95 POST laporan
  <=3 detik pada uji jaringan server; 5xx <0,1%. Hasil per endpoint/metode,
  penolakan yang diharapkan dan fault injection dilaporkan terpisah.
- RNF-03: halaman tiga foto transfer awal <=1 MB dan muat awal <=5 detik pada
  profil mobile terdokumentasi; seluruh foto setelah scroll juga selesai <=5 detik.
- RNF-04: CPU/memori/koneksi tidak tumbuh terus selama soak dua jam, disk bebas
  >=20%, dan kapasitas diputuskan dari uji server tujuan, bukan hasil lab saja.
- RNF-05: RPO <=24 jam, RTO <=4 jam; backup tanpa jeda layanan, diuji dengan
  upload bersamaan dan restore dari repository di luar server aplikasi.
- RNF-06: build/tes memakai dependency terkunci dan CI per commit; temuan
  dependency tidak diabaikan diam-diam. Panduan bisa dijalankan operator lain.

## Batas dan gate penerimaan

Tidak menambah NIK/KTP, peta, notifikasi eksternal, layanan berbayar aplikasi,
React, atau migrasi dari MySQL. Redis hanya wajib pada deployment multi-worker;
lokal boleh tetap memakai konfigurasi lama dengan peringatan eksplisit.

Kelulusan tes lokal tidak menandakan RF-06/RNF produksi telah terbukti. Gate
peluncuran adalah SOP dan kebijakan privasi/retensi disetujui, CI lulus, deployment
server tujuan lolos, alert diterima, restore remote tercatat, pilot 1-2 minggu
diterima, dan admin utama/cadangan serta biaya operasi sudah ditetapkan.
