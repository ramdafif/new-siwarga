# Deployment siwarga.elkyno.com

## Status deployment: 2 November 2026

Source branch `staging`, commit awal `d008470`, berada di
`/home/gajiku/app/elkyno/siwarga`. Deployment memakai VPS yang sudah ada,
bukan hosting Sites. Kode aplikasi tidak diubah.

Aplikasi, MySQL, Redis privat, backup lokal, dan HTTPS sudah berjalan.
Sertifikat Let's Encrypt untuk `siwarga.elkyno.com` berhasil diterbitkan,
berlaku sampai 31 Januari 2027. Simulasi renewal juga berhasil.

Delegasi registry `.com` sudah menunjuk `dakota.ns.cloudflare.com` dan
`maisie.ns.cloudflare.com`. Kedua authoritative nameserver dan Google DNS
mengembalikan IP VPS yang benar. Saat pemeriksaan, resolver `1.1.1.1` dan
resolver sistem VPS masih menyimpan hasil delegasi lama dan mengembalikan
`SERVFAIL`; propagasi/cache belum seragam. HTTPS berhasil diuji menggunakan
IP publik dengan SNI dan validasi sertifikat, serta melalui Google DNS-over-HTTPS.

Pada setup awal, registry sempat menunjuk `ns1.nonverifieddomain.com` dan
`ns2.nonverifieddomain.com`. Masalah delegasi tersebut sudah diperbaiki di
sisi pengelolaan domain. Jangan mengganti atau menghapus record layanan lain.

Record aktif di Cloudflare:

| Type | Name | Value | TTL |
| --- | --- | --- | --- |
| A | siwarga | 103.93.135.125 | 300 |

Record `siwarga` memakai DNS-only. Jangan menambahkan AAAA kecuali IPv6
VPS dan Nginx benar-benar dikonfigurasi untuk subdomain ini.

## Komponen server

- Python 3.12 dan dependency dari `requirements.lock` dalam `.venv` proyek.
- `siwarga.service`: Gunicorn, dua worker/two threads, `127.0.0.1:5010`.
- User sistem `siwarga`, tanpa shell login; source read-only untuk service.
- MySQL database `siwarga_production`, terpisah dari aplikasi lain.
- User database runtime hanya mendapat SELECT/INSERT/UPDATE/DELETE. Akun
  migrator dan backup terpisah dan terbatas pada database SiWarga.
- `siwarga-redis.service`: Redis berpassword, `127.0.0.1:6381`, batas 64 MB,
  terpisah dari Redis server yang sudah ada. Data limiter tidak dipersistenkan.
- `/etc/siwarga/app.env`, `migrator.env`, dan `backup.env`: root-only 0600.
- `/etc/siwarga/redis.conf`: root:siwarga 0640.
- `/var/lib/siwarga/uploads`: penyimpanan foto privat.
- `/etc/nginx/sites-available/siwarga.elkyno.com`: virtual host khusus.
- `/etc/siwarga/nginx-https.conf`: konfigurasi HTTPS siap aktivasi.

HTTP sekarang redirect ke HTTPS, kecuali path ACME yang digunakan untuk
renewal. Form login hanya dilayani melalui HTTPS. Gunicorn dan Redis tidak
mendengarkan pada interface publik. `/metrics` dan `/health/ready` diblokir
pada virtual host publik.

## Aktivasi ulang HTTPS dan renewal

Aktivasi awal sudah selesai; perintah aktivasi ulang berikut disimpan untuk
operasi berikutnya dan tidak perlu dijalankan lagi untuk membuka website.

Periksa DNS:

```bash
dig @1.1.1.1 siwarga.elkyno.com A +short
dig @8.8.8.8 siwarga.elkyno.com A +short
```

Keduanya harus mengembalikan IP VPS. Jalankan:

```bash
sudo /usr/local/sbin/siwarga-activate-https
```

Helper menolak DNS yang belum sesuai atau keberadaan AAAA yang belum
diverifikasi. Setelah lolos, helper meminta sertifikat Let's Encrypt melalui
webroot `/var/www/siwarga-acme`, memasang konfigurasi HTTPS, menjalankan
`nginx -t`, reload Nginx, dan menguji `/health/live` melalui HTTPS.
Jika validasi konfigurasi gagal, konfigurasi sebelumnya dipulihkan.

`certbot.timer` sudah aktif pada server. Sertifikat baru menggunakan deploy
hook untuk menguji dan reload Nginx setelah renewal. Setelah sertifikat
berhasil terbit, verifikasi renewal dan akses publik:

```bash
sudo certbot renew --cert-name siwarga.elkyno.com --dry-run --no-random-sleep-on-renew
curl --fail --show-error https://siwarga.elkyno.com/health/live
```

