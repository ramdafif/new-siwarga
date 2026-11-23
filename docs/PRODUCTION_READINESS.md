# SiWarga - checklist menuju produksi profesional

Tanggal baseline: **19 November 2026**, zona waktu **Asia/Jakarta**.
Lingkup: `/home/gajiku/app/elkyno/siwarga` dan hasil audit deployment terkait.
Status dokumen: **rencana perbaikan; belum merupakan persetujuan go-live**.

Tambahan audit yang dikirim pengguna telah dipetakan ke checklist ini dan
[AUDIT_SUPPLEMENT_2026-11-19.md](audits/AUDIT_SUPPLEMENT_2026-11-19.md). Lampiran itu
memuat koreksi batas klaim, cakupan yang dilaporkan, dan paket PR-17 sampai
PR-24. Keduanya satu backlog; jangan menjalankan implementasi hanya dari
ringkasan audit tanpa membaca kriteria lulus dan batas operasinya.

## 1. Kesimpulan dan batas pekerjaan

Domain SiWarga sudah dapat diakses melalui HTTPS. Namun, **situs sudah live
tidak sama dengan siap menerima data warga secara profesional**. Kekurangan
terpenting adalah pembuktian pemulihan di luar VPS, monitoring dengan alert
yang benar-benar diterima, serta pembatasan penyalahgunaan registrasi/penulisan.
Setelah itu, selesaikan keamanan dependency, pengelolaan rahasia dan rilis,
privasi, pengujian kapasitas, UAT, serta kesiapan pengurus.

Dokumen ini menerjemahkan audit read-only menjadi backlog yang dapat dikerjakan
bertahap. Penulisan dokumen **tidak memperbaiki kode, mengubah konfigurasi,
menjalankan migrasi, me-restart layanan, atau mengubah database**. Semua kotak
di bawah sengaja belum dicentang: bukti lama tidak otomatis meluluskan kandidat
rilis berikutnya. Temuan yang belum terbukti dibedakan dari cacat yang terlihat.

Larangan saat menjalankan roadmap:

- Jangan melakukan load test, fault injection, atau percobaan abuse di produksi.
- Gunakan staging terisolasi dengan database, Redis, foto, dan akun sintetis.
- Perubahan produksi memerlukan persetujuan operator, jadwal, dan rollback.
- Jangan menyalin password, token, cookie, kunci backup, atau data warga ke Git.
- Pertahankan perubahan lokal yang sudah ada; jangan reset checkout live.

## 2. Baseline yang sudah baik dan batas buktinya

Hal-hal ini dipertahankan dan diuji ulang setelah perubahan, bukan dibangun ulang:

| Area | Bukti yang tersedia | Batas klaim |
| --- | --- | --- |
| Akses publik | Landing/login/registrasi 200, dashboard anonim 302, HTTP menuju HTTPS, HSTS | Respons HTTP bukan UAT alur warga |
| Endpoint internal | Readiness dan metrics internal bekerja; metrics/readiness diblokir dari publik | Metrics bukan bukti sistem monitoring terpasang |
| Sesi dan akses | Cookie secure/HttpOnly/SameSite, CSRF, scope role/wilayah, pencabutan sesi | Tetap perlu regresi pada kandidat rilis |
| Foto dan submit | Validasi/pembersihan metadata, penyimpanan atomik, varian foto, idempotensi submit | Bukan jaminan kapasitas upload tanpa batas |
| Backup lokal | Timer 03:00/15:00 WIB; sukses terakhir yang diamati pada 19 November 2026, sekitar 15:00 WIB | Belum membuktikan selamat dari kehilangan VPS |
| Tes 10 November 2026 | 212 tes lulus tanpa skip; smoke browser 5 role, 27 screenshot, tanpa error JS/overflow | Bukti historis, bukan tes baru dalam pekerjaan dokumentasi ini |
| Beban sintetis | 48 request pada 1 dan 3 sesi dalam artefak rilis | Smoke saja, bukan bukti kapasitas satu RW atau SLO |

Sumber baseline: [RELEASE-2026-11-10.md](releases/RELEASE-2026-11-10.md),
`test-results/release/verification-summary.json`,
`test-results/release/source-manifest.json`, dan
`test-results/live-restart-2026-11-10/checks.json`.
Manifest sumber telah dicocokkan pada audit sebelumnya; tidak ada rerun pytest,
load test, atau mutasi produksi dalam pekerjaan penulisan ini. Hasil audit
dependency nol temuan pada 10 November adalah hasil historis, bukan jaminan
keamanan dependency per 19 November atau tanggal rilis mendatang.

## 3. Cara memakai checklist

- **P1**: risiko operasional/abuse tinggi; wajib selesai sebelum pilot data asli.
- **P2**: wajib ditutup pada batas tahap yang disebutkan dalam tabel.
- **P3**: peningkatan kualitas; bukan blocker keamanan dengan sendirinya.
- **OPEN**: belum selesai atau belum ada bukti penerimaan yang memadai.
- **VERIFIED**: tindakan selesai, kriteria lulus terpenuhi, bukti diperiksa reviewer.
- **ACCEPTED RISK**: hanya untuk sisa risiko non-blocker, dengan alasan, pemilik,
  kontrol pengganti, dan tanggal kedaluwarsa; bukan cara melompati gate wajib.

Prioritas ini adalah urutan kerja proyek, bukan skor CVSS. Pemilik dalam tabel
adalah usulan peran, belum penunjukan orang. Tetapkan nama dan target tanggal
sebelum implementasi. Satu orang boleh memegang beberapa peran, tetapi minta
orang lain memeriksa bukti untuk perubahan berisiko tinggi.

