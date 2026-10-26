import re

import pytest
from sqlalchemy import select

from app.models import User, db
from conftest import PASSWORD


def test_password_is_hashed(data):
    user = data["users"]["owner"]
    assert user.password_hash != PASSWORD
    assert user.check_password(PASSWORD)
    assert not user.check_password("incorrect-password")


def test_login_invalid_and_valid(client, data):
    response = client.post("/login", data={"email": data["users"]["owner"].email, "password": "wrong"})
    assert response.status_code == 200
    assert b"tidak sesuai" in response.data
    response = client.post("/login", data={"email": data["users"]["owner"].email, "password": PASSWORD})
    assert response.status_code == 302
    assert response.location.endswith("/dashboard")


def test_login_throttled(client, data):
    for unused_attempt in range(5):
        assert client.post("/login", data={"email": "owner@example.com", "password": "wrong"}).status_code == 200
    assert client.post("/login", data={"email": "owner@example.com", "password": PASSWORD}).status_code == 429


def test_pending_cannot_create_or_read_tickets(client, login, data):
    login("pending")
    for url in ("/dashboard", "/pengaduan/baru", f"/pengaduan/{data['tickets']['waiting'].id}"):
        response = client.get(url)
        assert response.status_code == 302
        assert response.location.endswith("/menunggu-verifikasi")


def test_deactivated_session_is_revoked(client, login, data):
    login("owner")
    data["users"]["owner"].status = "INACTIVE"
    db.session.commit()
    assert client.get("/dashboard").location.endswith("/login")


def test_registration_and_rt_verification(client, data):
    response = client.post("/register", data={
        "nama": "Warga Baru", "email": "baru@example.com", "no_hp": "08123456789",
        "rw_id": data["rw"].id, "rt_id": data["rt"].id, "password": PASSWORD, "confirm": PASSWORD,
    })
    assert response.status_code == 302
    user = db.session.scalar(select(User).where(User.email == "baru@example.com"))
    assert user.status == "PENDING"
    client.post("/logout")
    client.post("/login", data={"email": "rt@example.com", "password": PASSWORD})
    assert client.post(f"/rt/verifikasi-warga/{user.id}", data={"aksi": "terima"}).status_code == 302
    db.session.refresh(user)
    assert user.status == "ACTIVE"
    client.post("/logout")
    client.post("/login", data={"email": "baru@example.com", "password": PASSWORD})
    assert client.get("/pengaduan/baru").status_code == 200


def test_registration_rejects_rt_outside_rw(client, data):
    response = client.post("/register", data={"nama": "Warga Salah Wilayah", "email": "salah@example.com",
        "rw_id": data["rw"].id, "rt_id": data["outside_rt"].id, "password": PASSWORD, "confirm": PASSWORD})
    assert response.status_code == 200
    assert b"RT harus berada" in response.data
    assert db.session.scalar(select(User.id).where(User.email == "salah@example.com")) is None


def test_rt_cannot_verify_resident_outside_scope(client, login, data):
    login("neighbor_rt")
    assert client.post(f"/rt/verifikasi-warga/{data['users']['pending'].id}", data={"aksi": "terima"}).status_code == 404


def test_first_login_forces_password_change(client, data):
    user = data["users"]["rt"]
    user.must_change_password = True
    db.session.commit()
    client.post("/login", data={"email": user.email, "password": PASSWORD})
    assert client.get("/dashboard").location.endswith("/akun")
    response = client.post("/akun", data={"current_password": PASSWORD, "password": "NewPassword123!", "confirm": "NewPassword123!"})
    assert response.status_code == 302
    db.session.refresh(user)
    assert not user.must_change_password
    assert user.check_password("NewPassword123!")


def test_login_requires_csrf_when_enabled(app, client, data):
    app.config["WTF_CSRF_ENABLED"] = True
    assert client.post("/login", data={"email": "owner@example.com", "password": PASSWORD}).status_code == 400
    page = client.get("/login").data.decode()
    token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page).group(1)
    assert client.post("/login", data={"email": "owner@example.com", "password": PASSWORD, "csrf_token": token}).status_code == 302


@pytest.mark.parametrize("role,urls", [
    ("owner", ["/dashboard", "/pengaduan", "/pengaduan/baru", "/notifikasi", "/akun"]),
    ("rt", ["/dashboard", "/pengaduan", "/rt/verifikasi-warga"]),
    ("rw", ["/dashboard", "/pengaduan"]),
    ("kt", ["/dashboard", "/pengaduan"]),
    ("admin", ["/dashboard", "/admin/wilayah", "/admin/kategori", "/admin/pengurus"]),
])
def test_role_pages_render(client, login, role, urls):
    login(role)
    for url in urls:
        assert client.get(url).status_code == 200, url
