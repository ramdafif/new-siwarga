# Form bukti capstone dan penerimaan

Status awal 10 November 2026: **template belum diisi, bukan hasil UAT/pilot**.
Gunakan bersama REQUIREMENTS, PILOT, OPERATIONS, dan checklist RELEASE.
Jangan mengubah kolom kosong menjadi klaim berhasil tanpa bukti nyata.
Simpan data pribadi, kontak peserta, dan persetujuan di penyimpanan terbatas,
bukan Git. Pakai kode peserta anonim dalam ringkasan laporan capstone.

## 1. Masalah nyata dan baseline

| Data yang harus dibuktikan | Isian / referensi bukti privat |
| --- | --- |
| RT/RW, tanggal observasi, proses saat ini | BELUM DIISI |
| Kode narasumber dan perannya, persetujuan | BELUM DIISI |
| Cara laporan masuk, diverifikasi, ditugaskan, ditutup | BELUM DIISI |
| Hambatan dan contoh dampaknya (tanpa PII) | BELUM DIISI |
| Jumlah laporan, periode, jumlah yang terlacak/selesai | BELUM DIISI |
| Waktu kirim -> verifikasi -> selesai pada proses lama | BELUM DIISI |
| Kebutuhan disepakati dan tautan ke ID SRS | BELUM DIISI |

Minimal cocokkan wawancara warga dan pengurus dengan observasi proses, bukan
hanya pendapat pengembang. Tuliskan keterbatasan, laporan yang hilang, serta
perbedaan beban/kompleksitas saat membandingkan sebelum dan sesudah.

## 2. UAT per role di staging sintetis

Catat commit, perangkat/browser, profil jaringan, tanggal, moderator, dan kode
peserta. Jangan memakai akun bersama atau membagikan password demo live.

| ID | Role / skenario | Hasil yang diharapkan | Aktual, durasi, bantuan, bukti | Keputusan |
| --- | --- | --- | --- | --- |
| UAT-01 | WARGA daftar dan pilih RT/RW | Pending sampai RT yang tepat memverifikasi | BELUM DIUJI | BELUM |
| UAT-02 | RT verifikasi warga | Hanya warga RT/RW sendiri dapat diaktifkan | BELUM DIUJI | BELUM |
| UAT-03 | WARGA buat laporan dan foto | Nomor tiket, foto privat, status menunggu | BELUM DIUJI | BELUM |
| UAT-04 | WARGA retry formulir saat jaringan putus | Tidak ada laporan ganda untuk token sama | BELUM DIUJI | BELUM |
| UAT-05 | RT terima/tolak | Status sesuai aksi dan alasan penolakan tercatat | BELUM DIUJI | BELUM |
| UAT-06 | RT/RW menugaskan petugas | Hanya petugas aktif RW yang sama | BELUM DIUJI | BELUM |
| UAT-07 | KARANG_TARUNA progres dan pergantian petugas | Tugas baru terlihat; akses lama dicabut, notifikasi aman | BELUM DIUJI | BELUM |
| UAT-08 | RT/RW selesai, WARGA cek hasil | Riwayat, foto, dan notifikasi sesuai laporan | BELUM DIUJI | BELUM |
| UAT-09 | Salah wilayah/ID foto atau laporan pengguna lain | Ditolak tanpa bocor isi/PII | BELUM DIUJI | BELUM |
| UAT-10 | SUPERADMIN akun duplikat dan nomor 001/01 | Konflik aman, tidak ada data parsial | BELUM DIUJI | BELUM |
| UAT-11 | Password sementara, ganti/reset, logout | Sesi lama ditolak; logout mengeluarkan semua perangkat | BELUM DIUJI | BELUM |
| UAT-12 | HP kecil dan koneksi lambat, invalid foto/filter | Loading/interaksi terbaca, pesan validasi jelas | BELUM DIUJI | BELUM |

Per bug: ID, severity, langkah reproduksi, harapan/aktual, commit perbaikan,
hasil retest oleh peserta, keputusan pengurus. Lulus automated test bukan
pengganti penerimaan pengguna. Simpan tanggapan yang negatif juga.

## 3. Dampak terukur

| Indikator | Rumus / unit | Baseline (n, periode) | Pilot (n, periode) | Perubahan dan batas |
| --- | --- | --- | --- | --- |
| Waktu verifikasi | Median dan p95 menit dari kirim ke verifikasi | BELUM | BELUM | BELUM |
| Waktu penanganan | Median dan p95 jam sampai selesai; laporkan tiket terbuka terpisah | BELUM | BELUM | BELUM |
| Ketertelusuran | Laporan dengan status dan penanggung jawab / laporan masuk | BELUM | BELUM | BELUM |
| Keberhasilan tugas | Tugas selesai tanpa bantuan / semua percobaan UAT | BELUM | BELUM | BELUM |
| Pengalaman peserta | Skala yang konsisten, n respons, komentar anonim | BELUM | BELUM | BELUM |
| Kualitas dan keamanan | Bug menurut severity, retest akses antarwilayah | BELUM | BELUM | BELUM |
| Performa dan keandalan | p95, 5xx, throughput, CPU/RAM, payload, durasi/profil beban | BELUM | BELUM | BELUM |

Gunakan definisi dan periode yang sama; median saja tidak menunjukkan ekor
latency. Persentase peningkatan waktu = (baseline - pilot) / baseline x 100%,
hanya bila baseline >0 dan sampel dapat dibandingkan. Laporkan n, pengecualian,
kasus belum selesai, dan bias peserta; jangan mengubah benchmark sintetis
menjadi klaim peningkatan layanan warga.

## 4. Serah terima dan keputusan

- Penerimaan: tanggal, perwakilan warga/RT/RW/petugas, hasil skenario, bug
  tersisa dan penerimaan risikonya. Status awal: BELUM DITANDATANGANI.
- Operasional: operator utama/cadangan mendemonstrasikan backup offsite,
  restore baru + foto/login, dan penerimaan alert nyata. Catat RPO/RTO aktual,
  bukan hanya target. Status awal: BELUM DIBUKTIKAN.
- Privasi: tujuan/kategori data, akses, retensi, koreksi/penghapusan, backup,
  persetujuan, kontak bantuan, kepemilikan domain/server dan biaya.
- Keputusan demo data sintetis, pilot terbatas, atau perluasan harus terpisah;
  lampirkan commit/artifact yang benar-benar diuji dan penanggung jawab risiko.