| ID | Prioritas | Paket kerja | Pemilik usulan | Batas wajib | Status |
| --- | --- | --- | --- | --- | --- |
| PR-01 | P1 | Backup offsite dan pemulihan VPS baru | Operator/infrastruktur | Sebelum pilot | OPEN |
| PR-02 | P1 | Monitoring dan pengiriman alert | Operator/infrastruktur | Sebelum pilot | OPEN |
| PR-03 | P1 | Rate limit dan kuota abuse | Backend + operator | Sebelum pilot | OPEN |
| PR-04 | P2 | Dependency aman dan CI berkala | Backend/maintainer | Sebelum pilot; dipelihara tiap rilis | OPEN |
| PR-05 | P2 | Permission dan siklus hidup rahasia | Operator + maintainer | Sebelum pilot | OPEN |
| PR-06 | P2 | Rilis immutable dan rollback | Operator + maintainer | Sebelum pilot | OPEN |
| PR-07 | P2 | Admin individual, recovery, MFA | Backend + pengurus | Recovery sebelum pilot; MFA sebelum perluasan | OPEN |
| PR-08 | P2 | Privasi, retensi, bantuan warga | Pengurus + backend | Sebelum data asli | OPEN |
| PR-09 | P2 | Pagination detail tiket | Backend + frontend | Sebelum perluasan | OPEN |
| PR-10 | P2 | Audit perubahan master data | Backend | Sebelum perluasan | OPEN |
| PR-11 | P2 | Kapasitas dan target layanan | QA + operator + pengurus | Baseline sebelum pilot; penuh sebelum perluasan | OPEN |
| PR-12 | P2 | UAT, pilot, dan penerimaan | QA + pengurus | UAT sebelum pilot; penerimaan sebelum perluasan | OPEN |
| PR-13 | P2 | Aksesibilitas dan mobile | Frontend + QA | Alur utama sebelum pilot; lengkap sebelum perluasan | OPEN |
| PR-14 | P3 | Deep link login yang aman | Backend + QA | Target sebelum perluasan | OPEN |
| PR-15 | P2 | Sinkronisasi dokumen dan serah terima | Maintainer + operator | Runbook sebelum pilot; handover sebelum perluasan | OPEN |
| PR-16 | P2 | Regresi dan verifikasi kandidat rilis | QA + operator | Setiap kandidat rilis | OPEN |
| PR-17 | P2 | Edge, log Nginx, dan error di luar Flask | Operator + backend | Proteksi/log sebelum pilot; optimasi sebelum perluasan | OPEN |
| PR-18 | P2 | Header, cache, sesi, audit, dan pesan error | Backend + QA | Kontrol sensitif sebelum pilot; lengkap sebelum perluasan | OPEN |
| PR-19 | P2 | Durasi lock, pemrosesan foto, dan worker | Backend + operator | Sebelum perluasan; lebih awal jika baseline gagal | OPEN |
| PR-20 | P2 | Query, index, timeout, dan anggaran koneksi | Backend + DBA/operator | Sebelum perluasan; lebih awal jika baseline gagal | OPEN |
| PR-21 | P2 | Upload HP dan ketahanan formulir | Frontend + backend + QA | Alur dasar sebelum pilot; lengkap sebelum perluasan | OPEN |
| PR-22 | P3 | Aset, identitas publik, dan preview share | Frontend + operator | Target sebelum perluasan; fitur opsional terpisah | OPEN |
| PR-23 | P2 | Konsistensi operasional dan alur pengurus | Backend + pengurus + QA | Akses/konsistensi sebelum pilot; UX sebelum perluasan | OPEN |
| PR-24 | P2 | Schema/secret checks CI dan drift operasi | Maintainer + operator | Pemeriksaan rilis sebelum pilot; dipelihara tiap rilis | OPEN |

## 4. Paket perbaikan dan kriteria lulus

### PR-01 - Backup offsite dan disaster recovery

**Temuan:** backup lokal aktif, tetapi kehilangan VPS tetap dapat menghilangkan
aplikasi beserta salinannya. Akses repository offsite, kunci di luar VPS, dan
restore lengkap pada host baru belum dibuktikan.

Rujukan: `deploy/backup.sh`, `scripts/backup.py`,
[OPERATIONS.md](OPERATIONS.md), [DEPLOYMENT_ELKYNO.md](DEPLOYMENT_ELKYNO.md).

- [ ] Tetapkan RPO/RTO, jadwal, retensi, biaya, dan pemilik backup yang disetujui.
- [ ] Aktifkan salinan terenkripsi di luar VPS dengan kredensial berhak minimum;
  pisahkan otoritas hapus bila penyedia mendukung dan simpan kunci recovery
  pada pengelola utama/cadangan, bukan hanya di server aplikasi.
- [ ] Verifikasi backup mencakup database dan original foto yang konsisten;
  checksum, kegagalan parsial, upload bersamaan, dan retensi tidak boleh
  menghasilkan marker sukses palsu atau menghapus satu-satunya salinan baik.
- [ ] Lakukan restore dari offsite ke host/database/folder baru, lalu uji login,
  scope wilayah, tiket, komentar/progres, dan foto privat dengan data sintetis.
- [ ] Ukur RPO dan RTO termasuk pengambilan kunci, provisioning, serta pemeriksaan;
  hubungkan umur backup offsite dan kegagalan job ke PR-02.
- [ ] Pisahkan status snapshot lokal, salinan offsite, integrity check, dan
  pruning. Uji snapshot lama corrupt, disk penuh, dan sisa `.pending-*` di staging;
  karantina/bersihkan hanya dengan batas path/umur dan deteksi job aktif yang aman.
- [ ] Hitung ruang 14 snapshot foto penuh pada wrapper lokal, plus dump dan
  snapshot sementara; gunakan retensi/deduplikasi yang teruji bila diperlukan.
  Wrapper lokal belum menulis metrics `.prom`, berbeda dari `deploy/backup.sh`.

`prune_local()` memverifikasi snapshot sebelum penghapusan dan dapat berhenti
saat menemukan korupsi. Jangan menghilangkan pemeriksaan itu agar job tampak
sukses: backup baru mungkin sudah terbentuk/disalin walau housekeeping gagal.
Laporkan kedua hasil secara jujur dan pertahankan salinan terakhir yang baik.

**Lulus:** operator cadangan memulihkan layanan tanpa bergantung pada disk VPS
lama. Usulan target RPO <=24 jam dan RTO <=4 jam disetujui dan tercapai.
Restore tidak menimpa database warga atau membuat foto menjadi publik.

**Bukti:** ID/timestamp snapshot, hasil integrity check, lokasi offsite tanpa
rahasia, durasi end-to-end, data terakhir yang kembali, dan laporan drill
ditandatangani. `test-results/recovery-drill.json` lokal saja belum cukup.

### PR-02 - Monitoring aktif, bukan sekadar endpoint metrics

**Temuan:** metrics internal tersedia, tetapi layanan Prometheus/node exporter/
Alertmanager belum ditemukan terpasang dalam audit. Contoh scrape memakai
port 8000, sedangkan Gunicorn live yang diamati memakai loopback port 5010.

Rujukan: `deploy/prometheus.yml:13`, `deploy/alerts.yml`,
[OPERATIONS.md](OPERATIONS.md), unit aktif `/etc/systemd/system/siwarga.service`.

- [ ] Pasang monitoring dan alerting, atau layanan setara dengan cakupan sama;
  gunakan bind/target aktual 5010, jangan mengganti port live mengikuti contoh.
