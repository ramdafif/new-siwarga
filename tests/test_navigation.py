from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import pytest
from sqlalchemy import func, select
from werkzeug.exceptions import HTTPException

from app.models import Notifikasi, Pengaduan, db


class PageControls(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.links = []
        self.forms = []
        self.current_form = None
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if tag == "a" and "href" in attributes:
            self.links.append(attributes["href"])
        elif tag == "form":
            assert self.current_form is None, "Nested forms are not valid HTML"
            self.current_form = {"attributes": attributes, "hidden": {}, "buttons": []}
            self.forms.append(self.current_form)
        elif self.current_form is not None:
            if tag == "input" and attributes.get("type") == "hidden" and "name" in attributes:
                self.current_form["hidden"][attributes["name"]] = attributes.get("value", "")
            elif tag in {"button", "input"} and ("formaction" in attributes or "formmethod" in attributes):
                self.current_form["buttons"].append(attributes)

    def handle_endtag(self, tag):
        if tag == "form":
            self.current_form = None


def assert_controls_resolve(app, html, source):
    controls = PageControls(html)
    adapter = app.url_map.bind("localhost")
    targets = [(href, "GET") for href in controls.links]
    for form in controls.forms:
        attributes = form["attributes"]
        action = attributes.get("action") or source
        method = attributes.get("method", "GET").upper()
        targets.append((action, method))
        for button in form["buttons"]:
            targets.append((button.get("formaction", action), button.get("formmethod", method).upper()))
    for target, method in targets:
        if target.startswith("#"):
            continue
        parsed = urlsplit(urljoin("http://localhost" + source, target))
        if parsed.netloc != "localhost":
            continue
        try:
            adapter.match(parsed.path, method=method)
        except HTTPException as error:
            pytest.fail(f"{source}: {method} {target} resolves to HTTP {error.code}")
    return controls


@pytest.mark.parametrize("handle", [None, "owner", "rt", "rw", "kt", "admin", "pending"])
def test_rendered_navigation_and_form_methods(app, client, login, data, handle):
    if handle is None:
        pages = ["/", "/login", "/register"]
    else:
        login(handle)
        if handle == "pending":
            pages = ["/menunggu-verifikasi"]
        else:
            notification = Notifikasi(user_id=data["users"][handle].id, pesan="Pembaruan pengaduan.",
                                      pengaduan_id=data["tickets"]["assigned"].id)
            db.session.add(notification)
            db.session.commit()
            pages = ["/dashboard", "/pengaduan", "/pengaduan?q=not-found", "/notifikasi", "/akun"]
            if handle == "owner":
                pages.append("/pengaduan/baru")
            if handle == "rt":
                pages.append("/rt/verifikasi-warga")
            if handle == "admin":
                pages.extend(["/admin/wilayah", "/admin/kategori", "/admin/pengurus", "/admin/pengurus?page=2"])
            visible = ["assigned", "completed"] if handle == "kt" else ["waiting", "assigned", "unassigned", "completed"]
            pages.extend(f"/pengaduan/{data['tickets'][name].id}" for name in visible)
    for source in pages:
        response = client.get(source)
        assert response.status_code == 200, source
        assert_controls_resolve(app, response.get_data(as_text=True), source)


def complaint_form(response):
    controls = PageControls(response.get_data(as_text=True))
    return next(form for form in controls.forms if "submission_token" in form["hidden"])


def test_complaint_uses_rendered_action_with_csrf(app, client, login, data):
    login("owner")
    app.config["WTF_CSRF_ENABLED"] = True
    form = complaint_form(client.get("/pengaduan/baru"))
    assert form["attributes"]["action"] == "/pengaduan"
    values = dict(form["hidden"], judul="Lampu jalan padam di Gang Melati", kategori_id=str(data["category"].id),
                  lokasi_teks="Gang Melati nomor 12", deskripsi="Lampu jalan padam sejak kemarin dan membahayakan warga.")
    before = db.session.scalar(select(func.count()).select_from(Pengaduan))
    response = client.post(form["attributes"]["action"], data=values, follow_redirects=True)
    assert response.status_code == 200
    assert db.session.scalar(select(func.count()).select_from(Pengaduan)) == before + 1
    assert b"Lampu jalan padam di Gang Melati" in response.data


def test_invalid_complaint_keeps_working_form_and_create_link(app, client, login, data):
    login("owner")
    app.config["WTF_CSRF_ENABLED"] = True
    form = complaint_form(client.get("/pengaduan/baru"))
    response = client.post("/pengaduan", data=form["hidden"])
    assert response.status_code == 200
    controls = assert_controls_resolve(app, response.get_data(as_text=True), "/pengaduan")
    assert "/pengaduan/baru" in controls.links
    corrected = complaint_form(response)
    assert corrected["attributes"]["action"] == "/pengaduan"
    values = dict(corrected["hidden"], judul="Lampu jalan padam di Gang Melati", kategori_id=str(data["category"].id),
                  lokasi_teks="Gang Melati nomor 12", deskripsi="Lampu jalan padam sejak kemarin dan membahayakan warga.")
    assert client.post(corrected["attributes"]["action"], data=values).status_code == 302


@pytest.mark.parametrize("method,path,allowed", [
    ("GET", "/logout", "POST"),
    ("POST", "/dashboard", "GET"),
    ("POST", "/pengaduan/baru", "GET"),
    ("GET", "/telemetry/vitals", "POST"),
])
def test_method_errors_preserve_allow_header(client, method, path, allowed):
    response = client.open(path, method=method)
    assert response.status_code == 405
    assert allowed in {value.strip() for value in response.headers.get("Allow", "").split(",")}
