import json
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from threading import Barrier

import fakeredis
import pytest
from flask import current_app
from PIL import Image
from redis import ConnectionError as RedisConnectionError
from sqlalchemy import event, func, select

from app import create_app
from app.models import AuditEvent, Lampiran, Notifikasi, Pengaduan, RiwayatStatus, User, db
from app.security import login_keys, login_limiter, issue_submission_token, revoke_sessions
from app.uploads import atomic_write, variant_filename
from conftest import PASSWORD
from test_permissions import payload, photo


def test_preview_sizes_metadata_and_html(app, client, login, data):
    login("owner")
    source = Image.new("RGB", (2200, 1600), "#277c63")
    metadata = source.getexif()
    metadata[270] = "PRIVATE"
    stream = BytesIO()
    source.save(stream, "JPEG", exif=metadata)
    stream.seek(0)
    values = payload(data)
    values["foto"] = (stream, "large.jpg", "image/jpeg")
    response = client.post("/pengaduan", data=values, content_type="multipart/form-data")
    assert response.status_code == 302
    attachment = db.session.scalar(select(Lampiran))
    for variant, dimension, budget in (("thumbnail", 480, 60000), ("display", 1280, 220000)):
        response = client.get(f"/lampiran/{attachment.id}?variant={variant}")
        assert response.status_code == 200
        assert response.mimetype == "image/webp"
        assert len(response.data) <= budget
        assert "no-store" in response.headers["Cache-Control"]
        with Image.open(BytesIO(response.data)) as image:
            assert max(image.size) <= dimension
            assert not image.getexif()
    page = client.get(f"/pengaduan/{attachment.pengaduan_id}")
    assert b"srcset=" in page.data
    assert b"variant=display" in page.data
    assert b'width="480" height="320"' in page.data
    assert client.get(f"/lampiran/{attachment.id}?variant=unexpected").status_code == 400


@pytest.mark.parametrize("handle", ["other", "neighbor", "outside", "outside_rt", "outside_rw", "other_kt"])
@pytest.mark.parametrize("variant", ["original", "thumbnail", "display"])
def test_all_photo_variants_remain_private(client, login, data, handle, variant):
    login("owner")
    values = payload(data)
    values["foto"] = (photo(), "private.png", "image/png")
    client.post("/pengaduan", data=values, content_type="multipart/form-data")
    attachment = db.session.scalar(select(Lampiran))
    client.post("/logout")
    login(handle)
    assert client.get(f"/lampiran/{attachment.id}?variant={variant}").status_code == 404


def test_photo_backfill_is_repeatable(app, client, login, data):
    login("owner")
    values = payload(data)
    values["foto"] = (photo(), "legacy.png", "image/png")
    client.post("/pengaduan", data=values, content_type="multipart/form-data")
    attachment = db.session.scalar(select(Lampiran))
    folder = Path(app.config["UPLOAD_FOLDER"])
    (folder / variant_filename(attachment.nama_tersimpan, "thumbnail")).unlink()
    runner = app.test_cli_runner()
    first = runner.invoke(args=["backfill-photos", "--batch-size", "1"])
    assert first.exit_code == 0, first.output
    assert '"written": 1' in first.output
    second = runner.invoke(args=["backfill-photos"])
    assert second.exit_code == 0, second.output
    assert '"written": 0' in second.output


def test_atomic_file_failure_removes_temporary_file(tmp_path, monkeypatch):
    import app.uploads as uploads

    def full_disk(*args):
        raise OSError("Simulated full disk")

    monkeypatch.setattr(uploads.os, "replace", full_disk)
    with pytest.raises(OSError):
        atomic_write(tmp_path / "photo.webp", b"content")
    assert list(tmp_path.iterdir()) == []


