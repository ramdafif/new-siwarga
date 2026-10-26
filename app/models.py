from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData
from werkzeug.security import check_password_hash, generate_password_hash

from .constants import ROLES, STATUSES, USER_STATUSES

db = SQLAlchemy(metadata=MetaData(naming_convention={
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}))


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AuditEvent(db.Model):
    __tablename__ = "audit_event"
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer)
    target_id = db.Column(db.Integer)
    event = db.Column(db.String(60), nullable=False)
    outcome = db.Column(db.String(16), nullable=False)
    request_id = db.Column(db.String(32), nullable=False)
    details = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

class RW(db.Model):
    __tablename__ = "rw"
    id = db.Column(db.Integer, primary_key=True)
    nomor = db.Column(db.String(8), nullable=False, unique=True)
    nama_wilayah = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    rts = db.relationship("RT", back_populates="rw", lazy="select")


class RT(db.Model):
    __tablename__ = "rt"
    __table_args__ = (db.UniqueConstraint("rw_id", "nomor"),)
    id = db.Column(db.Integer, primary_key=True)
    rw_id = db.Column(db.Integer, db.ForeignKey("rw.id"), nullable=False, index=True)
    nomor = db.Column(db.String(8), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    rw = db.relationship("RW", back_populates="rts")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.CheckConstraint(
            "(role = 'SUPERADMIN' AND rw_id IS NULL AND rt_id IS NULL) OR "
            "(role IN ('RW', 'KARANG_TARUNA') AND rw_id IS NOT NULL AND rt_id IS NULL) OR "
            "(role IN ('RT', 'WARGA') AND rw_id IS NOT NULL AND rt_id IS NOT NULL)",
            name="user_scope",
        ),
    )
    id = db.Column(db.Integer, primary_key=True)
    rw_id = db.Column(db.Integer, db.ForeignKey("rw.id"), index=True)
    rt_id = db.Column(db.Integer, db.ForeignKey("rt.id"), index=True)
    nama = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(190), nullable=False, unique=True)
    no_hp = db.Column(db.String(25))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(*ROLES, name="user_role"), nullable=False, index=True)
    status = db.Column(db.Enum(*USER_STATUSES, name="user_status"), nullable=False, default="PENDING", index=True)
    must_change_password = db.Column(db.Boolean, nullable=False, default=False)
    session_version = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    rw = db.relationship("RW", foreign_keys=[rw_id], lazy="joined")
    rt = db.relationship("RT", foreign_keys=[rt_id], lazy="joined")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def initials(self):
        return "".join(part[0] for part in self.nama.split()[:2]).upper()


class Kategori(db.Model):
    __tablename__ = "kategori_pengaduan"
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(80), nullable=False, unique=True)
    deskripsi = db.Column(db.String(255))
    aktif = db.Column(db.Boolean, nullable=False, default=True)


class Pengaduan(db.Model):
    __tablename__ = "pengaduan"
    __table_args__ = (db.UniqueConstraint("pelapor_id", "submission_token", name="uq_pengaduan_submission"),)
    id = db.Column(db.Integer, primary_key=True)
    nomor_tiket = db.Column(db.String(30), nullable=False, unique=True)
    submission_token = db.Column(db.String(64))
    pelapor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    rt_id = db.Column(db.Integer, db.ForeignKey("rt.id"), nullable=False, index=True)
    kategori_id = db.Column(db.Integer, db.ForeignKey("kategori_pengaduan.id"), nullable=False, index=True)
    ditugaskan_ke_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    judul = db.Column(db.String(160), nullable=False)
    deskripsi = db.Column(db.Text, nullable=False)
    lokasi_teks = db.Column(db.String(255), nullable=False)
    status = db.Column(db.Enum(*STATUSES, name="ticket_status"), nullable=False, default="MENUNGGU_VERIFIKASI", index=True)
    alasan_penolakan = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    selesai_at = db.Column(db.DateTime)
    pelapor = db.relationship("User", foreign_keys=[pelapor_id], lazy="joined")
    ditugaskan_ke = db.relationship("User", foreign_keys=[ditugaskan_ke_id], lazy="joined")
    rt = db.relationship("RT", lazy="joined")
    kategori = db.relationship("Kategori", lazy="joined")
    lampiran = db.relationship("Lampiran", back_populates="pengaduan", lazy="selectin", order_by="Lampiran.created_at")
    riwayat = db.relationship("RiwayatStatus", back_populates="pengaduan", lazy="selectin", order_by="RiwayatStatus.created_at")
    progres = db.relationship("TindakLanjut", back_populates="pengaduan", lazy="selectin", order_by="TindakLanjut.created_at")
    komentar = db.relationship("Komentar", back_populates="pengaduan", lazy="selectin", order_by="Komentar.created_at")


class Lampiran(db.Model):
    __tablename__ = "lampiran"
    id = db.Column(db.Integer, primary_key=True)
    pengaduan_id = db.Column(db.Integer, db.ForeignKey("pengaduan.id"), nullable=False, index=True)
    uploader_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    nama_asli = db.Column(db.String(255), nullable=False)
    nama_tersimpan = db.Column(db.String(80), nullable=False, unique=True)
    jenis = db.Column(db.Enum("LAPORAN", "PROGRES", "PENYELESAIAN", name="attachment_kind"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    pengaduan = db.relationship("Pengaduan", back_populates="lampiran")


class TindakLanjut(db.Model):
    __tablename__ = "tindak_lanjut"
    id = db.Column(db.Integer, primary_key=True)
    pengaduan_id = db.Column(db.Integer, db.ForeignKey("pengaduan.id"), nullable=False, index=True)
    petugas_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    catatan = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    petugas = db.relationship("User", lazy="joined")
    pengaduan = db.relationship("Pengaduan", back_populates="progres")


class RiwayatStatus(db.Model):
    __tablename__ = "riwayat_status"
    id = db.Column(db.Integer, primary_key=True)
    pengaduan_id = db.Column(db.Integer, db.ForeignKey("pengaduan.id"), nullable=False, index=True)
    aktor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status_lama = db.Column(db.String(30))
    status_baru = db.Column(db.String(30), nullable=False)
    catatan = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    aktor = db.relationship("User", lazy="joined")
    pengaduan = db.relationship("Pengaduan", back_populates="riwayat")


class Komentar(db.Model):
    __tablename__ = "komentar"
    id = db.Column(db.Integer, primary_key=True)
    pengaduan_id = db.Column(db.Integer, db.ForeignKey("pengaduan.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    isi = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    user = db.relationship("User", lazy="joined")
    pengaduan = db.relationship("Pengaduan", back_populates="komentar")


class Notifikasi(db.Model):
    __tablename__ = "notifikasi"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    pengaduan_id = db.Column(db.Integer, db.ForeignKey("pengaduan.id"), index=True)
    pesan = db.Column(db.String(255), nullable=False)
    sudah_dibaca = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
