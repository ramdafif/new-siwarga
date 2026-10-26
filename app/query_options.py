from sqlalchemy.orm import contains_eager, joinedload, load_only, raiseload

from .models import Kategori, Pengaduan, RT, RW


def summary_options():
    return (load_only(Pengaduan.id, Pengaduan.nomor_tiket, Pengaduan.kategori_id, Pengaduan.rt_id,
                      Pengaduan.judul, Pengaduan.status, Pengaduan.created_at, raiseload=True),
            raiseload(Pengaduan.lampiran), raiseload(Pengaduan.riwayat), raiseload(Pengaduan.progres),
            raiseload(Pengaduan.komentar), raiseload(Pengaduan.pelapor), raiseload(Pengaduan.ditugaskan_ke),
            contains_eager(Pengaduan.rt).load_only(RT.id, RT.nomor, RT.rw_id)
                .joinedload(RT.rw).load_only(RW.id, RW.nomor),
            joinedload(Pengaduan.kategori).load_only(Kategori.id, Kategori.nama))