def test_upload_disk_failure_rolls_back_everything(app, client, login, data, monkeypatch):
    import app.uploads as uploads

    login("owner")
    before = db.session.scalar(select(func.count()).select_from(Pengaduan))
    folder = Path(app.config["UPLOAD_FOLDER"])
    files_before = set(folder.iterdir())
    original_write = uploads.atomic_write
    writes = []

    def full_disk(destination, content):
        writes.append(destination)
        if len(writes) == 2:
            raise OSError("Simulated full disk")
        original_write(destination, content)

    monkeypatch.setattr(uploads, "atomic_write", full_disk)
    values = payload(data)
    values["foto"] = (photo(), "full.png", "image/png")
    app.config["PROPAGATE_EXCEPTIONS"] = False
    try:
        assert client.post("/pengaduan", data=values, content_type="multipart/form-data").status_code == 500
    finally:
        app.config.pop("PROPAGATE_EXCEPTIONS", None)
    assert db.session.scalar(select(func.count()).select_from(Pengaduan)) == before
    assert set(folder.iterdir()) == files_before


def test_repeated_submission_redirects_to_same_ticket(client, login, data):
    login("owner")
    values = payload(data)
    first = client.post("/pengaduan", data=values)
    second = client.post("/pengaduan", data=values)
    assert first.status_code == second.status_code == 302
    assert first.location == second.location
    assert db.session.scalar(select(func.count()).select_from(Pengaduan).where(Pengaduan.judul == values["judul"])) == 1


def test_missing_or_other_users_submission_token_is_rejected(client, login, data):
    login("owner")
    values = payload(data)
    values.pop("submission_token")
    assert client.post("/pengaduan", data=values).status_code == 400
    values["submission_token"] = issue_submission_token(data["users"]["other"].id)
    assert client.post("/pengaduan", data=values).status_code == 400


def session_client(app, user_id, version):
    client = app.test_client()
    with client.session_transaction() as saved:
        saved["_user_id"] = str(user_id)
        saved["_fresh"] = True
        saved["account_version"] = version
    return client


def test_parallel_submission_creates_one_ticket(app, data):
    values = payload(data)
    owner = data["users"]["owner"]
    owner_id, version = owner.id, owner.session_version
    barrier = Barrier(2)

    def submit():
        with app.app_context():
            worker = session_client(app, owner_id, version)
            barrier.wait(timeout=10)
            response = worker.post("/pengaduan", data=values)
            return response.status_code, response.location

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda unused: submit(), range(2)))
    assert results[0] == results[1]
    assert results[0][0] == 302
    db.session.rollback()
    assert db.session.scalar(select(func.count()).select_from(Pengaduan).where(Pengaduan.judul == values["judul"])) == 1


def test_parallel_verification_only_one_transition(app, data):
    manager = data["users"]["rt"]
    manager_id, version = manager.id, manager.session_version
    ticket_id = data["tickets"]["waiting"].id
    barrier = Barrier(2)

    def verify():
        with app.app_context():
            worker = session_client(app, manager_id, version)
            barrier.wait(timeout=10)
            return worker.post(f"/pengaduan/{ticket_id}/verifikasi", data={"aksi": "terima", "catatan": "Diverifikasi bersama."}).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = sorted(executor.map(lambda unused: verify(), range(2)))
    assert statuses == [302, 409]
    db.session.rollback()
    assert db.session.scalar(select(func.count()).select_from(RiwayatStatus).where(RiwayatStatus.pengaduan_id == ticket_id, RiwayatStatus.status_baru == "DIPROSES")) == 1


def test_redis_limit_shared_by_app_workers(app, data):
    server = fakeredis.FakeServer()
    common = {"TESTING": True, "SECRET_KEY": app.secret_key, "SQLALCHEMY_DATABASE_URI": app.config["SQLALCHEMY_DATABASE_URI"],
              "WTF_CSRF_ENABLED": False, "UPLOAD_FOLDER": app.config["UPLOAD_FOLDER"], "LOGIN_RATE_LIMIT_BACKEND": "redis",
              "REDIS_NAMESPACE": "test-shared", "REDIS_CLIENT": fakeredis.FakeRedis(server=server)}
    workers = [create_app(common) for unused in range(2)]
    clients = [worker.test_client() for worker in workers]
    try:
        for index in range(5):
            assert clients[index % 2].post("/login", data={"email": "owner@example.com", "password": "wrong"}).status_code == 200
        assert clients[1].post("/login", data={"email": "owner@example.com", "password": PASSWORD}).status_code == 429
    finally:
        for worker in workers:
            with worker.app_context():
                db.session.remove()
                db.engine.dispose()