- [ ] Pantau domain/HTTPS dari luar VPS, umur sertifikat, kesiapan MySQL/Redis,
  5xx, latency per endpoint/metode, CPU, memori, koneksi, disk/inode, dan backup.
- [ ] Konfigurasikan penerima utama/cadangan, batas waktu respons, eskalasi,
  deduplikasi, maintenance window, dan pemberitahuan kondisi pulih.
- [ ] Di staging, simulasikan Redis gagal, backup gagal/terlambat, dan disk rendah;
  buktikan pesan diterima manusia yang bertugas, bukan hanya status firing.
- [ ] Batasi UI/exporter/metrics ke loopback atau jaringan admin; sediakan
  pemeriksaan eksternal agar matinya seluruh VPS tetap terdeteksi.
- [ ] Samakan trusted Host dan target scrape: pemeriksaan tambahan 19 November
  memberi 400 untuk Host bawaan `127.0.0.1:5010`, tetapi 200 dengan Host domain
  yang diizinkan. Buktikan konfigurasi scraper sebenarnya, bukan hanya portnya.
- [ ] Lengkapi alert expiry TLS, probe HTTPS/502-504, memori/OOM Redis,
  status unit aplikasi/Redis/Nginx/MySQL, serta kegagalan publikasi metrics
  backup lokal. Bedakan konfigurasi template dari konfigurasi aktif.

**Lulus:** gangguan dan pemulihan terdeteksi serta alert sampai ke dua petugas
sesuai waktu yang disepakati. Dashboard tanpa penerima alert tidak lulus.

**Bukti:** konfigurasi tanpa rahasia, daftar target sehat, timestamp gangguan,
pesan diterima/diakui, dan tautan runbook. Kanal operator bukan penambahan
notifikasi WhatsApp/email untuk warga.

### PR-03 - Pembatasan registrasi, penulisan, dan kapasitas upload

**Temuan:** login sudah dibatasi melalui Redis, tetapi registrasi belum dibatasi.
Registrasi memerlukan hashing, penyimpanan akun pending, dan notifikasi pengurus.
Pembatasan request/koneksi Nginx belum ditemukan pada konfigurasi yang diperiksa.
Batas tiga foto per pengiriman tidak membatasi total penyimpanan per akun.

Rujukan: `app/auth.py:24`, `app/auth.py:51`, `app/tickets.py`, `app/uploads.py`.

- [ ] Tentukan limit registrasi yang mempertimbangkan IP bersama/NAT, akun
  pending, interval, dan kapasitas pengurus; batasi sebelum pekerjaan mahal.
- [ ] Tambahkan limit penulisan laporan/komentar/progres dan kuota foto/bytes
  per pengguna/periode, disertai kapasitas total serta kebijakan saat hampir penuh.
- [ ] Terapkan counter atomik lintas-worker dan perilaku backend gagal yang
  eksplisit; jangan melemahkan limiter login atau menggantinya dengan memory.
- [ ] Pastikan alamat klien berasal dari proxy tepercaya; pertimbangkan
  `limit_req`/`limit_conn` per route di edge tanpa mengganggu layanan lain.
- [ ] Uji staging: banyak worker, IP dipalsukan, burst, akun pending menumpuk,
  batas kuota, dan retry sah; berikan 429/pesan tunggu yang jelas dan terukur.
- [ ] Tinjau respons registrasi untuk mengurangi email enumeration tanpa
  menghilangkan bantuan akun. Terapkan perlindungan terukur pada `/akun`,
  komentar/progres, serta telemetry yang hanya tersedia setelah login.
- [ ] Batasi amplifikasi DB/log ketika login ditolak: kode saat ini melakukan
  query akun dan menyimpan audit untuk setiap 429. Tetap jaga jejak keamanan
  melalui agregasi/sampling terukur; jangan mematikan seluruh audit.
- [ ] Uji batas memori/cardinality Redis di staging dan pantau penggunaan/OOM;
  template provisioning memakai 64 MB dengan `noeviction`. Jangan mengubahnya
  menjadi eviction sembarang atau fail-open; risiko kehabisan memori bergantung
  pada banyak klien/key, TTL, dan kepercayaan proxy, bukan email acak saja.

**Lulus:** percobaan massal dibatasi tanpa mengunci warga normal di jaringan
bersama; resource dan notifikasi tidak tumbuh tanpa batas. CSRF, otorisasi,
validasi file, serta idempotensi submit tetap bekerja.

**Bukti:** matriks limit, alasan pemilihan angka, hasil tes konkurensi/abuse
staging, metrik penolakan, dan prosedur bantuan ketika pengguna sah terbatasi.

### PR-04 - Dependency, supply chain, dan CI

**Temuan:** runtime mengunci `dnspython==2.9.0`; advisory upstream
`GHSA-vvf4-9x63-8xvv` / `CVE-2026-128089` mencakup versi <2.9.2. Dampaknya
memerlukan parsing teks zone/WKS yang dikendalikan penyerang; audit tidak
menemukan jalur eksploitasi aplikasi yang terjangkau. Jangan menyebutnya
endpoint aplikasi yang terbukti dapat dieksploitasi.

Dev lock mengunci `pip==25.0.1`. Salah satu advisory yang relevan adalah
`PYSEC-2026-3721`, diperbaiki pada pip 26.2. Risiko ini mengenai penggunaan
tooling dengan index paket berbahaya, bukan otomatis RCE pada web SiWarga.
Referensi upstream diperiksa pada 19 November 2026; versi perbaikan tersebut
adalah batas advisory, bukan klaim versi terbaru atau bebas semua kerentanan.

Rujukan: `requirements.lock:6`, `requirements-dev.lock:20`,
`.github/workflows/ci.yml:2`, `.github/workflows/ci.yml:43`.
Referensi primer:
`https://github.com/rthalley/dnspython/security/advisories/GHSA-vvf4-9x63-8xvv`
dan
`https://github.com/pypa/advisory-database/blob/main/vulns/pip/PYSEC-2026-3721.yaml`.

- [ ] Triage seluruh advisory runtime dan dev/tooling: versi, exposure,
  kompatibilitas, pemilik, deadline, serta keputusan yang bisa ditinjau.
- [ ] Perbarui pin dan regenerasi lock secara konsisten pada environment baru;
  gunakan versi kompatibel yang telah diperiksa pada tanggal implementasi.
- [ ] Audit kedua lock, bukan runtime saja; tambahkan audit terjadwal dan
  notifikasi hasil agar advisory baru terdeteksi walau tidak ada push/PR.