Konfigurasi memblokir `/metrics` dan `/health/ready` dari virtual host publik.
Untuk readiness internal:

```bash
curl --fail -H 'Host: siwarga.elkyno.com' http://127.0.0.1:5010/health/ready
```

## Akses admin pertama

Satu superadmin aktif dibuat dengan email `admin@siwarga.elkyno.com`, password
acak, dan kewajiban mengganti password saat login pertama. Kredensial awal
tersimpan di `/home/gajiku/.config/siwarga/initial-admin.txt`, milik `gajiku`
dengan mode 0600. Jangan menyalin password ke Git atau log. Setelah password
diganti, hapus salinan password awal tersebut.

Tidak ada akun demo, RW/RT fiktif, atau pengaduan contoh yang ditambahkan.
Admin perlu membuat wilayah, RT, kategori, serta akun pengurus yang benar
sebelum pendaftaran warga dapat digunakan.

## Operasi dan update

```bash
sudo systemctl status siwarga siwarga-redis --no-pager
sudo journalctl -u siwarga -n 100 --no-pager
sudo systemctl restart siwarga
sudo systemctl start siwarga-backup-local
```

Helper Flask memuat environment privat tanpa mencetaknya, lalu menjalankan
CLI sebagai user aplikasi. Kredensial migrator hanya dimuat untuk `db` dan
`upgrade-safe`:

```bash
sudo /usr/local/sbin/siwarga-manage db current
sudo /usr/local/sbin/siwarga-manage upgrade-safe
sudo /usr/local/sbin/siwarga-manage backfill-photos
```

Update berikutnya: backup terlebih dahulu, periksa perubahan branch dan
kompatibilitas schema, gunakan `git pull --ff-only origin staging`, pasang
dependency dari lockfile bila berubah, jalankan `upgrade-safe`, restart, dan
uji login/readiness. Jangan reset worktree atau downgrade database secara
otomatis. Saat ini checkout langsung dipakai service; untuk rilis atomik,
terapkan struktur release immutable pada `docs/OPERATIONS.md`.

Konfigurasi systemd, helper server, dan skrip pemeriksaan lokal juga tersedia
di `.local/deploy/` yang diabaikan Git. Sumber konfigurasi aktif tetap file
di `/etc/siwarga`, `/etc/systemd/system`, dan `/usr/local/sbin`.

## Backup dan batas kesiapan

`siwarga-backup-local.timer` aktif pukul 03:00 dan 15:00 Asia/Jakarta, dengan
jitter sampai satu menit. Backup menggunakan `scripts/backup.py`: dump
MySQL, import ke database khusus `siwarga_restore_test`, salin original foto
berdasarkan hasil import, lalu verifikasi checksum. Snapshot disimpan privat
di `/var/lib/siwarga/backups`; 14 snapshot sukses terakhir dipertahankan.
Database verifikasi bukan database aplikasi dan memakai akun berbeda.

Backup pertama berhasil dibuat dan diverifikasi. Ini **backup lokal saja**,
bukan perlindungan terhadap kehilangan VPS. Offsite backup/restic, penerima
alert, monitoring eksternal, dan latihan recovery penuh belum dikonfigurasi.
Siapkan semuanya dan persetujuan pengelola sebelum menerima data warga asli.

Pemeriksaan deployment yang sudah lolos:

- Dependency `pip check`, migrasi ke `bbb234424314`, dan readiness MySQL/Redis.
- Landing, login, registrasi, liveness, readiness, metrics internal, enam aset
  statis, serta dua belas request readiness bersamaan.
- Login admin dengan CSRF aktif, secure/HttpOnly/SameSite cookie, kewajiban
  mengganti password, logout, proteksi anonymous, CSRF tanpa token, dan 404.
- `nginx -t`, syntax template HTTPS memakai sertifikat induk hanya untuk
  validasi syntax, serta syntax shell/unit service.
- Respons virtual host aplikasi lain tetap sama setelah reload Nginx.

Penerbitan sertifikat, renewal dry-run, redirect HTTP, halaman landing/login,
aset statis, serta blokir metrics/readiness pada HTTPS sudah diverifikasi.
Login admin juga diuji melalui HTTPS asli dengan validasi sertifikat, HSTS,
CSRF aktif, secure cookie, kewajiban ganti password, dan logout. Resolver publik
belum seragam seperti dijelaskan pada status deployment. Full test suite belum
dijalankan. Ditemukan bug existing: Host yang tidak tepercaya pada
backend langsung menghasilkan 500, bukan 400, karena error template memanggil
`url_for` tanpa URL adapter. Tidak ada patch aplikasi untuk isu tersebut;
backend hanya loopback dan Nginx meneruskan host virtual host yang valid.