def test_redis_failure_does_not_fail_open(app, client, data, monkeypatch):
    app.config.update(LOGIN_RATE_LIMIT_BACKEND="redis", REDIS_CLIENT=fakeredis.FakeRedis())
    app.extensions.pop("login_attempts", None)
    limiter = login_limiter()

    def unavailable(*args, **kwargs):
        raise RedisConnectionError("Simulated outage")

    monkeypatch.setattr(limiter.client, "eval", unavailable)
    try:
        assert client.post("/login", data={"email": "owner@example.com", "password": PASSWORD}).status_code == 503
    finally:
        app.config["LOGIN_RATE_LIMIT_BACKEND"] = "memory"
        app.config.pop("REDIS_CLIENT", None)
        app.extensions.pop("login_attempts", None)


def test_role_change_and_password_reset_revoke_sessions(client, login, data):
    login("owner")
    owner = data["users"]["owner"]
    revoke_sessions(owner)
    db.session.commit()
    assert client.get("/dashboard").location.endswith("/login")


def test_admin_password_reset_has_audit_and_revokes_old_session(app, client, login, data):
    owner = data["users"]["owner"]
    old_client = session_client(app, owner.id, owner.session_version)
    login("admin")
    response = client.post(f"/admin/pengurus/{owner.id}", data={"nama": owner.nama, "email": owner.email,
        "role": "WARGA", "rw_id": owner.rw_id, "rt_id": owner.rt_id, "password": "TemporaryPassword123!"})
    assert response.status_code == 302
    audit = db.session.scalar(select(AuditEvent).where(AuditEvent.event == "account.updated"))
    assert audit.target_id == owner.id
    assert audit.details["password_reset"] is True
    assert "TemporaryPassword" not in str(audit.details)
    assert old_client.get("/dashboard").location.endswith("/login")


def test_live_and_ready_and_internal_metrics(client):
    assert client.get("/health/live").json == {"status": "alive"}
    assert client.get("/health/ready").status_code == 200
    assert client.get("/metrics").status_code == 200
    assert client.get("/metrics", environ_overrides={"REMOTE_ADDR": "203.0.113.10"}).status_code == 404


@pytest.mark.parametrize("payload_value", [None, [], {"name": "CLS", "value": -1, "page": "tickets.detail"},
    {"name": "LCP", "value": True, "page": "tickets.detail"},
    {"name": "LCP", "value": 100, "page": "/pengaduan/123"},
    {"name": "LCP", "value": 100, "page": "tickets.detail", "email": "private@example.com"}])
def test_vitals_reject_unbounded_or_private_payloads(client, login, payload_value):
    login("owner")
    assert client.post("/telemetry/vitals", data=json.dumps(payload_value), content_type="application/json").status_code == 400


def test_vitals_require_session_and_csrf(app, client, login):
    assert client.post("/telemetry/vitals", json={"name": "CLS", "value": .04, "page": "tickets.detail"}).status_code == 302
    login("owner")
    assert client.post("/telemetry/vitals", json={"name": "CLS", "value": .04, "page": "tickets.detail"}).status_code == 204
    app.config["WTF_CSRF_ENABLED"] = True
    assert client.post("/telemetry/vitals", json={"name": "CLS", "value": .04, "page": "tickets.detail"}).status_code == 400


def test_summary_does_not_load_ticket_collections(app, client, login, data):
    login("owner")
    statements = []

    def collect(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())

    event.listen(db.engine, "before_cursor_execute", collect)
    try:
        assert client.get("/pengaduan").status_code == 200
    finally:
        event.remove(db.engine, "before_cursor_execute", collect)
    assert not any("from lampiran" in statement or "from komentar" in statement or "from tindak_lanjut" in statement or "from riwayat_status" in statement for statement in statements)
