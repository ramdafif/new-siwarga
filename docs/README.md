# Dokumentasi SiWarga

Mulai menjalankan aplikasi melalui [README utama](../README.md). Direktori ini
menyimpan dokumentasi proyek; source aplikasi ada di `app/`, skema versi database
di `migrations/`, dan template layanan di `deploy/`.

## Panduan aktif

- [REQUIREMENTS.md](REQUIREMENTS.md): kebutuhan dan kriteria penerimaan.
- [ERD.md](ERD.md): tabel, relasi, PK/FK, dan alasan desain database.
- [TECHNICAL.md](TECHNICAL.md): arsitektur, antarmuka, tes, dan benchmark.
- [HTTP.md](HTTP.md): endpoint, metode, otorisasi, input, dan respons.
- [OPERATIONS.md](OPERATIONS.md): deployment, monitoring, backup, dan insiden.
- [DEPLOYMENT_ELKYNO.md](DEPLOYMENT_ELKYNO.md): catatan lingkungan deployment.
- [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md): backlog dan gate produksi.
- [PILOT.md](PILOT.md): panduan warga/pengurus dan penerimaan pilot.
- [EVIDENCE.md](EVIDENCE.md): formulir bukti UAT dan dampak.

## Riwayat dan referensi

Tanggal pada dokumen berikut menunjukkan waktu pemeriksaan awal. Hasil di
dalamnya bukan hasil pengujian ulang untuk checkout saat ini.

- [VALIDATION.md](VALIDATION.md): validasi lokal 26 Oktober 2026.
- [Audit 27 Oktober 2026](audits/AUDIT-2026-10-27.md).
- [Lampiran audit 19 November 2026](audits/AUDIT_SUPPLEMENT_2026-11-19.md).
- [Catatan rilis 10 November 2026](releases/RELEASE-2026-11-10.md).
- [Prompt awal proyek](archive/PROMPT_CODEX_SIWARGA_FLASK_MYSQL.md): referensi
  historis; struktur dan petunjuk operasional terbaru mengikuti README utama.

## Menjaga workspace tetap rapi

Jalankan perintah dari root repository. Source Python, template, CSS, JavaScript,
font, dan branding masuk `app/`; pengujian masuk `tests/`; alat bantu masuk
`scripts/`. Dependensi tetap di root karena dipakai instalasi, CI, dan deployment.
Pertahankan lisensi font dan vendor bersama asetnya.

Dokumen baru masuk `docs/`, laporan audit bertanggal masuk `docs/audits/`,
catatan rilis masuk `docs/releases/`, dan referensi lama masuk `docs/archive/`.
Tautan Markdown mengikuti lokasi dokumen; path perintah shell tetap relatif
terhadap root repository.

Data lokal berikut diabaikan Git dan punya fungsi berbeda:

- `.local/`: instalasi MySQL portabel, `mysql-data/`, kredensial lokal, log,
  dan backup. Dump SQL yang sebelumnya di root kini ada di
  `.local/backups/siwarga_db.sql`; pemindahan ini tidak membuat backup baru.
- `instance/`: unggahan privat dan berkas runtime, termasuk kunci maintenance.
- `test-results/`: screenshot, laporan, fixture benchmark, dan dump pra-migrasi.
  Pertahankan bukti yang dirujuk dokumen; arsipkan terpisah bila diperlukan
  untuk rilis. Direktori ini tidak dipindahkan oleh skrip cache.
- `.venv/`: environment Python yang digunakan `start.ps1`.

Untuk melihat cache yang bisa dibuang, lalu membersihkannya:

~~~powershell
./scripts/clean_cache.ps1 -WhatIf
./scripts/clean_cache.ps1
~~~

Skrip memindahkan direktori cache dari root dan direktori source proyek ke
`.local/archive/cache-<waktu>-<id>/`, dengan susunan path asal tetap tersimpan.
Pengarsipan dapat dibalik dan tidak membebaskan ruang disk. Python dan pytest
akan membuat cache kembali saat dibutuhkan. `.env`, `.local/`, `.venv/`,
`instance/`, `test-results/`, dan `.git/` tidak menjadi sumber pemindahan skrip.
Hentikan tes sebelum menjalankan pembersihan.

Perapian 23 November 2026 memindahkan dokumen dan dump SQL, mengarsipkan cache,
serta mengarsipkan installer `.local/mysql.zip` dan tiga direktori temporer
pytest lama ke `.local/archive/cleanup-2026-11-23/`. Seluruh 296 berkas hasil
ekstraksi installer cocok ukuran dan CRC dengan isi arsip. Instalasi MySQL
portabel tetap berada di `.local/mysql-8.4.13-winx64/`. Penghapusan permanen
ditolak kebijakan eksekusi; seluruh berkas dipertahankan melalui pengarsipan.
