from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
from pathlib import Path
from threading import Barrier, Event

from PIL import Image
from flask_login import login_user
import pytest
from sqlalchemy import select, text

from app.models import AuditEvent, Lampiran, User, db
from app.permissions import get_ticket
from app.uploads import variant_filename
from conftest import PASSWORD
from test_hardening import session_client
from test_permissions import payload, photo


def test_parallel_uploads_have_complete_independent_files(app, data):
    owner = data["users"]["owner"]
    owner_id, version = owner.id, owner.session_version
    submissions = [payload(data), payload(data)]
    barrier = Barrier(2)

    def upload(index):
        with app.app_context():
            client = session_client(app, owner_id, version)
            values = dict(submissions[index])
            values["foto"] = (photo(), f"parallel-{index}.png", "image/png")
            barrier.wait(timeout=10)
            response = client.post("/pengaduan", data=values, content_type="multipart/form-data")
            return response.status_code, response.location

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(upload, range(2)))
    assert all(response[0] == 302 for response in responses)
    assert responses[0][1] != responses[1][1]
    db.session.rollback()
    files = db.session.scalars(select(Lampiran)).all()
    assert len(files) == 2
    assert len({attachment.nama_tersimpan for attachment in files}) == 2
    folder = Path(app.config["UPLOAD_FOLDER"])
    for attachment in files:
        assert (folder / attachment.nama_tersimpan).is_file()
        assert all((folder / variant_filename(attachment.nama_tersimpan, variant)).is_file() for variant in ("thumbnail", "display"))


def test_self_password_change_keeps_current_session_only(app, client, login, data):
    owner = data["users"]["owner"]
    other_session = session_client(app, owner.id, owner.session_version)
    login("owner")
    response = client.post("/akun", data={"current_password": PASSWORD, "password": "ChangedPassword123!", "confirm": "ChangedPassword123!"})
    assert response.status_code == 302
    assert client.get("/dashboard").status_code == 200
    assert other_session.get("/dashboard").location.endswith("/login")


def test_login_failure_audit_never_records_password(client, data, caplog):
    secret = "NeverLogThisPassword123!"
    assert client.post("/login", data={"email": "owner@example.com", "password": secret}).status_code == 200
    audit = db.session.scalar(select(AuditEvent).where(AuditEvent.event == "login.failure"))
    assert audit.outcome == "denied"
    assert audit.target_id == data["users"]["owner"].id
    assert len(audit.request_id) == 32
    assert secret not in json.dumps(audit.details)
    assert secret not in caplog.text
    assert "owner@example.com" not in json.dumps(audit.details)


def test_demo_seed_refuses_production(app):
    previous = app.config["APP_ENV"]
    app.config["APP_ENV"] = "production"
    try:
        response = app.test_cli_runner().invoke(args=["seed-demo"])
        assert response.exit_code != 0
        assert "produksi" in response.output
    finally:
        app.config["APP_ENV"] = previous


def test_16_bit_png_still_uploads_with_current_pillow(client, login, data):
    login("owner")
    stream = BytesIO()
    Image.new("I;16", (8, 8), 32768).save(stream, "PNG")
    stream.seek(0)
    values = payload(data)
    values["foto"] = (stream, "sixteen.png", "image/png")
    assert client.post("/pengaduan", data=values, content_type="multipart/form-data").status_code == 302
    attachment = db.session.scalar(select(Lampiran))
    preview = client.get(f"/lampiran/{attachment.id}?variant=thumbnail")
    with Image.open(BytesIO(preview.data)) as rendered:
        assert 115 <= rendered.convert("RGB").getpixel((0, 0))[0] <= 140


def test_late_telemetry_cannot_resurrect_logged_out_cookie(app, client, login, data):
    login("owner")
    client.get("/dashboard")
    cookie = client.get_cookie("session")
    stale = app.test_client()
    stale.set_cookie("session", cookie.value)
    assert client.post("/logout").status_code == 302
    late = stale.post("/telemetry/vitals", json={"name": "CLS", "value": .01, "page": "main.dashboard"},
                      headers={"User-Agent": "late-background-request"})
    assert late.status_code == 204
    assert "Set-Cookie" not in late.headers
    assert client.get("/dashboard").location.partition("?")[0] == "/login"


def test_normal_reads_do_not_refresh_auth_cookie(client, login, data):
    login("owner")
    client.get("/dashboard")
    assert "Set-Cookie" not in client.get("/dashboard").headers


def test_failed_admin_commit_does_not_log_success(client, login, data, monkeypatch, caplog):
    from sqlalchemy.exc import OperationalError

    login("admin")
    caplog.clear()
    owner_id = data["users"]["owner"].id

    def unavailable():
        raise OperationalError("COMMIT", {}, Exception("Simulated failure"))

    monkeypatch.setattr(db.session, "commit", unavailable)
    response = client.post(f"/admin/pengurus/{owner_id}", data={"aksi": "toggle"})
    assert response.status_code == 500
    assert "account.updated" not in caplog.text
    assert db.session.scalar(select(AuditEvent).where(AuditEvent.event == "account.updated")) is None

@pytest.mark.parametrize("handle", ["admin", "rw", "rt", "kt", "owner"])
def test_ticket_lock_does_not_lock_region_or_user_parents(app, data, handle):
    ticket = data["tickets"]["assigned"]
    ticket_id, region_id = ticket.id, ticket.rt_id
    manager_id = data["users"][handle].id
    parent_ids = (ticket.pelapor_id, ticket.ditugaskan_ke_id, manager_id)
    locked, release = Event(), Event()
    engine = db.engine

    def hold_ticket():
        with app.test_request_context():
            try:
                login_user(db.session.get(User, manager_id))
                assert get_ticket(ticket_id, lock=True).id == ticket_id
                locked.set()
                assert release.wait(timeout=15)
            finally:
                db.session.rollback()
                db.session.remove()

    with ThreadPoolExecutor(max_workers=1) as executor:
        worker = executor.submit(hold_ticket)
        try:
            assert locked.wait(timeout=10)
            with engine.connect() as connection:
                connection.execute(text("SET SESSION innodb_lock_wait_timeout = 1"))
                assert connection.scalar(text("SELECT id FROM rt WHERE id = :target FOR UPDATE"), {"target": region_id}) == region_id
                for parent_id in set(parent_ids):
                    assert connection.scalar(text("SELECT id FROM users WHERE id = :target FOR UPDATE"), {"target": parent_id}) == parent_id
                connection.rollback()
        finally:
            release.set()
            worker.result(timeout=15)