- [ ] Jalankan fresh install, `pip check`, seluruh tes MySQL/Redis tanpa skip,
  smoke browser, dan audit sebelum mengizinkan artifact rilis.
- [ ] Tinjau hak akses CI, sumber paket, pin action/image, serta penyimpanan
  artifact; jangan melakukan auto-deploy hanya karena jadwal audit berjalan.

**Lulus:** lock dapat direproduksi, dependency terpasang tidak drift, dan tidak
ada advisory relevan yang dibuang diam-diam. Temuan tanpa jalur terjangkau tetap
dicatat; penundaan non-blocker memerlukan reviewer, kontrol, dan kedaluwarsa.

**Bukti:** diff dependency, laporan audit bertanggal untuk kedua lock, CI run
ID, artifact/commit SHA, hasil install bersih, dan alasan exception bila ada.

### PR-05 - Permission rahasia dan respons paparan

**Temuan:** `.env` dan `.local/verification/browser.env` memiliki mode 0664
dengan direktori induk yang dapat dilalui akun OS lain. Ini risiko pembacaan
lokal; bukan bukti bahwa `/etc/siwarga/app.env` atau kredensial produksi bocor.

- [ ] Inventaris rahasia aplikasi, DB, Redis, backup, akun smoke, CI, dan salinan;
  catat lokasi/pemilik saja, tidak perlu mencatat nilai rahasianya.
- [ ] Batasi file ke 0600 atau 0640 dengan owner/group minimum yang benar;
  periksa permission direktori induk dan kebutuhan baca service terlebih dahulu.
- [ ] Periksa tracking/history Git, log, artifact, dan backup untuk paparan
  tanpa mencetak isi rahasia ke output atau laporan audit.
- [ ] Jika paparan terkonfirmasi atau tidak dapat dikesampingkan, lakukan
  rotasi terencana dan pencabutan sesi/token terdampak; periksa health sesudahnya.
- [ ] Pisahkan credential runtime, migrator, backup, dan operator; dokumentasikan
  penyimpanan/recovery serta penonaktifan akses petugas yang berhenti.
- [ ] Pisahkan `.env` dev/test dari konfigurasi produksi. `create_app()` tetap
  memanggil `load_dotenv()` sehingga variabel lokal yang belum ada di environment
  bisa ikut terbaca; nilai environment yang sudah ada tidak otomatis tertimpa.
  Verifikasi tanpa mencetak nilai, termasuk variabel demo/test yang tidak perlu.

**Lulus:** hanya principal yang diperlukan dapat membaca rahasia; penggantian
credential dapat dilakukan tanpa kehilangan akses pemulihan atau data.

**Bukti:** daftar owner/mode/path yang disanitasi, hasil pemeriksaan paparan,
keputusan rotasi, dan verifikasi layanan. Jangan lampirkan isi file env.

### PR-06 - Rilis immutable, migrasi aman, dan rollback

**Temuan:** service live menggunakan checkout yang masih memiliki perubahan
belum di-commit. Aset statis dapat berubah lebih dulu daripada worker Python;
restart/recycle dapat menjalankan kombinasi versi yang sulit direproduksi.

Rujukan: [DEPLOYMENT_ELKYNO.md](DEPLOYMENT_ELKYNO.md),
[OPERATIONS.md](OPERATIONS.md), `README.md`.

- [ ] Inventaris perubahan lokal dan tentukan kandidat rilis dengan persetujuan
  pemilik; jangan menghapus perubahan atau menganggap HEAD sama dengan live.
- [ ] Pisahkan source release dari `.local/`, data MySQL/verification lokal,
  artefak uji, dan file SQL nyasar di root; klasifikasikan kepemilikan/kegunaan
  sebelum memindahkan apa pun. Jumlah file kotor dan ukuran disk pada laporan
  tambahan adalah snapshot historis, bukan alasan menjalankan penghapusan massal.
- [ ] Bangun release directory/artifact berdasarkan commit yang telah melalui
  CI, dependency terkunci, static assets cocok, serta environment per release.
- [ ] Uji perpindahan atomik `current` dan restart terencana; catat versi live,
  migrasi, backup offsite, health, dan persetujuan operator untuk setiap rilis.
- [ ] Uji migrasi aditif/kompatibel di staging beserta rollback aplikasi ke
  schema sesudah migrasi; jangan mengandalkan downgrade database otomatis.
- [ ] Latih rollback sambil mempertahankan laporan/foto yang masuk setelah
  deployment; tentukan kapan perlu menghentikan penulisan dan membuka insiden.

**Lulus:** versi source, dependency, template, dan aset yang aktif diketahui
serta konsisten. Rollback yang sudah diuji tidak menghapus laporan baru atau
menginterupsi backup aktif. Tidak ada rilis dari worktree yang belum disepakati.

**Bukti:** SHA/artifact, hasil CI, catatan cutover, versi schema, smoke test,
dan hasil rollback di staging dengan data sebelum/sesudah rilis.

### PR-07 - Akun istimewa, recovery, dan tindakan sensitif

**Temuan:** reset akun tersedia melalui admin, tetapi superadmin tidak dapat
diubah melalui UI pengurus. Belum ada jalur recovery CLI terpelihara, MFA, atau
step-up authentication khusus tindakan sensitif yang ditemukan dalam audit.

Rujukan: `app/admin.py:131`, `app/admin.py:171`, `app/auth.py`.

- [ ] Tetapkan admin utama/cadangan individual dan hak minimum; hilangkan
  penggunaan akun bersama/demo pada operasional resmi.
- [ ] Sediakan prosedur recovery/break-glass untuk admin dan superadmin melalui
  CLI/runbook berhak minimum, pemeriksaan identitas, dan catatan audit.
- [ ] Pastikan reset/perubahan hak/status mencabut sesi yang diperlukan,
  password sementara disampaikan privat, dan pengguna wajib menggantinya.
- [ ] Tambahkan MFA untuk akun istimewa dan autentikasi ulang tindakan kritis;
  simpan recovery codes di luar server dan uji kehilangan perangkat.
- [ ] Uji petugas berganti/berhenti, admin terkunci, pengambilalihan sesi lama,
  dan recovery gagal tanpa membocorkan password atau memberi hak berlebihan.
- [ ] Periksa apakah berkas credential admin awal masih ada dan aksesnya aman;
  jalankan disposisi/rotasi sesuai SOP. Bootstrap yang menolak saat user sudah
  ada tidak menggantikan recovery admin. Jangan menganggap file sudah dihapus
  hanya karena dokumentasi memerintahkannya.

