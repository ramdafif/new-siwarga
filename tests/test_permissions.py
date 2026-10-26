from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.models import Lampiran, Notifikasi, Pengaduan, RiwayatStatus, User, db
from app.security import issue_submission_token


def photo():
    stream = BytesIO()
    Image.new("RGB", (8, 8), "#4d8a68").save(stream, "PNG")
    stream.seek(0)
    return stream


def payload(data):
    return {"submission_token": issue_submission_token(data["users"]["owner"].id), "judul": "Saluran air tersumbat di Jalan Melati", "kategori_id": data["category"].id,
            "lokasi_teks": "Depan pos ronda Jalan Melati", "deskripsi": "Saluran air dipenuhi daun dan perlu dibersihkan agar tidak meluap saat hujan."}


@pytest.mark.parametrize("handle,visible,hidden", [
    ("owner", "waiting", "other"),
    ("rt", "waiting", "neighbor"),
    ("rt", "waiting", "outside"),
    ("rw", "neighbor", "outside"),
    ("kt", "assigned", "unassigned"),
    ("other_kt", None, "assigned"),
])
def test_ticket_scope_on_list_and_direct_url(client, login, data, handle, visible, hidden):
    login(handle)
    if visible:
        assert client.get(f"/pengaduan/{data['tickets'][visible].id}").status_code == 200
    assert client.get(f"/pengaduan/{data['tickets'][hidden].id}").status_code == 404
    listing = client.get("/pengaduan").data.decode()
    assert data["tickets"][hidden].judul not in listing
    dashboard = client.get("/dashboard").data.decode()
    assert data["tickets"][hidden].judul not in dashboard


def test_superadmin_global_read_only(client, login, data):
    login("admin")
    assert client.get(f"/pengaduan/{data['tickets']['outside'].id}").status_code == 200
    for action in ("verifikasi", "tugaskan", "tindak-lanjut", "selesai", "komentar"):
        assert client.post(f"/pengaduan/{data['tickets']['assigned'].id}/{action}").status_code == 403


@pytest.mark.parametrize("handle,action", [("owner", "verifikasi"), ("rw", "verifikasi"),
    ("kt", "verifikasi"), ("kt", "tugaskan"), ("kt", "selesai"), ("owner", "selesai")])
def test_disallowed_actions(client, login, data, handle, action):
    login(handle)
    assert client.post(f"/pengaduan/{data['tickets']['assigned'].id}/{action}", data={"catatan": "Tindakan yang tidak diizinkan."}).status_code == 403


def test_rt_cannot_mutate_other_rt_ticket(client, login, data):
    login("rt")
    assert client.post(f"/pengaduan/{data['tickets']['neighbor'].id}/verifikasi", data={"aksi": "terima"}).status_code == 404
    assert data["tickets"]["neighbor"].status == "MENUNGGU_VERIFIKASI"


@pytest.mark.parametrize("handle", ["owner", "rw", "rt", "kt"])
def test_admin_pages_and_actions_require_admin(client, login, handle):
    login(handle)
    assert client.get("/admin/wilayah").status_code == 403
    assert client.post("/admin/rw", data={"nomor": "99", "nama_wilayah": "Wilayah terlarang"}).status_code == 403
    assert client.get("/admin/pengurus").status_code == 403


def test_cross_rw_assignment_rejected(client, login, data):
    login("rt")
    ticket = data["tickets"]["assigned"]
    response = client.post(f"/pengaduan/{ticket.id}/tugaskan", data={"petugas_id": data["users"]["outside_kt"].id})
    assert response.status_code == 400
    db.session.refresh(ticket)
    assert ticket.ditugaskan_ke_id == data["users"]["kt"].id


def test_reassignment_revokes_former_assignee_access(client, login, data):
    login("rt")
    ticket = data["tickets"]["assigned"]
    assert client.post(f"/pengaduan/{ticket.id}/tugaskan", data={"petugas_id": data["users"]["other_kt"].id}).status_code == 302
    client.post("/logout")
    login("kt")
    assert client.get(f"/pengaduan/{ticket.id}").status_code == 404
    assert client.post(f"/pengaduan/{ticket.id}/tindak-lanjut", data={"catatan": "Tidak boleh menulis progres lama."}).status_code == 404


def test_protected_photo_only_ticket_viewers(client, login, data):
    login("owner")
    values = payload(data)
    values["foto"] = (photo(), "bukti.png", "image/png")
    assert client.post("/pengaduan", data=values, content_type="multipart/form-data").status_code == 302
    attachment = db.session.scalar(select(Lampiran))
    response = client.get(f"/lampiran/{attachment.id}")
    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert "no-store" in response.headers["Cache-Control"]
    assert attachment.nama_tersimpan != attachment.nama_asli
    client.post("/logout")
    login("other")
    assert client.get(f"/lampiran/{attachment.id}").status_code == 404
    assert client.get("/static/uploads/" + attachment.nama_tersimpan).status_code == 404


