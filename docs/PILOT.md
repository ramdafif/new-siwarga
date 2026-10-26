# Pilot dan penerimaan satu RT

## Peserta dan pengelola

Usulan awal pilot berlangsung 1-2 minggu dengan 10-20 warga dalam satu RT.
Durasi dan peserta dikonfirmasi bersama pengurus sebelum mulai. Tunjuk pengurus RT,
koordinator RW, petugas Karang Taruna, admin utama dan admin cadangan individual.
Jangan menggunakan akun bersama atau akun demo pada pemakaian resmi.

Sebelum mulai, isi dan sepakati: RW/RT peserta, penanggung jawab tiap tahap,
jam pemeriksaan notifikasi, waktu respons/verifikasi yang disepakati, eskalasi
laporan terlambat, kontak bantuan, serta proses verifikasi identitas tanpa NIK/KTP.
Notifikasi warga tetap hanya dalam aplikasi; tidak ada WhatsApp/email/push baru.

## Panduan warga

1. Daftar dengan email, password, dan RT/RW yang benar; tunggu verifikasi RT.
2. Login, buat pengaduan dengan lokasi/deskripsi jelas dan maksimal tiga foto.
3. Setelah submit, catat nomor tiket. Jika koneksi terputus, retry formulir yang
   sama aman; formulir baru berarti pengaduan baru, bukan pembaruan tiket lama.
4. Periksa dashboard/notifikasi dan detail tiket; tambahkan komentar bila perlu.
5. Buka foto untuk ukuran penuh hanya saat diperlukan. Jangan membagikan akun
   atau mengunggah data pribadi orang lain yang tidak diperlukan penanganan.

## Panduan pengurus

1. RT memverifikasi warga wilayahnya berdasarkan prosedur offline yang disepakati.
2. RT menerima/menolak laporan disertai catatan; RT/RW menugaskan petugas aktif.
3. Petugas mencatat progres dan bukti. Penyelesaian mengikuti alur dan peran
   aplikasi yang sudah ada; tidak mengubah status lewat database manual.
4. Periksa notifikasi sesuai jadwal dan tindak lanjuti laporan yang melewati
   waktu respons. Catat alasan penundaan dan informasi yang diberikan ke warga.
5. Admin menangani reset password setelah pemeriksaan identitas; password
   sementara disampaikan lewat jalur privat dan wajib diganti pengguna.

## Bukti penerimaan

Uji daftar -> verifikasi -> laporan -> penugasan -> progres -> selesai pada HP
serta jaringan peserta. Sertakan salah wilayah, foto tidak valid, koneksi lambat,
retry, akun dinonaktifkan, pergantian petugas, dan bantuan reset password.

Catat waktu kirim/verifikasi/selesai, persentase tertangani, tugas berhasil tanpa
bantuan, masalah penggunaan, dan tanggapan peserta. Bandingkan dengan proses
sebelumnya sebelum mengklaim peningkatan. Jangan memasukkan nama, password,
nomor HP, atau isi laporan warga dalam artefak benchmark publik.

## Privasi, serah terima, dan keputusan perluasan

Sebelum data warga masuk, pengelola menandatangani pemberitahuan privasi:
tujuan/kategori data, pihak yang dapat mengakses, masa simpan, mekanisme koreksi/
penghapusan, kontak pengelola, serta perlakuan salinan backup. Pilot tidak
menghapus foto otomatis. Penghapusan fisik hanya melalui operator dengan
maintenance lock dan prosedur retensi yang disetujui; jangan membuat cron rm uploads.

Serah terima mencakup kepemilikan domain/server, biaya/perpanjangan, akun admin
cadangan, akses backup/kunci di luar server, rotasi rahasia, jadwal pemutakhiran,
dan latihan restore. Operator selain pembuat harus mendemonstrasikan runbook.

Perluasan ke seluruh RW memerlukan penerimaan UAT, tidak ada masalah kritis
terbuka, restore remote dan alert terbukti, serta uji server tujuan. Inventaris
jumlah warga/RT dan perkiraan puncak aktivitas, lalu uji setidaknya dua kali
perkiraan tersebut. Tes 50 sesi lokal bukan angka kapasitas seluruh RW.

Pada awal rilis, tinjau error, laporan tertunda, ruang foto, backup dan keluhan
setiap hari; lanjutkan laporan operasional mingguan setelah kondisi stabil.
Tetapkan ulang jadwal menurut hasil pilot, bukan tanggal peluncuran yang dipaksakan.
