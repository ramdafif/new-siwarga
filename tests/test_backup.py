from concurrent.futures import ThreadPoolExecutor
import json
from time import perf_counter
from pathlib import Path

import pytest
from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import make_url

from scripts import backup
from app import create_app
from conftest import PASSWORD
from app.models import Lampiran, db
from test_hardening import session_client
from test_permissions import payload, photo


@pytest.mark.parametrize("name", ["../secret", "..", "/etc/passwd", "folder/name", "folder\\name", ""])
def test_snapshot_paths_cannot_escape(tmp_path, name):
    with pytest.raises(ValueError):
        backup.safe_file(tmp_path, name)


def test_snapshot_detects_photo_and_database_corruption(tmp_path):
    (tmp_path / "uploads").mkdir()
    database = tmp_path / "database.sql"
    database.write_bytes(b"SQL snapshot")
    picture = tmp_path / "uploads" / "photo.jpg"
    picture.write_bytes(b"Original photo")
    manifest = dict(version=1, database_sha256=backup.checksum(database),
                    attachments=[dict(id=1, name="photo.jpg", sha256=backup.checksum(picture))])
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    assert backup.verify_snapshot(tmp_path) == manifest
    picture.write_bytes(b"Changed photo")
    with pytest.raises(ValueError):
        backup.verify_snapshot(tmp_path)
    picture.write_bytes(b"Original photo")
    database.write_bytes(b"Changed database")
    with pytest.raises(ValueError):
        backup.verify_snapshot(tmp_path)


@pytest.mark.parametrize("target", ["mysql+pymysql://user@localhost/app", "mysql+pymysql://user@elsewhere/app"])
def test_restore_rejects_application_database_even_with_host_alias(target):
    with pytest.raises(ValueError):
        backup.validate_recovery_target(target, "mysql+pymysql://user@127.0.0.1/app")


def test_verification_requires_explicit_scratch_schema():
    with pytest.raises(ValueError):
        backup.validate_recovery_target("mysql+pymysql://user@localhost/other_data", "mysql+pymysql://user@localhost/app", verification=True)


def test_backup_and_restore_with_upload_after_snapshot(app, client, login, data, tmp_path, monkeypatch):
    login("owner")
    values = payload(data)
    values["foto"] = (photo(), "before.png", "image/png")
    assert client.post("/pengaduan", data=values, content_type="multipart/form-data").status_code == 302
    source = make_url(app.config["SQLALCHEMY_DATABASE_URI"])
    assert source.database.endswith("_test")
    prefix = source.database[:-5]
    verification = source.set(database=prefix + "_restore_test")
    recovery = source.set(database=prefix + "_recovery_drill_test")
    assert recovery.database.endswith("_recovery_drill_test")
    recovery_engine = create_engine(recovery)
    try:
        metadata = MetaData()
        metadata.reflect(bind=recovery_engine)
        metadata.drop_all(bind=recovery_engine)
    finally:
        recovery_engine.dispose()
    original_run = backup.run_mysql
    owner = data["users"]["owner"]
    owner_id, version = owner.id, owner.session_version
    after_values = payload(data)
    statuses = []

    def upload_after_snapshot():
        with app.app_context():
            worker = session_client(app, owner_id, version)
            incoming = dict(after_values)
            incoming["foto"] = (photo(), "after.png", "image/png")
            return worker.post("/pengaduan", data=incoming, content_type="multipart/form-data").status_code

    def dump_and_upload(url, dump_path=None, output_path=None):
        original_run(url, dump_path=dump_path, output_path=output_path)
        if output_path:
            with ThreadPoolExecutor(max_workers=1) as executor:
                statuses.append(executor.submit(upload_after_snapshot).result(timeout=30))

    monkeypatch.setattr(backup, "run_mysql", dump_and_upload)
    snapshot = backup.create_snapshot(source.render_as_string(hide_password=False), verification.render_as_string(hide_password=False),
                                      app.config["UPLOAD_FOLDER"], tmp_path / "snapshots")
    assert statuses == [302]
    manifest = backup.verify_snapshot(snapshot)
    assert len(manifest["attachments"]) == 1
    db.session.rollback()
    assert db.session.query(Lampiran).count() == 2
    restore_started = perf_counter()
    restored = backup.restore_snapshot(snapshot, recovery.render_as_string(hide_password=False),
                                      source.render_as_string(hide_password=False), tmp_path / "restored-photos")
    assert len(restored["attachments"]) == 1
    fresh = create_app({"TESTING": True, "SECRET_KEY": app.secret_key, "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": recovery.render_as_string(hide_password=False),
        "UPLOAD_FOLDER": str(tmp_path / "restored-photos"), "LOGIN_RATE_LIMIT_BACKEND": "memory"})
    try:
        recovered_client = fresh.test_client()
        assert recovered_client.post("/login", data={"email": "owner@example.com", "password": PASSWORD}).status_code == 302
        attachment_id = restored["attachments"][0]["id"]
        assert recovered_client.get(f"/lampiran/{attachment_id}").status_code == 200
        assert recovered_client.get(f"/lampiran/{attachment_id}?variant=display").mimetype == "image/webp"
    finally:
        with fresh.app_context():
            db.session.remove()
            db.engine.dispose()
    artifact = Path(__file__).resolve().parent.parent / "test-results" / "recovery-drill.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(dict(backup_seconds=manifest["duration_seconds"],
        restore_and_smoke_seconds=round(perf_counter() - restore_started, 3),
        snapshot_attachments=len(manifest["attachments"]), concurrent_upload_succeeded=True,
        login_and_private_photo_verified=True, scope="local MySQL; remote repository/provisioning not tested"), indent=2) + "\n")
    for attachment in restored["attachments"]:
        assert (tmp_path / "restored-photos" / attachment["name"]).is_file()
        assert len(list((tmp_path / "restored-photos").glob("*.webp"))) == 2