**Lulus sebelum pilot:** dua pengelola dapat menjalankan recovery yang aman
tanpa mengedit DB manual tanpa prosedur. **Lulus sebelum perluasan:** MFA,
step-up, dan recovery-nya teruji. Email reset mandiri tidak wajib untuk MVP.

**Bukti:** matriks hak, SOP recovery, hasil uji pencabutan sesi/MFA, dan audit
event yang disanitasi; jangan menyimpan recovery code di dokumentasi publik.

### PR-08 - Privasi, retensi, dan bantuan warga

**Temuan:** halaman publik privasi/bantuan/kontak dan pemberitahuan saat
registrasi belum tersedia. Kebijakan pemrosesan serta retensi perlu disepakati
pengurus sebelum data warga masuk; audit teknis bukan kesimpulan kepatuhan hukum.

Rujukan: [REQUIREMENTS.md](REQUIREMENTS.md), [PILOT.md](PILOT.md),
`app/auth.py:51`, `app/routes.py`.

- [ ] Sepakati tujuan, kategori data, akses tiap role, pihak pemroses, kontak
  pengelola, dan dasar pemrosesan yang sesuai; tinjau kewajiban yang berlaku
  dengan pihak kompeten jika diperlukan, bukan mengarang klaim kepatuhan.
- [ ] Tambahkan pemberitahuan privasi yang dapat dibaca tanpa login dan mudah
  ditemukan dari registrasi/footer; jangan otomatis mewajibkan checkbox consent
  tanpa menilai kebutuhan dan dasar pemrosesan.
- [ ] Tetapkan retensi akun pending/nonaktif, tiket, komentar, foto, audit log,
  dan backup; jelaskan koreksi/penghapusan, pengecualian, serta waktu layanan.
- [ ] Sediakan bantuan/kontak dan panduan foto aman tanpa data sensitif orang
  lain; tentukan jalur pengaduan keamanan/privasi dan eskalasinya.
- [ ] Uji prosedur koreksi/penghapusan di staging, termasuk otorisasi, relasi
  data, backup, dan foto; jangan membuat cron penghapusan uploads sembarangan.

**Lulus:** pengurus menyetujui kebijakan; warga dapat membaca pemberitahuan
sebelum mendaftar dan tahu cara meminta bantuan/koreksi. Implementasi dan SOP
konsisten, termasuk apa yang terjadi pada salinan backup.

**Bukti:** versi kebijakan, pihak penyetuju/tanggal, lokasi halaman, SOP
retensi, serta hasil uji permintaan pengguna dengan identitas sintetis.

### PR-09 - Detail tiket tetap ringan saat riwayat membesar

**Temuan:** detail memuat seluruh attachment, history, progres, dan komentar
sekaligus. Varian/lazy loading foto sudah ada, tetapi tidak membatasi jumlah
baris query atau elemen DOM saat satu tiket berumur panjang.

Rujukan: `app/models.py:119`, `app/tickets.py:145`,
`app/templates/pengaduan/detail.html:7`.

- [ ] Tentukan batas per halaman untuk diskusi, progres, history, dan attachment;
  gunakan pagination/lazy endpoint dengan urutan stabil dan tie-breaker ID.
- [ ] Terapkan filter otorisasi pada setiap halaman/endpoint foto; cursor/ID
  yang dipalsukan tidak boleh membocorkan tiket atau wilayah lain.
- [ ] Batasi query, ukuran respons, dan DOM; sediakan kondisi kosong, akhir
  halaman, gagal muat, serta retry yang tidak menggandakan item.
- [ ] Tambahkan regresi dengan riwayat besar dan penulisan bersamaan di staging;
  ukur jumlah query, waktu, ukuran respons, dan penggunaan memori.

**Lulus:** biaya halaman awal dibatasi oleh page size, bukan total umur tiket;
isi tetap dapat ditelusuri tanpa hilang/duplikat akibat urutan tidak stabil.

**Bukti:** ukuran dataset, query/timing sebelum-sesudah, hasil scope test,
dan smoke pada HP/jaringan yang disepakati.

### PR-10 - Audit perubahan master data

**Temuan:** mutasi akun sudah diaudit, tetapi perubahan wilayah/kategori belum
memiliki cakupan audit setara. Ini mempersulit penelusuran kesalahan pengurus.

Rujukan: `app/admin.py:48`, `app/admin.py:98`, `app/security.py`.

- [ ] Catat create/update/delete wilayah dan kategori yang memang didukung,
  lengkap dengan actor, target, waktu, hasil, dan request ID.
- [ ] Simpan perubahan minimum sebelum/sesudah yang diperlukan; jangan merekam
  credential atau data warga berlebihan pada payload audit.
- [ ] Uji commit/rollback: audit sukses harus sesuai mutasi yang benar-benar
  tersimpan, dan penolakan/gagal tetap memiliki jejak yang dibutuhkan.
- [ ] Tentukan akses, retensi, dan ekspor log untuk investigasi; sertakan
  pengujian bahwa pengguna biasa tidak dapat membaca log administratif.

**Lulus:** pengurus dapat menjawab siapa mengubah master data apa dan kapan
tanpa membocorkan rahasia atau menghasilkan catatan sukses palsu.

**Bukti:** sampel event sintetis, hasil tes transaksi/otorisasi, dan SOP retensi.

### PR-11 - Kapasitas, performa, dan target layanan yang disahkan

**Temuan:** bukti source saat ini hanya smoke 48 request pada 1/3 sesi. Belum
ada pembuktian beban tujuan, soak dua jam, dan kapasitas seluruh RW.

Rujukan: [REQUIREMENTS.md](REQUIREMENTS.md), [VALIDATION.md](VALIDATION.md),
[PILOT.md](PILOT.md), `test-results/release/verification-summary.json`.

- [ ] Sepakati jumlah warga/RT, sesi bersamaan, volume tiket/foto, pola puncak,
  anggaran storage/backup, dan target layanan dengan pengurus.
- [ ] Siapkan staging representatif, data sintetis berumur panjang, dan profil
  mobile/jaringan terdokumentasi; isolasikan resource dari data warga asli.
- [ ] Uji bertahap minimal dua kali perkiraan puncak sebelum perluasan, meliputi
  login, dashboard/filter/detail, submit foto, komentar/progres, dan notifikasi.
- [ ] Lakukan soak dua jam; rekam p95 per endpoint/metode, 5xx, request ditolak
  sesuai desain, CPU/memori/koneksi, disk/inode, dan efek backup bersamaan.
