# Kontrak HTTP SiWarga

Inventaris kode tanggal 10 November 2026. Ini aplikasi HTML server-rendered,
bukan REST API JSON umum. Jangan mengharapkan respons JSON dari formulir.
`<int:id>` adalah ID integer pada URL. GET otomatis mendukung HEAD; Flask
menyediakan OPTIONS. Aset publik dilayani melalui `/static/<path:filename>`.

## Autentikasi, akses, dan respons umum

- Autentikasi menggunakan cookie sesi bertanda tangan, bukan bearer token.
  Produksi wajib HTTPS, Secure, HttpOnly, SameSite=Lax, dan trusted hosts.
- Semua POST memerlukan CSRF, termasuk login/register/logout. Ambil token dari
  formulir GET menggunakan cookie jar yang sama; JSON memakai `X-CSRFToken`.
- Tanpa login, endpoint bersesi mengalihkan 302 ke login. Akun pending
  diarahkan ke halaman menunggu; akun dengan password sementara ke `/akun`.
  Sesi dicabut atau akun nonaktif memerlukan login ulang. Endpoint operasional
  tidak mewajibkan akun. CSRF yang tidak valid menghasilkan 400 sebelum aksi.
- Role di luar izin aksi mendapat 403. Data yang tidak ditemukan atau berada
  di luar scope mendapat 404. WARGA hanya melihat laporannya, RT wilayah RT/RW
  sendiri, RW wilayah RW sendiri, KARANG_TARUNA tugasnya dalam RW sendiri,
  SUPERADMIN semua laporan. Akses baca admin tidak memberi izin semua mutasi.
- Semua listing menerima `page` berupa digit ASCII 1-10000, default 1; invalid
  mendapat 400. Filter tidak dikenal tidak diteruskan ke tautan pagination.
- Form Flask-WTF tidak valid biasanya ditampilkan lagi dengan 200 dan pesan
  per field, bukan 422. Validasi aksi manual mendapat 400, konflik mendapat
  409, unggahan terlalu besar 413. Metode salah mendapat 405 dan header Allow.
- Kesalahan internal/DB menghasilkan 500 generik, bukan traceback/SQL pada
  halaman. Gunakan `X-Request-ID` untuk korelasi log privat. Host tidak
  diizinkan mendapat 400 teks biasa. Setiap respons memiliki security headers.

## Akun dan navigasi

| Metode | Endpoint | Akses | Input / hasil normal |
| --- | --- | --- | --- |
| GET | `/` | Publik | 200 landing; pengguna login diarahkan 302 ke dashboard. |
| GET | `/login` | Publik | 200 formulir; sudah login mendapat 302 dashboard. |
| POST | `/login` | Publik + CSRF | `email`, `password`; sukses 302 dashboard/menunggu; gagal 200 pesan generik, limit 429, backend limiter gagal 503. |
| GET | `/register` | Publik | 200 formulir pilihan wilayah. |
| POST | `/register` | Publik + CSRF | `nama`, `email`, `no_hp` opsional, `rw_id`, `rt_id`, `password`, `confirm`; sukses 302 menunggu; duplikat/invalid ditampilkan di formulir. |
| GET | `/menunggu-verifikasi` | Sesi | 200 pending; akun aktif diarahkan ke dashboard. |
| POST | `/logout` | Sesi + CSRF | Tanpa field bisnis; 302 login; mencabut semua sesi akun, termasuk cookie salinan. |
| GET | `/akun` | Sesi | 200 formulir ganti password. |
| POST | `/akun` | Sesi + CSRF | `current_password`, `password`, `confirm`; sukses 302 dashboard, sesi perangkat lain dicabut. |
| GET | `/dashboard` | Sesi aktif | 200 agregat, aktivitas, dan tiket sesuai scope. |

Password baru 10-128 karakter; konfirmasi harus cocok. Nama 2-100, email maksimal
190, nomor HP opsional maksimal 25 karakter dengan format angka/telepon.
RT registrasi harus berada di RW yang dipilih. Akun pengurus tidak dibuat dari
registrasi publik. Limiter login lima kegagalan/reservasi per akun dan 30 per IP
selama 15 menit, lintas-worker melalui Redis produksi. Identitas memakai email
tersimpan agar alias collation MySQL tidak memperoleh limit baru.

## Pengaduan dan foto

