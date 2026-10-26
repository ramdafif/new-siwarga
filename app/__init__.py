import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, g, redirect, render_template, request, url_for
from flask_login import AnonymousUserMixin, LoginManager, current_user, logout_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFError, CSRFProtect
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from .constants import ROLE_LABELS, STATUSES, STATUS_LABELS
from .models import Notifikasi, User, db, utcnow

login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()


def create_app(test_config=None):
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY"),
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "mysql+pymysql://root@127.0.0.1/siwarga_db?charset=utf8mb4"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True, "pool_recycle": 1800},
        MAX_CONTENT_LENGTH=11 * 1024 * 1024,
        UPLOAD_FOLDER=str(Path(app.instance_path) / "uploads"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        WTF_CSRF_TIME_LIMIT=3600,
        DEMO_PASSWORD=os.getenv("DEMO_PASSWORD"),
    )
    if test_config:
        app.config.update(test_config)
    secret = app.config.get("SECRET_KEY")
    if not secret or len(secret) < 32 or secret.startswith("replace-with"):
        raise RuntimeError("Isi SECRET_KEY acak minimal 32 karakter di .env. Lihat README.md.")
    if not app.config["SQLALCHEMY_DATABASE_URI"].startswith("mysql+pymysql://"):
        raise RuntimeError("SiWarga memerlukan DATABASE_URL MySQL dengan driver mysql+pymysql.")
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Silakan masuk untuk melanjutkan."
    login_manager.login_message_category = "info"
    csrf.init_app(app)
    migrate.init_app(app, db, compare_type=True)

    from . import admin, auth, routes, tickets
    from .seed import seed_demo

    for blueprint in (auth.bp, routes.bp, tickets.bp, admin.bp):
        app.register_blueprint(blueprint)
    app.cli.add_command(seed_demo)

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    @app.before_request
    def check_account():
        if not current_user.is_authenticated or request.endpoint == "static":
            return None
        if current_user.status == "INACTIVE":
            logout_user()
            flash("Akun Anda dinonaktifkan. Hubungi pengurus RT.", "error")
            return redirect(url_for("auth.login"))
        if current_user.status == "PENDING" and request.endpoint not in {"auth.waiting", "auth.logout"}:
            return redirect(url_for("auth.waiting"))
        if current_user.status == "ACTIVE" and current_user.must_change_password and request.endpoint not in {"auth.account", "auth.logout"}:
            return redirect(url_for("auth.account"))
        return None

    @app.context_processor
    def shared_context():
        unread = 0
        if current_user.is_authenticated:
            unread = db.session.scalar(select(func.count()).select_from(Notifikasi).where(
                Notifikasi.user_id == current_user.id, Notifikasi.sudah_dibaca.is_(False)))
        return dict(role_labels=ROLE_LABELS, status_labels=STATUS_LABELS,
                    statuses=STATUSES, unread_count=unread, today=utcnow() + timedelta(hours=7))

    @app.template_filter("tanggal")
    def tanggal(value, mode="short"):
        if not value:
            return "-"
        local = value + timedelta(hours=7)
        months = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")
        result = f"{local.day:02d} {months[local.month - 1]} {local.year}"
        return f"{result}, {local:%H:%M} WIB" if mode == "full" else result

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' blob:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; font-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        )
        if current_user.is_authenticated:
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return render_template("error.html", code=400, message="Formulir kedaluwarsa atau token keamanan tidak valid. Muat ulang halaman dan coba lagi."), 400

    @app.errorhandler(HTTPException)
    def http_error(error):
        messages = {403: "Anda tidak memiliki izin untuk membuka halaman atau melakukan tindakan ini.",
                    404: "Halaman atau data tidak ditemukan dalam akses Anda.",
                    413: "Unggahan terlalu besar. Maksimal 3 foto, masing-masing 3 MB."}
        return render_template("error.html", code=error.code, message=messages.get(error.code, error.description)), error.code

    @app.errorhandler(SQLAlchemyError)
    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        g._login_user = AnonymousUserMixin()
        app.logger.error("Terjadi kesalahan aplikasi", exc_info=error)
        return render_template("error.html", code=500, message="Layanan belum dapat memproses permintaan. Periksa koneksi MySQL atau hubungi pengelola."), 500

    return app