- [ ] Hitung pertumbuhan foto/DB/log/offsite dan waktu mencapai ambang penuh;
  tetapkan kapan tambah kapasitas atau hentikan perluasan.

Usulan gate awal dari REQUIREMENTS, **belum SLO yang disepakati/tercapai**:

| Pengukuran | Usulan target |
| --- | --- |
| HTML pada uji jaringan server | Rata-rata <=300 ms |
| GET utama / POST laporan | p95 <=1 detik / <=3 detik |
| Error server | 5xx <0,1%; penolakan yang diharapkan dilaporkan terpisah |
| Halaman tiga foto di profil mobile | Transfer awal <=1 MB; muat awal <=5 detik; foto setelah scroll <=5 detik |
| Stabilitas | Soak 2 jam tanpa pertumbuhan resource terus-menerus |
| Ruang disk | Bebas >=20%, dengan proyeksi pertumbuhan |
| Pemulihan | RPO <=24 jam; RTO <=4 jam melalui offsite |

**Lulus:** baseline aman untuk peserta pilot tersedia lebih dulu; perluasan
baru dilakukan setelah target disahkan dan tercapai pada lingkungan
representatif. Sampel terlalu kecil tidak cukup menyimpulkan 5xx <0,1%.
Jika kapasitas kurang, kurangi peserta/perbaiki bottleneck; jangan mengganti
target diam-diam agar tes terlihat lulus.

**Bukti:** skenario, dataset, profil jaringan, konfigurasi mesin, jumlah/sampel
request, hasil per endpoint/metode, grafik soak, dan keputusan kapasitas.

### PR-12 - UAT nyata dan pilot satu RT

**Temuan:** `docs/EVIDENCE.md` masih template, bukan UAT atau penerimaan warga
yang sudah selesai. Screenshot dan tes otomatis tidak menggantikan ini.

Rujukan: [PILOT.md](PILOT.md), [EVIDENCE.md](EVIDENCE.md).

- [ ] Tetapkan RT/RW, peserta, penanggung jawab tiap role, jam pelayanan,
  target respons/verifikasi, bantuan, dan eskalasi tiket terlambat.
- [ ] Lakukan UAT sintetis lima role: daftar -> verifikasi -> laporan ->
  penugasan -> progres -> selesai/ditolak, komentar dan notifikasi.
- [ ] Sertakan salah wilayah, foto tidak valid, koneksi lambat/terputus,
  submit ulang, akun nonaktif, pergantian petugas, dan reset password.
- [ ] Setelah gate pilot lulus, jalankan pilot 1-2 minggu, usulan 10-20 warga
  satu RT; konfirmasi peserta/durasi dengan pengurus sebelum mulai.
- [ ] Isi bukti penerimaan aktual: keberhasilan tugas, bantuan yang diperlukan,
  waktu respons, laporan tertunda, keluhan, insiden, serta keputusan perluasan.

**Lulus:** pengurus dan perwakilan pengguna menerima hasil; tidak ada masalah
kritis terbuka. Bandingkan dengan baseline proses lama sebelum mengklaim dampak.
Ketidakadaan keluhan saja bukan bukti seluruh skenario lulus.

**Bukti:** matriks UAT, daftar issue/status, ringkasan pilot yang disanitasi,
dan tanda persetujuan. Jangan mempublikasikan nama, nomor HP, atau isi laporan.

### PR-13 - Aksesibilitas dan pengalaman mobile

**Temuan:** error field belum terhubung melalui `aria-describedby`/
`aria-invalid`; sidebar mobile disembunyikan dengan transform tanpa pengelolaan
fokus/inert. Elemen di luar layar berisiko tetap terjangkau keyboard.

Rujukan: `app/templates/components.html:43`, `app/static/js/app.js:5`.

- [ ] Hubungkan label, bantuan, dan error dengan ID yang unik dan atribut ARIA
  yang sesuai; fokuskan/umumkan kegagalan submit secara dapat dipahami.
- [ ] Kelola fokus sidebar: elemen tertutup tidak tabbable, status expanded
  sesuai, Escape menutup, dan fokus kembali ke pemicu; uji perilaku modal bila ada.
- [ ] Uji alur utama dengan keyboard dan pembaca layar, kontras, zoom/reflow,
  target sentuh, serta ukuran HP kecil tanpa horizontal overflow.
- [ ] Tinjau deklarasi font 6-10 px pada stylesheet dan ukur ukuran/kontras
  yang benar-benar tampil di setiap breakpoint. Sepakati baseline keterbacaan
  untuk warga; ukuran minimum desain bukan otomatis aturan minimum font WCAG.
- [ ] Periksa status loading/sukses/gagal, koneksi buruk, upload ditolak,
  empty state, dan navigasi kembali tanpa kehilangan masukan yang seharusnya aman.

**Lulus:** warga dapat daftar/login, membuat dan memantau tiket tanpa terjebak
fokus atau kehilangan penjelasan error. Smoke otomatis dilengkapi pemeriksaan
manual; jangan mengklaim sertifikasi aksesibilitas dari screenshot saja.

**Bukti:** perangkat/browser, skenario keyboard/screen reader, hasil automated
check bila digunakan, serta issue dan verifikasi perbaikannya.

### PR-14 - Login kembali ke tujuan yang aman

**Temuan:** login selalu menuju dashboard/halaman pending sehingga tujuan
`next` dari deep link tidak dipakai. Ini perbaikan UX, bukan bukti open redirect
saat ini; dukungan baru justru harus menolak redirect berbahaya.

Rujukan: `app/auth.py:47`.

- [ ] Pertahankan tujuan internal yang tervalidasi setelah login sukses;
  akun pending tetap diarahkan ke alur verifikasi sesuai kebijakan.
- [ ] Tolak origin eksternal, URL protocol-relative, skema berbahaya, dan bentuk
  encoding/karakter kontrol yang dapat melewati validasi; gunakan fallback aman.
- [ ] Tetap lakukan otorisasi pada tujuan; uji link tiket milik sendiri,
  lintas wilayah, tidak ditemukan, dan sesi yang habis.

**Lulus:** deep link sah bekerja tanpa membuka redirect keluar situs atau
melewati scope akses. Jika ditunda, catat sebagai risiko UX non-blocker.

**Bukti:** regresi parameter `next` valid/tidak valid dan smoke alur pengguna.

### PR-15 - Dokumen operasional dan serah terima

