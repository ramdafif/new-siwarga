import ast
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

from dotenv import dotenv_values

import fakeredis
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app import create_app
from app.models import AuditEvent, Notifikasi, RT, RW, User, db
from conftest import PASSWORD
from test_hardening import session_client
from test_navigation import PageControls


def test_logout_revokes_copied_cookie_and_other_devices(app, client, login, data):
    login("owner")
    owner = data["users"]["owner"]
    previous_version = owner.session_version
    copied = app.test_client()
    copied.set_cookie("session", client.get_cookie("session").value)
    other_device = session_client(app, owner.id, previous_version)

    assert client.post("/logout").status_code == 302
    db.session.refresh(owner)
    assert owner.session_version == previous_version + 1
    for browser in (client, copied, other_device):
        assert browser.get("/dashboard").location.partition("?")[0] == "/login"
    audit = db.session.scalar(select(AuditEvent).where(AuditEvent.event == "logout"))
    assert audit.target_id == owner.id
    assert audit.details == {"scope": "all_sessions"}


def test_failed_logout_rolls_back_session_revocation(client, login, data, monkeypatch):
    login("owner")
    owner = data["users"]["owner"]
    previous_version = owner.session_version

    def unavailable():
        raise OperationalError("COMMIT", {}, Exception("Simulated failure"))

    with monkeypatch.context() as scoped:
        scoped.setattr(db.session, "commit", unavailable)
        assert client.post("/logout").status_code == 500
    db.session.refresh(owner)
    assert owner.session_version == previous_version
    assert db.session.scalar(select(AuditEvent.id).where(AuditEvent.event == "logout")) is None
    assert client.get("/dashboard").status_code == 200


@pytest.mark.parametrize("email", ["OWNER@example.com", "\u00f3wner@example.com", "o\u0301wner@example.com"])
def test_login_aliases_share_account_limit(client, data, email):
    assert db.session.scalar(select(User.id).where(User.email == email)) == data["users"]["owner"].id
    for unused_attempt in range(5):
        assert client.post("/login", data={"email": "owner@example.com", "password": "wrong"}).status_code == 200
    assert client.post("/login", data={"email": email, "password": PASSWORD}).status_code == 429


def test_existing_unicode_account_keeps_login_and_shared_limit(client, data):
    owner = data["users"]["owner"]
    owner.email = "\u00f3wner@example.com"
    db.session.commit()
    for unused_attempt in range(5):
        assert client.post("/login", data={"email": owner.email, "password": "wrong"}).status_code == 200
    assert client.post("/login", data={"email": "owner@example.com", "password": PASSWORD}).status_code == 429


def test_unicode_account_can_still_login(client, data):
    owner = data["users"]["owner"]
    owner.email = "\u00f3wner@example.com"
    db.session.commit()
    assert client.post("/login", data={"email": owner.email, "password": PASSWORD}).status_code == 302


def test_collation_alias_limit_is_shared_between_workers(app, data):
    server = fakeredis.FakeServer()
    configuration = {"TESTING": True, "SECRET_KEY": app.secret_key,
                     "SQLALCHEMY_DATABASE_URI": app.config["SQLALCHEMY_DATABASE_URI"],
                     "WTF_CSRF_ENABLED": False, "UPLOAD_FOLDER": app.config["UPLOAD_FOLDER"],
                     "LOGIN_RATE_LIMIT_BACKEND": "redis", "REDIS_NAMESPACE": "test-alias-limit",
                     "REDIS_CLIENT": fakeredis.FakeRedis(server=server)}
    workers = [create_app(configuration) for unused in range(2)]
    clients = [worker.test_client() for worker in workers]
    try:
        for attempt in range(5):
            email = "owner@example.com" if attempt % 2 else "\u00f3wner@example.com"
            assert clients[attempt % 2].post("/login", data={"email": email, "password": "wrong"}).status_code == 200
        assert clients[1].post("/login", data={"email": "owner@example.com", "password": PASSWORD}).status_code == 429
    finally:
        for worker in workers:
            with worker.app_context():
                db.session.remove()
                db.engine.dispose()


@pytest.mark.parametrize("path", ["/health/live", "/login", "/missing-route"])
def test_untrusted_host_returns_safe_400(client, app, monkeypatch, path):
    monkeypatch.setitem(app.config, "TRUSTED_HOSTS", ["siwarga.example.org"])
    response = client.get(path, base_url="http://untrusted.invalid")
    assert response.status_code == 400
    assert response.mimetype == "text/plain"
    assert b"Host permintaan tidak diizinkan" in response.data
    assert b"Traceback" not in response.data
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_untrusted_host_does_not_process_authenticated_account(app, client, login, data, monkeypatch):
    login("owner")
    data["users"]["owner"].must_change_password = True
    db.session.commit()
    monkeypatch.setitem(app.config, "TRUSTED_HOSTS", ["siwarga.example.org"])
    response = client.get("/dashboard")
    assert response.status_code == 400

def test_authenticated_missing_page_still_disables_caching(client, login):
    login("owner")
    response = client.get("/page-that-does-not-exist")
    assert response.status_code == 404
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("path,handle", [("/pengaduan", "owner"), ("/notifikasi", "owner"),
                                         ("/admin/pengurus", "admin"), ("/rt/verifikasi-warga", "rt")])
@pytest.mark.parametrize("page", ["0", "-1", "invalid", "9" * 80, "10001", "\u0661"])
def test_invalid_pagination_is_rejected(client, login, path, handle, page):
    login(handle)
    assert client.get(path, query_string={"page": page}).status_code == 400


