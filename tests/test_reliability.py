from io import BytesIO
from pathlib import Path

from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app import create_app
from app.models import Lampiran, Pengaduan, User, db
from conftest import PASSWORD
from test_permissions import payload


def test_seed_is_idempotent_and_preserves_passwords(app, data):
    runner = app.test_cli_runner()
    first = runner.invoke(args=["seed-demo"])
    assert first.exit_code == 0, first.output
    counts = [db.session.scalar(select(func.count()).select_from(model)) for model in (User, Pengaduan)]
    seeded = db.session.scalar(select(User).where(User.email == "warga@siwarga.id"))
    original_hash = seeded.password_hash
    second = runner.invoke(args=["seed-demo"])
    assert second.exit_code == 0, second.output
    assert [db.session.scalar(select(func.count()).select_from(model)) for model in (User, Pengaduan)] == counts
    db.session.refresh(seeded)
    assert seeded.password_hash == original_hash


def test_database_error_renders_informative_500(client, login, monkeypatch):
    login("owner")

    def fail(*args, **kwargs):
        raise OperationalError("SELECT", {}, Exception("Simulated connection loss"))

    monkeypatch.setattr(db.session, "scalar", fail)
    response = client.get("/notifikasi")
    assert response.status_code == 500
    assert b"Periksa koneksi MySQL" in response.data


def test_uploaded_png_metadata_is_removed(app, client, login, data):
    login("owner")
    image = Image.new("RGB", (8, 8), "green")
    metadata = image.getexif()
    metadata[270] = "PRIVATE_METADATA_SHOULD_NOT_SURVIVE"
    stream = BytesIO()
    image.save(stream, "PNG", exif=metadata)
    stream.seek(0)
    values = payload(data)
    values["foto"] = (stream, "metadata.png", "image/png")
    assert client.post("/pengaduan", data=values, content_type="multipart/form-data").status_code == 302
    attachment = db.session.scalar(select(Lampiran))
    saved = Path(app.config["UPLOAD_FOLDER"]) / attachment.nama_tersimpan
    with Image.open(saved) as cleaned:
        assert not cleaned.getexif()
    assert b"PRIVATE_METADATA" not in saved.read_bytes()


def test_data_is_persisted_across_app_instances(app, data):
    fresh = create_app({"TESTING": True, "SECRET_KEY": app.config["SECRET_KEY"],
        "SQLALCHEMY_DATABASE_URI": app.config["SQLALCHEMY_DATABASE_URI"],
        "UPLOAD_FOLDER": app.config["UPLOAD_FOLDER"], "WTF_CSRF_ENABLED": False})
    fresh_client = fresh.test_client()
    response = fresh_client.post("/login", data={"email": "owner@example.com", "password": PASSWORD})
    assert response.status_code == 302
    assert fresh_client.get(f"/pengaduan/{data['tickets']['waiting'].id}").status_code == 200
    with fresh.app_context():
        db.session.remove()
        db.engine.dispose()


def test_failed_commit_cleans_up_files_and_rolls_back_ticket(app, client, login, data, monkeypatch):
    from test_permissions import photo

    login("owner")
    before = db.session.scalar(select(func.count()).select_from(Pengaduan))
    folder = Path(app.config["UPLOAD_FOLDER"])
    files_before = set(folder.iterdir())

    def fail_commit():
        raise OperationalError("COMMIT", {}, Exception("Simulated commit failure"))

    monkeypatch.setattr(db.session, "commit", fail_commit)
    values = payload(data)
    values["foto"] = (photo(), "rollback.png", "image/png")
    response = client.post("/pengaduan", data=values, content_type="multipart/form-data")
    assert response.status_code == 500
    assert db.session.scalar(select(func.count()).select_from(Pengaduan)) == before
    assert set(folder.iterdir()) == files_before
