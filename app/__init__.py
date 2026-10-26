import os
import logging
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from flask_login import AnonymousUserMixin, LoginManager, current_user, logout_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFError, CSRFProtect
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from .constants import ROLE_LABELS, STATUSES, STATUS_LABELS
from .models import Notifikasi, User, db, utcnow
from .security import TelemetryReadOnlySessionInterface
from .observability import init_observability

login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()


def create_app(test_config=None):
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    app = Flask(__name__, instance_relative_config=True)
    app.session_interface = TelemetryReadOnlySessionInterface()
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY"),
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "mysql+pymysql://root@127.0.0.1/siwarga_db?charset=utf8mb4"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True, "pool_recycle": 1800, "hide_parameters": True,
                                   "pool_timeout": 5, "connect_args": {"connect_timeout": 3}},
        MAX_CONTENT_LENGTH=11 * 1024 * 1024,
        UPLOAD_FOLDER=os.getenv("UPLOAD_FOLDER", str(Path(app.instance_path) / "uploads")),
        APP_ENV=os.getenv("APP_ENV", "local"),
        LOGIN_RATE_LIMIT_BACKEND=os.getenv("LOGIN_RATE_LIMIT_BACKEND", "memory"),
        REDIS_URL=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
        REDIS_NAMESPACE=os.getenv("REDIS_NAMESPACE", "siwarga:local"),
        PROXY_HOPS=int(os.getenv("PROXY_HOPS", "0")),
        TRUSTED_HOSTS=[host.strip() for host in os.getenv("TRUSTED_HOSTS", "").split(",") if host.strip()] or None,
        PROFILE_REQUESTS=os.getenv("PROFILE_REQUESTS", "false").lower() == "true",
        ENABLE_WEB_VITALS=os.getenv("ENABLE_WEB_VITALS", "true").lower() == "true",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_REFRESH_EACH_REQUEST=False,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        WTF_CSRF_TIME_LIMIT=3600,
        DEMO_PASSWORD=os.getenv("DEMO_PASSWORD"),
    )
    if test_config:
        app.config.update(test_config)
    app.logger.setLevel(logging.INFO)
    secret = app.config.get("SECRET_KEY")
    if not secret or len(secret) < 32 or secret.startswith("replace-with"):
        raise RuntimeError("Isi SECRET_KEY acak minimal 32 karakter di .env. Lihat README.md.")
    if not app.config["SQLALCHEMY_DATABASE_URI"].startswith("mysql+pymysql://"):
        raise RuntimeError("SiWarga memerlukan DATABASE_URL MySQL dengan driver mysql+pymysql.")
    if app.config["LOGIN_RATE_LIMIT_BACKEND"] not in {"memory", "redis"}:
        raise RuntimeError("LOGIN_RATE_LIMIT_BACKEND harus memory atau redis.")
    if app.config["PROXY_HOPS"] not in {0, 1}:
        raise RuntimeError("PROXY_HOPS hanya mendukung 0 atau 1 reverse proxy tepercaya.")
    if app.config["APP_ENV"] in {"staging", "production"}:
        if app.config["LOGIN_RATE_LIMIT_BACKEND"] != "redis" or not app.config["SESSION_COOKIE_SECURE"] or not app.config["TRUSTED_HOSTS"]:
            raise RuntimeError("Staging/produksi wajib menggunakan Redis, secure cookie, dan TRUSTED_HOSTS.")
    if app.config["PROXY_HOPS"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Silakan masuk untuk melanjutkan."
    login_manager.login_message_category = "info"
    init_observability(app)
    csrf.init_app(app)
    migrate.init_app(app, db, compare_type=True)

    from . import admin, auth, routes, tickets
    from .seed import seed_demo

    for blueprint in (auth.bp, routes.bp, tickets.bp, admin.bp):
        app.register_blueprint(blueprint)
    app.cli.add_command(seed_demo)
    from .commands import backfill_photos, upgrade_safe
    app.cli.add_command(backfill_photos)
    app.cli.add_command(upgrade_safe)
    if app.config["LOGIN_RATE_LIMIT_BACKEND"] == "memory" and not app.testing:
        app.logger.warning("Rate limit lokal per proses; gunakan Redis sebelum multi-worker/staging.")

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    @app.before_request
    def check_account():
        if request.endpoint in {"static", "ops.live", "ops.ready", "ops.metrics"}:
            return None
        if not current_user.is_authenticated:
            return None
        if session.get("account_version") != current_user.session_version:
            logout_user()
            session.clear()
            flash("Sesi berakhir setelah perubahan akun. Silakan masuk kembali.", "info")
            return redirect(url_for("auth.login"))
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
        if current_user.is_authenticated and not getattr(g, "rendering_error", False):
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
        if request.endpoint not in {"static", "ops.live", "ops.ready", "ops.metrics"} and current_user.is_authenticated:
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
        g.rendering_error = True
        app.logger.error("Terjadi kesalahan aplikasi request_id=%s", getattr(g, "request_id", ""), exc_info=error)
        return render_template("error.html", code=500, message="Layanan belum dapat memproses permintaan. Periksa koneksi MySQL atau hubungi pengelola."), 500

    return app