def test_notification_access_is_personal(client, login, data):
    notification = Notifikasi(user_id=data["users"]["other"].id, pesan="Pesan pribadi yang tidak boleh bocor")
    db.session.add(notification)
    db.session.commit()
    login("owner")
    assert b"Pesan pribadi yang tidak boleh bocor" not in client.get("/notifikasi").data
    assert client.post(f"/notifikasi/{notification.id}/baca").status_code == 404
    client.post("/notifikasi/baca-semua")
    db.session.refresh(notification)
    assert not notification.sudah_dibaca


@pytest.mark.parametrize("action,values", [
    ("verifikasi", {"aksi": "terima"}),
    ("tugaskan", {"petugas_id": "1"}),
    ("tindak-lanjut", {"catatan": "Progres yang tidak boleh masuk."}),
    ("selesai", {"catatan": "Belum boleh diselesaikan."}),
])
def test_illegal_transitions_are_rejected(client, login, data, action, values):
    login("rt")
    ticket = data["tickets"]["completed"]
    before = db.session.scalar(select(func.count()).select_from(RiwayatStatus))
    assert client.post(f"/pengaduan/{ticket.id}/{action}", data=values).status_code == 409
    db.session.refresh(ticket)
    assert ticket.status == "SELESAI"
    assert db.session.scalar(select(func.count()).select_from(RiwayatStatus)) == before


def test_cannot_finish_before_verification(client, login, data):
    login("rt")
    assert client.post(f"/pengaduan/{data['tickets']['waiting'].id}/selesai", data={"catatan": "Melewati verifikasi tidak boleh."}).status_code == 409


def test_rejection_requires_reason(client, login, data):
    login("rt")
    ticket = data["tickets"]["waiting"]
    assert client.post(f"/pengaduan/{ticket.id}/verifikasi", data={"aksi": "tolak", "alasan": ""}).status_code == 400
    db.session.refresh(ticket)
    assert ticket.status == "MENUNGGU_VERIFIKASI"
    assert client.post(f"/pengaduan/{ticket.id}/verifikasi", data={"aksi": "tolak", "alasan": "Laporan di luar kewenangan fasilitas umum."}).status_code == 302
    db.session.refresh(ticket)
    assert ticket.status == "DITOLAK"
    assert ticket.alasan_penolakan


@pytest.mark.parametrize("route", ["verifikasi", "tugaskan", "tindak-lanjut", "selesai", "komentar"])
def test_important_actions_require_csrf(app, client, login, data, route):
    login("rt")
    app.config["WTF_CSRF_ENABLED"] = True
    assert client.post(f"/pengaduan/{data['tickets']['assigned'].id}/{route}", data={"catatan": "Tanpa token tidak boleh disimpan."}).status_code == 400


def test_admin_rejects_mismatched_user_region(client, login, data):
    login("admin")
    response = client.post("/admin/pengurus", data={"nama": "Pengurus Tidak Valid", "email": "badrt@example.com",
        "role": "RT", "rw_id": data["rw"].id, "rt_id": data["outside_rt"].id, "password": "ValidPassword123!"})
    assert response.status_code == 400
    assert db.session.scalar(select(User.id).where(User.email == "badrt@example.com")) is None


def test_csrf_required_for_logout_and_admin_changes(app, client, login):
    login("admin")
    app.config["WTF_CSRF_ENABLED"] = True
    assert client.post("/logout").status_code == 400
    assert client.post("/admin/rw", data={"nomor": "03", "nama_wilayah": "Tanpa token"}).status_code == 400


def test_inactive_member_cannot_be_assigned(client, login, data):
    login("rt")
    member = data["users"]["other_kt"]
    member.status = "INACTIVE"
    db.session.commit()
    assert client.post(f"/pengaduan/{data['tickets']['assigned'].id}/tugaskan", data={"petugas_id": member.id}).status_code == 400


def test_rw_cannot_mutate_another_rw_ticket(client, login, data):
    login("rw")
    assert client.post(f"/pengaduan/{data['tickets']['outside'].id}/tindak-lanjut", data={"catatan": "Tidak boleh menjangkau wilayah lain."}).status_code == 404


def test_comment_content_is_html_escaped(client, login, data):
    login("owner")
    ticket_id = data["tickets"]["waiting"].id
    assert client.post(f"/pengaduan/{ticket_id}/komentar", data={"isi": "<script>alert('xss')</script>"}).status_code == 302
    page = client.get(f"/pengaduan/{ticket_id}").data
    assert b"&lt;script&gt;" in page
    assert b"<script>alert(" not in page