| Metode | Endpoint | Akses | Input / hasil normal |
| --- | --- | --- | --- |
| GET | `/pengaduan` | Sesi aktif, scope | `page`, `q`, `status`, `kategori`, `rt`, `dari`, `sampai`; 200 daftar. Status/tanggal invalid mendapat 400. |
| GET | `/pengaduan/baru` | WARGA aktif | 200 formulir dan submission_token. |
| POST | `/pengaduan` | WARGA aktif + CSRF | `submission_token`, `judul`, `kategori_id`, `lokasi_teks`, `deskripsi`, `foto` opsional; sukses/retry token sama 302 detail. |
| GET | `/pengaduan/<int:id>` | Sesi aktif, scope | 200 detail, histori, komentar, dan foto privat. |
| POST | `/pengaduan/<int:id>/verifikasi` | RT, scope + CSRF | `aksi=terima` atau `tolak`; tolak wajib `alasan` 10-3000; 302 detail, status bukan MENUNGGU_VERIFIKASI mendapat 409. |
| POST | `/pengaduan/<int:id>/tugaskan` | RT/RW, scope + CSRF | `petugas_id` KARANG_TARUNA aktif dalam RW laporan; 302 detail; status bukan DIPROSES mendapat 409. |
| POST | `/pengaduan/<int:id>/tindak-lanjut` | RT/RW/KARANG_TARUNA, scope + CSRF | `catatan` 10-3000, `foto` opsional; 302 detail; wajib DIPROSES. |
| POST | `/pengaduan/<int:id>/selesai` | RT/RW, scope + CSRF | `catatan` 10-3000, `foto` opsional; 302 detail; DIPROSES menjadi SELESAI, status lain 409. |
| POST | `/pengaduan/<int:id>/komentar` | WARGA/RT/RW/KARANG_TARUNA, scope + CSRF | `isi` 2-2000; 302 detail pada anchor diskusi. |
| GET | `/lampiran/<int:id>` | Sesi aktif, scope laporan | `variant=original` (default), `thumbnail`, atau `display`; 200 berkas, varian invalid 400, tidak ada/tidak berizin 404. |

`q` dipangkas 160 karakter. Status: MENUNGGU_VERIFIKASI, DIPROSES, SELESAI,
DITOLAK. Tanggal berformat YYYY-MM-DD adalah tanggal WIB; batas bawah harus
dapat diwakili MySQL dalam UTC (mulai 1000-01-02), sampai 9999-12-31. Batas
akhir inklusif untuk tanggal yang dipilih; query memakai awal hari berikutnya.

Judul 8-160, lokasi 5-255, deskripsi 20-5000 karakter, kategori harus aktif.
Submission token terikat akun dan berlaku 24 jam; retry yang sama tidak
mengubah isi laporan pertama. Unggah menggunakan multipart/form-data, maksimum
tiga foto per pengiriman, masing-masing 3 MiB, total request maksimum 11 MiB.
Format/resolusi/MIME divalidasi server dan metadata dibersihkan; jangan
menyediakan URL publik langsung ke direktori uploads. Lihat TECHNICAL untuk
budget thumbnail/display dan backfill foto lama. Respons foto private/no-store.

## Notifikasi dan verifikasi warga

| Metode | Endpoint | Akses | Input / hasil normal |
| --- | --- | --- | --- |
| GET | `/notifikasi` | Sesi aktif | `page`; 200 notifikasi milik sendiri. |
| POST | `/notifikasi/<int:id>/baca` | Pemilik notifikasi + CSRF | 302 tiket jika masih berizin; jika akses berubah kembali ke notifikasi dengan pesan aman; notifikasi tanpa tiket menuju verifikasi warga bagi RT. |
| POST | `/notifikasi/baca-semua` | Sesi aktif + CSRF | Menandai hanya notifikasi sendiri; 302 daftar. |
| GET | `/rt/verifikasi-warga` | RT aktif | `page`, `status=PENDING` (default), ACTIVE, INACTIVE; 200 warga RT/RW sendiri; status invalid 400. |
| POST | `/rt/verifikasi-warga/<int:id>` | RT aktif, warga wilayah sendiri + CSRF | `aksi=terima` atau `nonaktifkan`; 302 daftar; sesi warga dicabut dan audit disimpan. |

## Administrasi

Semua endpoint berikut hanya SUPERADMIN aktif. Semua POST memerlukan CSRF;
normalnya 302 ke listing, input invalid 400, objek tidak ada 404, konflik 409.
Akun SUPERADMIN tidak dapat diedit melalui pengelolaan pengurus (403).

