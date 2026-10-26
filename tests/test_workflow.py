from io import BytesIO

import pytest
from sqlalchemy import func, select

from app.models import Lampiran, Notifikasi, Pengaduan, RiwayatStatus, TindakLanjut, db
from test_permissions import payload, photo


def test_full_warga_rt_karang_taruna_rw_workflow(client, login, data):
    login("owner")
    values = payload(data)
    values["foto"] = (photo(), "awal.png", "image/png")
    values["rt_id"] = data["outside_rt"].id
    response = client.post("/pengaduan", data=values, content_type="multipart/form-data")
    assert response.status_code == 302
    ticket = db.session.scalar(select(Pengaduan).order_by(Pengaduan.id.desc()).limit(1))
    assert ticket.rt_id == data["rt"].id
    assert ticket.nomor_tiket.startswith("SW-")
    assert ticket.status == "MENUNGGU_VERIFIKASI"
    ticket_id = ticket.id
    client.post("/logout")
    login("rt")
    assert client.post(f"/pengaduan/{ticket_id}/verifikasi", data={"aksi": "terima"}).status_code == 302
    assert client.post(f"/pengaduan/{ticket_id}/tugaskan", data={"petugas_id": data["users"]["kt"].id}).status_code == 302
    client.post("/logout")
    login("kt")
    assert client.get(f"/pengaduan/{ticket_id}").status_code == 200
    assert client.post(f"/pengaduan/{ticket_id}/tindak-lanjut", data={"catatan": "Selokan sudah dibersihkan bersama warga.",
        "foto": (photo(), "progres.png", "image/png")}, content_type="multipart/form-data").status_code == 302
    assert client.post(f"/pengaduan/{ticket_id}/selesai", data={"catatan": "Karang Taruna tidak boleh menutup tiket."}).status_code == 403
    client.post("/logout")
    login("rw")
    assert b"Selokan sudah dibersihkan" in client.get(f"/pengaduan/{ticket_id}").data
    assert client.post(f"/pengaduan/{ticket_id}/selesai", data={"catatan": "Aliran air sudah lancar dan lokasi diperiksa kembali."}).status_code == 302
    client.post("/logout")
    login("owner")
    page = client.get(f"/pengaduan/{ticket_id}")
    assert page.status_code == 200
    assert b"Aliran air sudah lancar" in page.data
    assert client.post(f"/pengaduan/{ticket_id}/komentar", data={"isi": "Terima kasih pengurus dan Karang Taruna!"}).status_code == 302
    db.session.expire_all()
    saved = db.session.get(Pengaduan, ticket_id)
    assert saved.status == "SELESAI"
    assert saved.selesai_at is not None
    assert len(saved.riwayat) == 5
    assert len(saved.lampiran) == 2
    assert db.session.scalar(select(func.count()).select_from(TindakLanjut).where(TindakLanjut.pengaduan_id == ticket_id)) == 1
    assert db.session.scalar(select(func.count()).select_from(Notifikasi).where(Notifikasi.user_id == data["users"]["owner"].id)) >= 4


@pytest.mark.parametrize("filename,content,mimetype", [
    ("malware.exe", b"not an image", "application/octet-stream"),
    ("fake.png", b"this is text", "image/png"),
    ("wrong.jpg", None, "image/jpeg"),
    ("wrong.png", None, "text/html"),
    ("large.png", b"x" * (3 * 1024 * 1024 + 1), "image/png"),
], ids=["extension", "corrupt", "format-mismatch", "mime-mismatch", "oversize"])
def test_invalid_upload_rejected_without_partial_ticket(client, login, data, filename, content, mimetype):
    login("owner")
    before = db.session.scalar(select(func.count()).select_from(Pengaduan))
    values = payload(data)
    values["foto"] = (photo() if content is None else BytesIO(content), filename, mimetype)
    response = client.post("/pengaduan", data=values, content_type="multipart/form-data")
    assert response.status_code == 400
    assert db.session.scalar(select(func.count()).select_from(Pengaduan)) == before
    assert db.session.scalar(select(func.count()).select_from(Lampiran)) == 0


