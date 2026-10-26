# Validasi lokal 26 Oktober 2026

## Lingkungan dan batas

Implementasi berada di Capstone copy; checkout Capstone tidak diubah. .env lokal
identik dengan sumber. Database aplikasi memakai konfigurasi lokal yang sama,
dengan migrasi aditif bbb234424314 setelah dump pra-migrasi. Jalankan startup
hanya dari copy karena checkout lama tidak mengenal revision Alembic baru.

Pengujian otomatis memakai schema khusus berakhiran _test, bukan data aplikasi.
Benchmark memakai siwarga_benchmark_test, MySQL 8.4.13, Python 3.12, dan server
Werkzeug threaded lokal. Ini bukan bukti kapasitas Gunicorn/VPS produksi.
Artefak mentah di test-results diabaikan Git; arsipkan bersama commit rilis.

## Tes dan keamanan

- Baseline sebelum perubahan: 69 tes lulus.
- Suite akhir: 140 tes lulus, tanpa skip, 57,93 detik. Hasil JUnit:
  test-results/pytest.xml.
- Browser: lima role, 27 screenshot, tanpa error JavaScript atau overflow;
  test-results/browser/report.json.
- Audit runtime: 29 dependency, nol kerentanan dikenal pada saat audit;
  test-results/dependency-audit.json. Ini bukan jaminan tanpa kerentanan.
- compileall dan git diff --check lulus. YAML CI/monitoring berhasil diparse;
  deploy/backup.sh lolos bash -n. CI remote belum dijalankan.
- Redis lokal memakai fakeredis dan Lua; reservasi lintas-worker dan paralel,
  fail-closed, pencabutan sesi, rollback audit, akses wilayah/foto, upload dan
  transisi status paralel diuji. CI disiapkan memakai Redis nyata.

## Foto mobile sebelum dan sesudah

Tiga pengulangan per versi, cache mati, viewport 390x844, DPR 1, download
200.000 byte/detik, upload 93.750 byte/detik, latency 150 ms, CPU throttle 4x,
Chrome 156.0.8078.47. Dataset awal 10.009 laporan sintetis, dua RW; tiket 10
memiliki tiga foto dengan total original 3.512.060 byte.

- Median transfer seluruh halaman: 3.857.487 menjadi 481.249 byte.
- Median waktu sampai seluruh foto dimuat setelah scroll: 20.098,16 menjadi
  3.333,63 ms. Versi sesudah memenuhi usulan <=1 MB dan <=5 detik profil ini.
- Median transfer awal sesudah: 473.257 byte; load awal 2.770,50 ms.
- Artefak: test-results/benchmark/mobile-before.json dan mobile-after.json.
- Ini baseline ulang pada profil terdokumentasi, bukan perbandingan langsung
  terhadap angka audit lama 5,44 MB / 29,04 detik yang profilnya tidak tersedia.
  LCP/INP/CLS p75 lapangan belum terbukti dari uji ini.

## Profil query

Dua puluh sampel single-client per role dan endpoint, sebelum uji beban mutasi.
Jumlah median query daftar turun dari 13-14 menjadi 6; dashboard 15-17 menjadi
7-8. p95 daftar SUPERADMIN: 145,419 menjadi 20,553 ms; RT: 72,198 menjadi
16,835 ms; RW: 119,005 menjadi 20,272 ms; WARGA: 80,978 menjadi 38,870 ms.
Hasil lengkap dan EXPLAIN berada di test-results/benchmark/queries-before.json
dan queries-after.json. Pengurangan over-fetch menjadi perbaikan utama; tidak
ada indeks spekulatif. Hasil ini bukan p95 beban 50 sesi.

## Beban campuran dan konkurensi

Workload 70% baca, 20% komentar, 10% laporan dengan upload; pembacaan detail
juga mengambil tiga varian foto. Think time satu detik. Dataset bertambah selama
uji tulis; jangan memperlakukan pengulangan sebagai dataset yang identik.

Uji awal 50 sesi menemukan lima deadlock MySQL 1213 pada komentar. Penyebabnya
SELECT FOR UPDATE dengan eager join ikut mengunci parent RT/akun. Perbaikannya
mengunci hanya baris tiket sambil mempertahankan scope pada SELECT pengunci.
Regresi lima role memastikan kunci tiket tidak mengunci parent RT/akun.

Uji ulang 15 detik per tahap (1/10/25/50 sesi) mencatat 1.460 request, tanpa
respons tak terduga, 5xx, atau kegagalan jaringan. Di 50 sesi, p95 GET utama
1,54-1,95 detik dan POST upload 3,54 detik: gate latensi belum terpenuhi meski
gate error lulus. Artefak: test-results/benchmark/load-smoke.json.

Konfirmasi terpisah 30 detik per tahap (25/50 sesi), setelah suite selesai,
mencatat 2.410 request tambahan tanpa error. Pada 25 sesi, p95 daftar/dashboard/
detail 812/497/854 ms; upload 1.898 ms. Pada 50 sesi, p95 ketiga GET utama
sekitar 1.028-1.030 ms dan rata-rata 583-654 ms, masih melampaui usulan gate
GET 1 detik dan rata-rata HTML 300 ms. p95 upload 2.636 ms. Total kedua run
pascaperbaikan 3.870 request tanpa error, bukan klaim kapasitas produksi.
Artefak konfirmasi: test-results/benchmark/load-confirmation.json.

Uji ini singkat, bukan soak dua jam, bukan puncak kapasitas yang telah disahkan,
dan tidak membuktikan kestabilan CPU/memori/disk jangka panjang.

## Backup dan pemulihan

Drill MySQL lokal mengunggah foto sebelum snapshot dan foto lain sesudah dump.
Manifest hanya memuat foto snapshot; restore ke schema/folder kosong terpisah
berhasil, termasuk login serta akses original/display privat. Pada suite akhir,
backup 1,375 detik dan restore plus smoke 1,343 detik; satu lampiran snapshot.
Artefak: test-results/recovery-drill.json. Waktu ini bukan RTO produksi: tidak
termasuk penyediaan server, download remote, DNS, maupun pemulihan layanan.

## Gate yang masih terbuka

Domain/TLS, instalasi server kosong, Gunicorn/Redis nyata multi-worker, backup
SFTP/restic di luar server, penerimaan alert, soak panjang dan benchmark server
tujuan perlu dibuktikan. Pengurus masih harus menyepakati SOP, beban, RPO/RTO,
privasi/retensi dan penanggung jawab. Pilot 10-20 warga satu RT selama 1-2 minggu
serta penerimaan UAT belum dilakukan. Jangan menyatakan aplikasi siap produksi
atau menetapkan kapasitas seluruh wilayah hanya dari hasil lokal ini.