**Temuan:** dokumen deployment memuat status historis 2 November, termasuk
masalah host/DNS yang harus dibedakan dari perbaikan dan bukti 10 November.
Contoh port/layanan bukan selalu konfigurasi aktif. Beberapa artefak operasional
berada di direktori yang diabaikan Git.

Rujukan: [DEPLOYMENT_ELKYNO.md](DEPLOYMENT_ELKYNO.md),
[OPERATIONS.md](OPERATIONS.md), [TECHNICAL.md](TECHNICAL.md),
[HTTP.md](HTTP.md), [RELEASE-2026-11-10.md](releases/RELEASE-2026-11-10.md).

- [ ] Sinkronkan topologi, port 5010, unit service, domain, lokasi konfigurasi,
  status DNS/TLS, dan prosedur deploy dengan keadaan aktual bertanggal;
  pertahankan catatan lama sebagai histori, bukan instruksi aktif yang menyesatkan.
- [ ] Lengkapi runbook DB/Redis gagal, 5xx, disk penuh, foto hilang, backup
  gagal, admin terkunci, dugaan bocor, serta rollback; tulis pemilik dan eskalasi.
- [ ] Tetapkan pemilik domain/VPS/repository, biaya/perpanjangan, akses pengganti,
  lokasi kunci recovery di luar VPS, dan prosedur offboarding.
- [ ] Arsipkan bukti CI/rilis/drill di penyimpanan terkendali dengan retensi;
  `test-results/` yang diabaikan Git bukan arsip jangka panjang dengan sendirinya.
- [ ] Minta operator selain pembuat melakukan deployment/recovery latihan dari
  runbook di staging tanpa mengambil credential dari chat atau DB produksi.

**Lulus:** pengurus dapat mengoperasikan dan memulihkan layanan tanpa
ketergantungan tunggal pada pembuat; dokumen tidak menyatakan pekerjaan selesai
hanya karena contoh konfigurasi atau template bukti sudah tersedia.

**Bukti:** versi runbook, daftar tanggung jawab tanpa rahasia, arsip artifact,
catatan latihan operator cadangan, dan persetujuan serah terima.

### PR-16 - Regresi keamanan dan verifikasi kandidat rilis

**Jenis:** gate mempertahankan kontrol yang sudah ada, bukan daftar celah baru
yang semuanya ditemukan. Bukti 10 November dipakai sebagai baseline pembanding.

Rujukan: `tests/`, `.github/workflows/ci.yml`,
[RELEASE-2026-11-10.md](releases/RELEASE-2026-11-10.md), [HTTP.md](HTTP.md).

- [ ] Jalankan seluruh tes unit/integrasi MySQL/Redis serta browser smoke
  lima role pada kandidat rilis; tidak boleh ada skip/gagal yang disembunyikan.
- [ ] Regresikan CSRF, akses lintas user/RT/RW, foto privat, sesi dicabut,
  password wajib diganti, validasi/metadata upload, idempotensi, dan konkurensi.
- [ ] Verifikasi mode produksi: debug mati, trusted hosts/proxy benar, cookie
  dan header aman, TLS/redirect/renewal, DB/Redis serta port admin tidak publik;
  tinjau firewall, patch host, dan hak service sebagai pemeriksaan deployment.
- [ ] Pastikan log/error tidak mengungkap credential/traceback kepada warga;
  request ID, rotasi/retensi log, readiness dependency, dan metrics tetap berguna.
- [ ] Setelah cutover disetujui, lakukan smoke non-destruktif domain/asset/health;
  alur tulis memakai staging atau akun/tiket uji yang diotorisasi terpisah.
- [ ] Cocokkan SHA/artifact, schema, dependency, dan konfigurasi aktif dengan
  bukti rilis; tutup semua issue regresi sebelum memperluas pengguna.

**Lulus:** kontrol baseline tidak mundur, CI sesuai kandidat rilis, serta
lingkungan tujuan sehat. Tes lokal saja tidak menggantikan backup, alert,
kapasitas, privasi, atau persetujuan pengurus.

**Bukti:** CI/JUnit, laporan dependency, browser report, source/artifact manifest,
checklist deployment yang disanitasi, dan keputusan operator.

### Paket pelengkap PR-17 sampai PR-24

Detail temuan, tindakan, kriteria lulus, dan bukti delapan paket lanjutan ada di
[lampiran audit tambahan](audits/AUDIT_SUPPLEMENT_2026-11-19.md). Pakai ID dari tabel
induk ini saat menutup issue agar temuan lama dan baru tidak dihitung dua kali.
Optimasi seperti HTTP/2, offload media, atau format font dipilih berdasarkan
kompatibilitas/hasil ukur, bukan dianggap syarat keamanan universal.

## 5. Urutan eksekusi yang disarankan

| Tahap | Fokus | Hasil yang harus tersedia sebelum lanjut |
| --- | --- | --- |
| A - Siapkan batas aman | Nama pemilik, scope peserta, staging terisolasi, rencana perubahan | Akses dan data uji terpisah; tidak mengganggu warga |
| B - Lindungi data dan akses | PR-01, PR-02, PR-05, PR-07 recovery, PR-08 | Offsite/restore, alert, rahasia, recovery, kebijakan terbukti |
| C - Siapkan kandidat rilis | PR-03/04/06/10, kontrol edge/sesi PR-17/18, PR-24, runbook PR-15 | Proteksi abuse, rahasia/CI, rilis/rollback reproducible |
| D - Buktikan kualitas | PR-09/11/13/14/16, PR-19/20/21/23, pilihan PR-22, UAT PR-12 | Regresi, UX, kapasitas, dan UAT dengan bukti |
| E - Pilot terbatas | Gate pilot; PR-12 selama 1-2 minggu | Hasil pilot dan perbaikan diterima pengurus |
| F - Perluasan | MFA PR-07, kapasitas penuh PR-11, handover PR-15, gate perluasan | Keputusan go/no-go tertulis dan pemilik operasi aktif |

Pekerjaan dapat tumpang tindih bila tidak berbagi risiko, tetapi gate tidak
dilompati. Durasi implementasi belum diestimasi; ukur setelah pemilik, pilihan
infrastruktur, dan hasil investigasi ditetapkan. Waktu pilot bukan janji semua
perbaikan dapat diselesaikan dalam 1-2 minggu.

## 6. Gate go/no-go

### Gate A - Boleh memulai pilot data warga asli