@pytest.mark.parametrize("value", ["0001-01-01", "0001-01-02", "0999-12-31", "invalid"])
@pytest.mark.parametrize("field", ["dari", "sampai"])
def test_invalid_date_boundaries_return_400(client, login, value, field):
    login("owner")
    assert client.get("/pengaduan", query_string={field: value}).status_code == 400


@pytest.mark.parametrize("value", ["1000-01-02", "9999-12-31"])
def test_supported_date_boundaries_still_work(client, login, value):
    login("owner")
    assert client.get("/pengaduan", query_string={"dari": value, "sampai": value}).status_code == 200


@pytest.mark.parametrize("parameter,value", [("endpoint", "anything"), ("_method", "DELETE"),
                                           ("_external", "true"), ("_scheme", "https")])
def test_unknown_pagination_parameters_cannot_override_routing(client, login, data, parameter, value):
    login("owner")
    for index in range(16):
        db.session.add(Notifikasi(user_id=data["users"]["owner"].id, pesan=f"Pagination {index}"))
    db.session.commit()
    for path in ("/pengaduan", "/notifikasi"):
        response = client.get(path, query_string={parameter: value})
        assert response.status_code == 200
        controls = PageControls(response.get_data(as_text=True))
        for link in controls.links:
            assert parameter not in parse_qs(urlsplit(link).query)


def test_pagination_preserves_only_public_filters(client, login):
    login("admin")
    response = client.get("/admin/pengurus?role=invalid&endpoint=anything&_external=true")
    assert response.status_code == 200
    links = PageControls(response.get_data(as_text=True)).links
    page_links = [link for link in links if "page=" in link]
    assert page_links
    for link in page_links:
        parsed = urlsplit(link)
        assert not parsed.netloc
        assert set(parse_qs(parsed.query)) == {"role", "page"}


def test_duplicate_admin_email_returns_conflict_without_audit(client, login, data):
    login("admin")
    before = db.session.scalar(select(func.count()).select_from(User))
    response = client.post("/admin/pengurus", data={"nama": "Pengurus Duplikat",
        "email": data["users"]["owner"].email, "role": "RT", "rw_id": data["rw"].id,
        "rt_id": data["rt"].id, "password": PASSWORD})
    assert response.status_code == 409
    assert db.session.scalar(select(func.count()).select_from(User)) == before
    assert db.session.scalar(select(AuditEvent.id).where(AuditEvent.event == "account.created")) is None


@pytest.mark.parametrize("path,model", [("/admin/rw", RW), ("/admin/rt", RT)])
def test_region_zero_padding_cannot_create_duplicate_number(client, login, data, path, model):
    login("admin")
    before = db.session.scalar(select(func.count()).select_from(model))
    response = client.post(path, data={"nomor": "001", "nama_wilayah": "Duplikat wilayah", "rw_id": data["rw"].id})
    assert response.status_code == 409
    assert db.session.scalar(select(func.count()).select_from(model)) == before


def test_new_region_number_is_canonical(client, login):
    login("admin")
    assert client.post("/admin/rw", data={"nomor": "003", "nama_wilayah": "Wilayah baru"}).status_code == 302
    assert db.session.scalar(select(RW.nomor).where(RW.nama_wilayah == "Wilayah baru")) == "03"


def test_notification_for_reassigned_ticket_does_not_restore_access(client, login, data):
    login("kt")
    ticket = data["tickets"]["assigned"]
    notification = Notifikasi(user_id=data["users"]["kt"].id, pengaduan_id=ticket.id, pesan="Tugas sebelumnya")
    db.session.add(notification)
    ticket.ditugaskan_ke_id = data["users"]["other_kt"].id
    db.session.commit()
    response = client.post(f"/notifikasi/{notification.id}/baca")
    assert response.location.endswith("/notifikasi")
    assert notification.sudah_dibaca
    assert b"sudah berubah" in client.get(response.location).data
    assert client.get(f"/pengaduan/{ticket.id}").status_code == 404

def test_monitoring_example_matches_bind_and_trusted_hosts(app, client, monkeypatch):
    root = Path(__file__).resolve().parent.parent
    configuration = dotenv_values(root / "deploy" / "app.env.example")
    hosts = configuration["TRUSTED_HOSTS"].split(",")
    settings = ast.parse((root / "deploy" / "gunicorn.conf.py").read_text())
    bind = next(ast.literal_eval(node.value) for node in settings.body
                if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "bind"
                                                       for target in node.targets))
    prometheus = (root / "deploy" / "prometheus.yml").read_text()
    target = re.search(r"job_name:\s*siwarga\s+static_configs:\s+- targets:\s*\['([^']+)'\]", prometheus)
    assert target is not None
    assert target.group(1) == bind
    monkeypatch.setitem(app.config, "TRUSTED_HOSTS", hosts)
    response = client.get("/metrics", base_url=f"http://{bind}")
    assert response.status_code == 200
    assert b"siwarga_database_up 1" in response.data
    assert client.get("/metrics", base_url=f"http://{bind}",
                      environ_overrides={"REMOTE_ADDR": "203.0.113.10"}).status_code == 404

def test_http_documentation_covers_all_application_routes(app):
    documentation = (Path(__file__).resolve().parent.parent / "docs" / "HTTP.md").read_text()
    for rule in app.url_map.iter_rules():
        if rule.endpoint != "static":
            for method in rule.methods - {"HEAD", "OPTIONS"}:
                assert f"| {method} | `{rule.rule}` |" in documentation