def test_more_than_three_photos_rejected(client, login, data):
    login("owner")
    values = payload(data)
    values["foto"] = [(photo(), f"photo-{index}.png", "image/png") for index in range(4)]
    assert client.post("/pengaduan", data=values, content_type="multipart/form-data").status_code == 400
    assert db.session.scalar(select(func.count()).select_from(Lampiran)) == 0


def test_filters_and_invalid_dates(client, login, data):
    login("owner")
    response = client.get("/pengaduan?status=DIPROSES&q=assigned")
    assert response.status_code == 200
    assert data["tickets"]["waiting"].judul not in response.data.decode()
    assert client.get("/pengaduan?dari=not-a-date").status_code == 400
    assert client.get("/pengaduan?status=ILLEGAL").status_code == 400


def test_admin_crud_regions_categories_and_accounts(client, login, data):
    from app.models import Kategori, RT, RW, User

    login("admin")
    assert client.post("/admin/rw", data={"nomor": "03", "nama_wilayah": "Lingkungan Baru"}).status_code == 302
    rw = db.session.scalar(select(RW).where(RW.nomor == "03"))
    assert client.post("/admin/rt", data={"rw_id": rw.id, "nomor": "01"}).status_code == 302
    rt = db.session.scalar(select(RT).where(RT.rw_id == rw.id))
    assert client.post("/admin/kategori", data={"nama": "Keamanan Lingkungan", "deskripsi": "Fasilitas keamanan umum."}).status_code == 302
    category = db.session.scalar(select(Kategori).where(Kategori.nama == "Keamanan Lingkungan"))
    assert client.post(f"/admin/kategori/{category.id}", data={"nama": category.nama, "deskripsi": "Diubah"}).status_code == 302
    db.session.refresh(category)
    assert not category.aktif
    assert client.post("/admin/pengurus", data={"nama": "Ketua RT Baru", "email": "newrt@example.com", "role": "RT",
        "rw_id": rw.id, "rt_id": rt.id, "password": "NewOfficer123!"}).status_code == 302
    user = db.session.scalar(select(User).where(User.email == "newrt@example.com"))
    assert user.must_change_password
    assert user.check_password("NewOfficer123!")
    assert client.post(f"/admin/pengurus/{user.id}", data={"aksi": "toggle"}).status_code == 302
    db.session.refresh(user)
    assert user.status == "INACTIVE"
    assert client.post(f"/admin/rw/{rw.id}", data={"aksi": "hapus"}).status_code == 409


def test_trimmed_short_content_and_inactive_category_rejected(client, login, data):
    login("owner")
    before = db.session.scalar(select(func.count()).select_from(Pengaduan))
    values = payload(data)
    values["judul"] = "   satu   "
    response = client.post("/pengaduan", data=values)
    assert response.status_code == 200
    assert b"8-160 karakter" in response.data
    values = payload(data)
    data["category"].aktif = False
    db.session.commit()
    response = client.post("/pengaduan", data=values)
    assert response.status_code == 200
    assert b"Pilihan tidak valid" in response.data
    assert db.session.scalar(select(func.count()).select_from(Pengaduan)) == before


def test_admin_can_edit_and_delete_unused_region_and_category(client, login):
    from app.models import Kategori, RT, RW

    login("admin")
    client.post("/admin/rw", data={"nomor": "03", "nama_wilayah": "Wilayah Baru"})
    rw = db.session.scalar(select(RW).where(RW.nomor == "03"))
    assert client.post(f"/admin/rw/{rw.id}", data={"nomor": "04", "nama_wilayah": "Wilayah Diperbarui"}).status_code == 302
    client.post("/admin/rt", data={"rw_id": rw.id, "nomor": "01"})
    rt = db.session.scalar(select(RT).where(RT.rw_id == rw.id))
    assert client.post(f"/admin/rt/{rt.id}", data={"nomor": "02"}).status_code == 302
    assert client.post(f"/admin/rt/{rt.id}", data={"aksi": "hapus"}).status_code == 302
    assert client.post(f"/admin/rw/{rw.id}", data={"aksi": "hapus"}).status_code == 302
    client.post("/admin/kategori", data={"nama": "Kategori Belum Digunakan"})
    category = db.session.scalar(select(Kategori).where(Kategori.nama == "Kategori Belum Digunakan"))
    assert client.post(f"/admin/kategori/{category.id}", data={"aksi": "hapus"}).status_code == 302
