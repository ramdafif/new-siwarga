import os
from pathlib import Path

import pytest
from dotenv import dotenv_values
from flask import g
from flask.testing import FlaskClient
from flask_migrate import upgrade
from sqlalchemy import text
from sqlalchemy.engine import make_url
from werkzeug.security import generate_password_hash

from app import create_app
from app.models import Kategori, Pengaduan, RT, RW, RiwayatStatus, User, db

ROOT = Path(__file__).resolve().parent.parent
PASSWORD = "TestPassword123!"
PASSWORD_HASH = generate_password_hash(PASSWORD)


class FreshRequestClient(FlaskClient):
    def open(self, *args, **kwargs):
        g.pop("_login_user", None)
        return super().open(*args, **kwargs)


@pytest.fixture(scope="session")
def test_app(tmp_path_factory):
    values = dotenv_values(ROOT / ".env")
    database_url = os.getenv("TEST_DATABASE_URL") or values.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL belum dikonfigurasi; tes integrasi memerlukan MySQL 8 khusus test.")
    url = make_url(database_url)
    production_url = os.getenv("DATABASE_URL") or values.get("DATABASE_URL")
    if not url.database or not url.database.endswith("_test") or (production_url and url.database == make_url(production_url).database):
        pytest.fail("Demi keamanan, nama database test wajib berakhiran _test dan berbeda dari database aplikasi.")
    application = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-only-secret-key-with-more-than-32-characters",
        "SQLALCHEMY_DATABASE_URI": database_url,
        "WTF_CSRF_ENABLED": False,
        "UPLOAD_FOLDER": str(tmp_path_factory.mktemp("uploads")),
        "DEMO_PASSWORD": PASSWORD,
    })
    application.test_client_class = FreshRequestClient
    with application.app_context():
        version = db.session.scalar(text("SELECT VERSION()"))
        if not version.startswith("8.") or "MariaDB" in version:
            pytest.fail(f"Jalankan tes pada MySQL 8, bukan {version}.")
        db.session.remove()
        upgrade(directory=str(ROOT / "migrations"))
    yield application
    with application.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def app(test_app):
    test_app.config["WTF_CSRF_ENABLED"] = False
    test_app.extensions.pop("login_attempts", None)
    with test_app.app_context():
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()
        yield test_app
        db.session.rollback()
        db.session.remove()


@pytest.fixture
def data(app):
    first_rw = RW(nomor="01", nama_wilayah="Wilayah Pertama")
    second_rw = RW(nomor="02", nama_wilayah="Wilayah Kedua")
    db.session.add_all([first_rw, second_rw])
    db.session.flush()
    first_rt = RT(rw_id=first_rw.id, nomor="01")
    neighbor_rt = RT(rw_id=first_rw.id, nomor="02")
    outside_rt = RT(rw_id=second_rw.id, nomor="01")
    db.session.add_all([first_rt, neighbor_rt, outside_rt])
    category = Kategori(nama="Drainase", aktif=True)
    db.session.add(category)
    db.session.flush()
    definitions = {
        "admin": ("SUPERADMIN", None, None, "ACTIVE"),
        "rw": ("RW", first_rw.id, None, "ACTIVE"),
        "rt": ("RT", first_rw.id, first_rt.id, "ACTIVE"),
        "neighbor_rt": ("RT", first_rw.id, neighbor_rt.id, "ACTIVE"),
        "outside_rw": ("RW", second_rw.id, None, "ACTIVE"),
        "outside_rt": ("RT", second_rw.id, outside_rt.id, "ACTIVE"),
        "kt": ("KARANG_TARUNA", first_rw.id, None, "ACTIVE"),
        "other_kt": ("KARANG_TARUNA", first_rw.id, None, "ACTIVE"),
        "outside_kt": ("KARANG_TARUNA", second_rw.id, None, "ACTIVE"),
        "owner": ("WARGA", first_rw.id, first_rt.id, "ACTIVE"),
        "other": ("WARGA", first_rw.id, first_rt.id, "ACTIVE"),
        "neighbor": ("WARGA", first_rw.id, neighbor_rt.id, "ACTIVE"),
        "outside": ("WARGA", second_rw.id, outside_rt.id, "ACTIVE"),
        "pending": ("WARGA", first_rw.id, first_rt.id, "PENDING"),
    }
    users = {}
    for handle, (role, rw_id, rt_id, status) in definitions.items():
        user = User(nama=handle.replace("_", " ").title(), email=f"{handle}@example.com", role=role,
                    rw_id=rw_id, rt_id=rt_id, status=status, password_hash=PASSWORD_HASH)
        db.session.add(user)
        users[handle] = user
    db.session.flush()
    tickets = {}
    for index, (handle, reporter, status, assigned) in enumerate((
        ("waiting", "owner", "MENUNGGU_VERIFIKASI", None),
        ("other", "other", "MENUNGGU_VERIFIKASI", None),
        ("neighbor", "neighbor", "MENUNGGU_VERIFIKASI", None),
        ("outside", "outside", "MENUNGGU_VERIFIKASI", None),
        ("assigned", "owner", "DIPROSES", "kt"),
        ("unassigned", "owner", "DIPROSES", None),
        ("completed", "owner", "SELESAI", "kt"),
    ), 1):
        ticket = Pengaduan(nomor_tiket=f"TEST-{index:06d}", pelapor_id=users[reporter].id,
                           rt_id=users[reporter].rt_id, kategori_id=category.id, judul=f"Laporan {handle} untuk pengujian",
                           deskripsi="Pengaduan tentang saluran air yang perlu dibersihkan bersama warga.",
                           lokasi_teks="Jalan Pengujian nomor 12", status=status,
                           ditugaskan_ke_id=users[assigned].id if assigned else None)
        db.session.add(ticket)
        db.session.flush()
        db.session.add(RiwayatStatus(pengaduan_id=ticket.id, aktor_id=users[reporter].id, status_baru=status,
                                    catatan="Riwayat awal pengujian."))
        tickets[handle] = ticket
    db.session.commit()
    return dict(users=users, tickets=tickets, rw=first_rw, outside_rw=second_rw, rt=first_rt,
                neighbor_rt=neighbor_rt, outside_rt=outside_rt, category=category)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def login(client, data):
    def perform(handle):
        response = client.post("/login", data={"email": data["users"][handle].email, "password": PASSWORD})
        assert response.status_code == 302
        return response
    return perform
