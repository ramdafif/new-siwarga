# ERD SiWarga

Semua data utama disimpan di MySQL 8 menggunakan InnoDB/utf8mb4. Primary key
berupa integer auto-increment; waktu disimpan UTC. Sepuluh tabel bisnis awal
ditambah audit_event pada migrasi penguatan. Tabel `alembic_version` adalah metadata migrasi,
bukan tabel bisnis tambahan.

## Relasi

~~~mermaid
erDiagram
    rw ||--o{ rt : memiliki
    rw ||--o{ users : menaungi
    rt ||--o{ users : beranggotakan
    rt ||--o{ pengaduan : berlokasi
    users ||--o{ pengaduan : melaporkan
    users o|--o{ pengaduan : ditugaskan
    kategori_pengaduan ||--o{ pengaduan : mengelompokkan
    pengaduan ||--o{ lampiran : memiliki
    users ||--o{ lampiran : mengunggah
    pengaduan ||--o{ tindak_lanjut : ditangani
    users ||--o{ tindak_lanjut : mencatat
    pengaduan ||--o{ riwayat_status : diaudit
    users ||--o{ riwayat_status : bertindak
    pengaduan ||--o{ komentar : didiskusikan
    users ||--o{ komentar : menulis
    users ||--o{ notifikasi : menerima
    pengaduan o|--o{ notifikasi : terkait
~~~

## Tabel dan kolom

1. **`rw`**: PK `id`; `nomor` VARCHAR(8) unik; `nama_wilayah`
   VARCHAR(120); `created_at`. Satu RW memiliki banyak RT dan pengguna.
2. **`rt`**: PK `id`; FK `rw_id -> rw.id`; `nomor` VARCHAR(8);
   `created_at`. Pasangan `(rw_id, nomor)` unik, sehingga RT 01 boleh ada pada
   beberapa RW tanpa bertabrakan.
3. **`users`**: PK `id`; FK nullable `rw_id -> rw.id`, `rt_id -> rt.id`;
   `nama`, `email` unik, `no_hp` opsional, `password_hash`, `role`, `status`,
   `must_change_password`, `session_version` (default 1), `created_at`. Role dan status menggunakan ENUM.
   Check constraint mengharuskan wilayah sesuai role: SUPERADMIN tanpa
   RW/RT, RW/KARANG_TARUNA dengan RW tanpa RT, RT/WARGA dengan keduanya.
   Kecocokan RT dalam RW divalidasi server pada registrasi/pengelolaan akun.
   RT tidak dapat dipindahkan RW melalui UI agar hubungan wilayah tidak rusak.
4. **`kategori_pengaduan`**: PK `id`; `nama` unik; `deskripsi` opsional;
   `aktif`. Kategori nonaktif tetap dipertahankan untuk riwayat lama, tetapi
   tidak dapat dipilih pada laporan baru.
5. **`pengaduan`**: PK `id`; `nomor_tiket` unik; FK `pelapor_id -> users.id`,
   `rt_id -> rt.id`, `kategori_id -> kategori_pengaduan.id`; FK nullable
   `ditugaskan_ke_id -> users.id`; `judul`, `deskripsi`, `lokasi_teks`,
   `status`, `alasan_penolakan` opsional, `created_at`, `updated_at`,
   `selesai_at` opsional; `submission_token` nullable dengan unique constraint
   `(pelapor_id, submission_token)` untuk retry formulir. Dua relasi ke User memakai `foreign_keys` eksplisit.
   RW tiket diturunkan dari RT, tidak disalin, agar tidak ada dua sumber wilayah.
6. **`lampiran`**: PK `id`; FK `pengaduan_id -> pengaduan.id`,
   `uploader_id -> users.id`; `nama_asli`, `nama_tersimpan` unik (UUID),
   `jenis` ENUM LAPORAN/PROGRES/PENYELESAIAN, `created_at`. Hanya metadata yang
   disimpan di MySQL; byte foto berada pada penyimpanan privat.
7. **`tindak_lanjut`**: PK `id`; FK `pengaduan_id -> pengaduan.id`,
   `petugas_id -> users.id`; `catatan`, `created_at`. Menyimpan catatan progres
   petugas tanpa memberi Karang Taruna izin menutup tiket.
8. **`riwayat_status`**: PK `id`; FK `pengaduan_id -> pengaduan.id`,
   `aktor_id -> users.id`; `status_lama` nullable, `status_baru`, `catatan`
   nullable, `created_at`. Riwayat pertama memiliki status lama NULL.
   Penugasan/progres juga dicatat dengan status lama sama dengan status baru.
9. **`komentar`**: PK `id`; FK `pengaduan_id -> pengaduan.id`,
   `user_id -> users.id`; `isi`, `created_at`. Diskusi tidak mengubah status.
10. **`notifikasi`**: PK `id`; FK `user_id -> users.id`; FK nullable
    `pengaduan_id -> pengaduan.id`; `pesan`, `sudah_dibaca`, `created_at`.
    Notifikasi akun dapat ada tanpa tiket. Penyaringan selalu menurut penerima.

11. **`audit_event`**: PK id; actor_id/target_id nullable (referensi logis,
    tanpa FK); event, outcome, request_id, details JSON, created_at dengan indeks.
    Audit perubahan akun disimpan dalam transaksi administratif yang sama.

Semua kolom inti NOT NULL kecuali yang disebut opsional/nullable. FK tidak
menggunakan penghapusan cascade: laporan dan audit bukan data yang boleh ikut
terhapus ketika akun dinonaktifkan. Penghapusan wilayah/kategori yang digunakan
ditolak backend maupun FK. Akun tidak dihapus melalui aplikasi.

## Indeks dan konsistensi

- `pengaduan`: indeks `rt_id`, `pelapor_id`, `kategori_id`, `status`,
  `created_at`, `ditugaskan_ke_id`; nomor tiket unik.
- `users`: indeks `rw_id`, `rt_id`, `role`, `status`; email unik dan dinormalisasi
  ke huruf kecil pada semua jalur input.
- FK pada tabel anak diindeks untuk pencarian riwayat/lampiran/progres/komentar.
  Notifikasi juga memiliki indeks penerima dan flag sudah dibaca.
- Wilayah, penugasan aktif, role, dan state machine diperiksa lagi pada setiap
  tindakan backend; constraint database bukan pengganti otorisasi.
- Mutasi status/penugasan/progres memakai `SELECT ... FOR UPDATE`, kemudian
  status + audit + notifikasi di-commit bersama. Hal ini mencegah status final
  dibuka ulang akibat permintaan berulang atau bersamaan.

Desain sengaja sederhana: satu anggota Karang Taruna per tiket, satu kategori,
satu RT asal, relasi 1:N untuk bukti/riwayat/diskusi; tidak ada repository layer,
tabel role, atau tabel workflow tambahan yang tidak dibutuhkan MVP.
