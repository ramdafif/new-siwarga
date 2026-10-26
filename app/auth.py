import secrets

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import lazyload
from werkzeug.security import check_password_hash, generate_password_hash

from .forms import LoginForm, PasswordForm, RegisterForm
from .models import Notifikasi, RT, RW, User, db
from .security import (LimiterUnavailable, fingerprint, login_keys, login_limiter, remember_session,
                       revoke_sessions, security_event)

bp = Blueprint("auth", __name__)
_dummy_hash = generate_password_hash("not-a-real-account-password")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        keys = login_keys(email, request.remote_addr)
        token = secrets.token_hex(16)
        try:
            limiter = login_limiter()
            if not limiter.reserve(keys, token):
                security_event("login.throttled", outcome="denied", details={"account": fingerprint(email), "client": fingerprint(request.remote_addr or "unknown")}, commit=True)
                abort(429, description="Terlalu banyak percobaan masuk. Silakan coba kembali 15 menit lagi.")
            user = db.session.scalar(select(User).where(User.email == email))
            valid = user.check_password(form.password.data) if user else check_password_hash(_dummy_hash, form.password.data)
            success = bool(user and valid and user.status != "INACTIVE")
            limiter.finish(keys, token, success)
        except LimiterUnavailable:
            current_app.logger.error("security login.backend_unavailable request_id=%s", getattr(g, "request_id", ""))
            abort(503, description="Layanan masuk sementara tidak tersedia. Silakan coba kembali.")
        security_event("login.success" if success else "login.failure", outcome="success" if success else "denied",
                       target=user, details={"account": fingerprint(email), "client": fingerprint(request.remote_addr or "unknown")}, commit=True)
        if success:
            session.clear()
            login_user(user)
            remember_session(user)
            session.permanent = True
            return redirect(url_for("auth.waiting" if user.status == "PENDING" else "main.dashboard"))
        flash("Email atau kata sandi tidak sesuai, atau akun tidak aktif.", "error")
    return render_template("auth/login.html", form=form, title="Selamat datang kembali")

@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = RegisterForm()
    rws = db.session.scalars(select(RW).order_by(RW.nomor)).all()
    rts = db.session.scalars(select(RT).order_by(RT.rw_id, RT.nomor)).all()
    form.rw_id.choices = [(0, "Pilih RW")] + [(rw.id, f"RW {rw.nomor} - {rw.nama_wilayah}") for rw in rws]
    form.rt_id.choices = [(0, "Pilih RT")] + [(rt.id, f"RT {rt.nomor} / RW {rt.rw.nomor}") for rt in rts]
    if form.validate_on_submit():
        rt = db.session.get(RT, form.rt_id.data)
        email = form.email.data.strip().lower()
        if not rt or rt.rw_id != form.rw_id.data:
            form.rt_id.errors.append("RT harus berada di RW yang dipilih.")
        elif db.session.scalar(select(User.id).where(User.email == email)):
            form.email.errors.append("Email sudah terdaftar. Silakan gunakan email lain atau masuk.")
        else:
            user = User(nama=form.nama.data.strip(), email=email, no_hp=form.no_hp.data.strip() or None,
                        role="WARGA", status="PENDING", rw_id=form.rw_id.data, rt_id=form.rt_id.data)
            user.set_password(form.password.data)
            db.session.add(user)
            managers = db.session.scalars(select(User).where(User.role == "RT", User.rt_id == rt.id,
                                                             User.rw_id == rt.rw_id, User.status == "ACTIVE")).all()
            for manager in managers:
                db.session.add(Notifikasi(user_id=manager.id, pesan=f"{user.nama} mendaftar sebagai warga. Silakan verifikasi akun."))
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                form.email.errors.append("Email sudah terdaftar.")
            else:
                session.clear()
                login_user(user)
                remember_session(user)
                return redirect(url_for("auth.waiting"))
    return render_template("auth/register.html", form=form, rts=rts, title="Jadi bagian dari lingkungan yang lebih baik")


@bp.get("/menunggu-verifikasi")
@login_required
def waiting():
    if current_user.status == "ACTIVE":
        return redirect(url_for("main.dashboard"))
    return render_template("auth/waiting.html", title="Menunggu verifikasi")


@bp.post("/logout")
@login_required
def logout():
    security_event("logout", commit=True)
    logout_user()
    session.clear()
    flash("Anda telah keluar dengan aman.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/akun", methods=["GET", "POST"])
@login_required
def account():
    form = PasswordForm()
    if form.validate_on_submit():
        db.session.execute(select(User).where(User.id == current_user.id).options(lazyload("*")).with_for_update().execution_options(populate_existing=True)).unique().scalar_one()
        if session.get("account_version") != current_user.session_version:
            logout_user()
            session.clear()
            return redirect(url_for("auth.login"))
        if not current_user.check_password(form.current_password.data):
            form.current_password.errors.append("Kata sandi saat ini tidak sesuai.")
        elif current_user.check_password(form.password.data):
            form.password.errors.append("Gunakan kata sandi yang berbeda dari sebelumnya.")
        else:
            current_user.set_password(form.password.data)
            current_user.must_change_password = False
            revoke_sessions(current_user)
            security_event("password.changed", target=current_user)
            db.session.commit()
            remember_session(current_user)
            flash("Kata sandi berhasil diperbarui.", "success")
            return redirect(url_for("main.dashboard"))
    return render_template("auth/account.html", form=form, title="Pengaturan akun", active_page="account")