- [ ] PR-01/02/03 VERIFIED: offsite dan restore host baru, alert diterima, abuse dibatasi.
- [ ] PR-04/05/06 VERIFIED: dependency ditinjau, rahasia terlindungi, rilis dan rollback teruji.
- [ ] Bagian recovery PR-07 dan seluruh PR-08 lulus; admin utama/cadangan ditunjuk.
- [ ] Baseline kapasitas PR-11 sesuai peserta, UAT sintetis PR-12, dan aksesibilitas
  alur utama PR-13 lulus; tidak ada masalah akses/data/availability kritis terbuka.
- [ ] Runbook awal PR-15 tersedia dan PR-16 lulus untuk kandidat yang benar-benar dipasang.
- [ ] Kontrol sensitif PR-17/18/24 lolos: log tidak membocorkan data, header/cache
  sesuai respons aktual, schema/secret checks tersedia, konfigurasi aktif tidak
  diasumsikan sama dengan provisioning. Tidak wajib menerapkan semua optimasi.
- [ ] PR-21/23 tidak menyisakan alur formulir rusak, penugasan tidak sah, atau
  inkonsistensi akses/data yang menghalangi peserta pilot.
- [ ] Pengurus menyetujui peserta, jam layanan, kebijakan, pemantauan harian,
  serta prosedur menghentikan pilot dengan aman bila muncul insiden.

**NO-GO** bila backup hanya lokal, alert belum sampai, akses lintas wilayah
bocor, rahasia terpapar belum ditangani, dependency berisiko relevan belum
ditangani, atau pemulihan belum terbukti. Jangan menganggap penggunaan data
asli aman hanya karena landing page bisa dibuka. Jika data asli sudah ada,
prioritaskan mitigasi dan keputusan operator; jangan menonaktifkan/menghapus
layanan atau data secara sepihak.

### Gate B - Boleh memperluas ke seluruh target pengguna

- [ ] Gate A tetap berlaku pada release yang aktif, bukan hanya rilis sebelumnya.
- [ ] PR-07 lengkap, PR-09/10 VERIFIED, dan PR-11 membuktikan >=2x perkiraan
  puncak beserta soak dua jam terhadap target yang sudah disetujui.
- [ ] PR-12 memiliki hasil pilot 1-2 minggu yang diterima, issue ditutup,
  dan kesiapan pengurus menanggapi laporan sudah terbukti.
- [ ] PR-13 lengkap dan PR-15 handover diterima; PR-16 lulus setelah perbaikan terakhir.
- [ ] PR-14 selesai atau penundaan UX ditulis sebagai ACCEPTED RISK dengan deadline.
- [ ] PR-17/18/19/20/21/23/24 memiliki bukti sesuai kriteria; pilihan teknis
  optimasi dijustifikasi oleh pengukuran. PR-22 ditutup atau ditunda eksplisit
  sebagai kualitas non-blocker; ekspor CSV/print bukan kewajiban go-live baru.
- [ ] Biaya, kapasitas, jadwal patch/drill, kepemilikan domain, dan pengganti
  operator disepakati; tidak ada blocker tanpa bukti atau tanpa pemilik.

Keputusan akhir: **GO / NO-GO**, ditetapkan pengurus bersama operator dan
reviewer teknis. Dokumen ini sendiri tidak memberi keputusan GO.

## 7. Format pencatatan penyelesaian

Untuk setiap PR-ID, tambahkan catatan berikut saat pelaksanaan. Kotak baru boleh
dicentang setelah reviewer memeriksa bukti, bukan saat coding selesai.

```text
ID pekerjaan       : PR-xx
Pemilik / reviewer :
Target / selesai   :
Status             : OPEN / IN PROGRESS / VERIFIED / ACCEPTED RISK
Commit / artifact  :
Lingkungan / waktu :
Tindakan selesai   :
Kriteria diuji     :
Lokasi bukti       :
Risiko tersisa     :
Kontrol / deadline :
Persetujuan        :
```

Gunakan artifact CI atau arsip privat untuk data operasional. Di repo cukup
simpan ringkasan yang disanitasi, SHA, dan referensi bukti. Catat tanggal,
lingkungan, metode, ukuran sampel, dan siapa yang memeriksa. Jangan menghapus
hasil gagal; jelaskan tes perbaikan mana yang menggantikannya.

## 8. Tanggung jawab setelah live

Jadwal berikut usulan awal untuk disahkan saat handover, bukan otomatis sudah aktif.

| Frekuensi | Pemeriksaan | Pemilik usulan |
| --- | --- | --- |
| Terus-menerus | Uptime/HTTPS, dependency health, 5xx/latency, disk, umur backup; alert dan eskalasi | Operator utama/cadangan |
| Harian selama pilot | Backup offsite sukses, error, tiket tertunda, kuota foto, keluhan warga | Operator + pengurus RT |
| Mingguan | Tinjau advisory otomatis, issue, log anomali, pending account, pertumbuhan kapasitas | Maintainer + operator |
| Bulanan | Patch terencana, review akses petugas, biaya, retensi, proyeksi storage | Maintainer + pengurus |
| Tiap rilis | CI/audit, backup, kompatibilitas migrasi, rollback, smoke, versi artifact | Maintainer + QA + operator |
| Triwulanan atau setelah perubahan besar | Drill restore offsite, recovery admin, alert, dan pelaksanaan runbook oleh cadangan | Operator cadangan + reviewer |
| Sebelum tenggat | Perpanjangan domain/sertifikat/layanan dan pemeriksaan mekanisme renewal | Pemilik domain + operator |
| Setiap insiden | Containment, pemulihan, komunikasi sesuai kebijakan, timeline, dan tindak lanjut | Penanggung jawab insiden |

Untuk gangguan keamanan atau integritas data: catat request ID dan timeline,
batasi dampak dengan persetujuan operator, pertahankan bukti, pulihkan dari
sumber terpercaya, lalu tinjau akar masalah. Jangan menaruh data insiden sensitif
pada issue publik atau mengumumkan penyebab sebelum terverifikasi.

## 9. Yang bukan syarat wajib profesional

Roadmap ini tidak memerlukan migrasi ke React, penggantian Flask/MySQL,
microservices, Docker/Kubernetes, GPS/peta, NIK/KTP, aplikasi mobile native,
notifikasi eksternal untuk warga, atau layanan aplikasi berbayar. Tambahkan
hanya jika kebutuhan dan biaya disetujui; bukan untuk menggantikan perbaikan
backup, keamanan, operasi, serta penerimaan yang belum terbukti.

Daftar ini berbasis bukti audit yang tersedia, bukan sertifikasi bebas bug,
pentest menyeluruh, atau penetapan kepatuhan hukum. Evaluasi ulang bila jumlah
pengguna, jenis data, integrasi, atau topologi layanan berubah.