| Metode | Endpoint | Akses | Input / hasil normal |
| --- | --- | --- | --- |
| GET | `/admin/wilayah` | SUPERADMIN | 200 daftar RW/RT. |
| POST | `/admin/rw` | SUPERADMIN + CSRF | `nomor`, `nama_wilayah`; 302 wilayah. |
| POST | `/admin/rw/<int:id>` | SUPERADMIN + CSRF | `nomor`, `nama_wilayah`; atau `aksi=hapus` jika tidak dipakai. |
| POST | `/admin/rt` | SUPERADMIN + CSRF | `rw_id`, `nomor`; 302 wilayah. |
| POST | `/admin/rt/<int:id>` | SUPERADMIN + CSRF | `nomor`; atau `aksi=hapus` jika tidak dipakai. |
| GET | `/admin/kategori` | SUPERADMIN | 200 daftar kategori. |
| POST | `/admin/kategori` | SUPERADMIN + CSRF | `nama`, `deskripsi` opsional; kategori baru aktif. |
| POST | `/admin/kategori/<int:id>` | SUPERADMIN + CSRF | `nama`, `deskripsi`, checkbox `aktif`; atau `aksi=hapus` jika tidak dipakai. |
| GET | `/admin/pengurus` | SUPERADMIN | `page`, `role` opsional; 200 daftar akun. |
| POST | `/admin/pengurus` | SUPERADMIN + CSRF | `nama`, `email`, `role`, `rw_id`, `rt_id` untuk RT, `password`; duplikat email 409 tanpa akun/audit parsial. |
| POST | `/admin/pengurus/<int:id>` | SUPERADMIN + CSRF | Field akun seperti pembuatan (password opsional), atau `aksi=toggle`; 302 daftar dan sesi target dicabut. |

Nomor wilayah 1-999, digit ASCII, disimpan minimal dua digit (`001` menjadi
`01`); nomor sama dalam scope yang sama konflik. Nama wilayah 3-120, nama
kategori 3-80, deskripsi kategori dipangkas 255 karakter. Pembuatan akun hanya
RW/RT/KARANG_TARUNA; warga memakai registrasi. Akun warga yang ada hanya dapat
tetap ber-role WARGA dengan RT/RW valid. Password baru/reset 10-128 karakter,
memerlukan penggantian saat login berikutnya. Penghapusan data yang direferensi
ditolak; nonaktifkan kategori/akun agar riwayat tetap utuh.

## Operasional dan telemetry

| Metode | Endpoint | Akses | Input / hasil normal |
| --- | --- | --- | --- |
| GET | `/health/live` | Publik, Host tepercaya | 200 JSON `{"status":"alive"}`; tidak memeriksa DB. |
| GET | `/health/ready` | Publik, Host tepercaya | 200 JSON `{"status":"ready"}`; DB/limiter/storage gagal 503 `{"status":"not_ready"}`. |
| GET | `/metrics` | Loopback saja | 200 teks Prometheus; alamat bukan loopback 404; Nginx wajib menolak publik. |
| POST | `/telemetry/vitals` | Sesi + CSRF | JSON persis `name`, `value`, `page`; 204 tanpa cookie baru; invalid 400, ukuran tidak ada/>2048 byte 413, dinonaktifkan 404. |

Telemetry: name LCP/INP/CLS, value angka finite nonnegatif (bukan boolean),
maksimum 100 untuk CLS dan 3.600.000 untuk yang lain. Page hanya
main.dashboard, tickets.index, tickets.detail, tickets.create, auth.login,
auth.account. Sesi tetap wajib walaupun auth.login berada dalam enum page.
Tidak menerima URL bebas/ID atau isi laporan. Cookie logout yang sudah dicabut
ditolak sebelum telemetry diproses; respons telemetry tidak menulis sesi.

## Contoh respons

Contoh berikut ilustrasi kontrak, bukan rekaman kredensial/ID live. Login atau
mutasi berhasil menggunakan redirect; jangan mengikuti redirect otomatis jika
ingin membedakan POST sukses dari formulir gagal yang juga memberi HTTP 200.

```http
POST /login HTTP/1.1
Content-Type: application/x-www-form-urlencoded
Cookie: session=<cookie-dari-GET-login>

csrf_token=<token-formulir>&email=warga%40example.org&password=<password>
```

```http
HTTP/1.1 302 FOUND
Location: /dashboard
Set-Cookie: session=<signed-session>; Secure; HttpOnly; Path=/; SameSite=Lax
```

```http
GET /health/ready HTTP/1.1
Host: siwarga.example.org

HTTP/1.1 200 OK
Content-Type: application/json

{"status":"ready"}
```

```http
POST /telemetry/vitals HTTP/1.1
Content-Type: application/json
X-CSRFToken: <token-formulir-sesi>
Cookie: session=<signed-session>

{"name":"LCP","value":1850,"page":"main.dashboard"}

HTTP/1.1 204 NO CONTENT
```

HTML error 400/403/404/409/500 ditampilkan dengan layout SiWarga, bukan objek
JSON. Host yang ditolak adalah pengecualian: 400 text/plain dengan pesan
`Host permintaan tidak diizinkan.`. Tes inventaris endpoint gagal jika route
aplikasi baru belum dicatat di dokumen ini (aset statis dikecualikan).
