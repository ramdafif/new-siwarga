from datetime import timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, select, update

from .constants import STATUSES
from .models import Kategori, Notifikasi, Pengaduan, RiwayatStatus, User, db, utcnow
from .permissions import roles_required, scoped_tickets

bp = Blueprint("main", __name__)


@bp.get("/")
def landing():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("landing.html", title="Lingkungan nyaman dimulai dari kepedulian")


@bp.get("/dashboard")
@login_required
def dashboard():
    scope = scoped_tickets().subquery()
    counts = {status: 0 for status in STATUSES}
    counts.update(dict(db.session.execute(select(scope.c.status, func.count()).group_by(scope.c.status)).all()))
    total = sum(counts.values())
    recent = db.session.execute(scoped_tickets().order_by(Pengaduan.created_at.desc(), Pengaduan.id.desc()).limit(5)).unique().scalars().all()
    activities = db.session.scalars(select(RiwayatStatus).where(RiwayatStatus.pengaduan_id.in_(select(scope.c.id)))
                                   .order_by(RiwayatStatus.created_at.desc(), RiwayatStatus.id.desc()).limit(4)).all()
    local_now = utcnow() + timedelta(hours=7)
    start = local_now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)
    local_date = func.date(func.convert_tz(scope.c.created_at, "+00:00", "+07:00"))
    daily = dict(db.session.execute(select(local_date, func.count()).where(scope.c.created_at >= start - timedelta(hours=7))
                                    .group_by(local_date)).all())
    peak = max(daily.values(), default=1) or 1
    days = ("Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min")
    chart = []
    for index in range(7):
        day = start + timedelta(days=index)
        count = daily.get(day.date(), 0)
        chart.append(dict(label=days[day.weekday()], count=count, height=max(5, round(count / peak * 100))))
    category_counts = db.session.execute(select(Kategori.nama, func.count()).join(scope, scope.c.kategori_id == Kategori.id)
                                         .group_by(Kategori.id, Kategori.nama).order_by(func.count().desc()).limit(4)).all()
    pending = 0
    if current_user.role == "RT":
        pending = db.session.scalar(select(func.count()).select_from(User).where(User.role == "WARGA", User.status == "PENDING",
                                                                                User.rw_id == current_user.rw_id, User.rt_id == current_user.rt_id))
    return render_template("dashboard.html", title="Dashboard", active_page="dashboard", counts=counts,
                           total=total, recent=recent, activities=activities, chart=chart, category_counts=category_counts,
                           pending=pending, completion=round(counts["SELESAI"] / total * 100) if total else 0)


@bp.get("/notifikasi")
@login_required
def notifications():
    pagination = db.paginate(select(Notifikasi).where(Notifikasi.user_id == current_user.id)
                             .order_by(Notifikasi.created_at.desc(), Notifikasi.id.desc()), per_page=15, error_out=False)
    return render_template("notifications.html", title="Notifikasi", active_page="notifications", pagination=pagination)


@bp.post("/notifikasi/<int:id>/baca")
@login_required
def read_notification(id):
    notification = db.session.scalar(select(Notifikasi).where(Notifikasi.id == id, Notifikasi.user_id == current_user.id))
    if not notification:
        abort(404)
    notification.sudah_dibaca = True
    db.session.commit()
    if notification.pengaduan_id:
        return redirect(url_for("tickets.detail", id=notification.pengaduan_id))
    return redirect(url_for("main.verify_residents" if current_user.role == "RT" else "main.notifications"))


@bp.post("/notifikasi/baca-semua")
@login_required
def read_all_notifications():
    db.session.execute(update(Notifikasi).where(Notifikasi.user_id == current_user.id).values(sudah_dibaca=True))
    db.session.commit()
    flash("Semua notifikasi ditandai sudah dibaca.", "success")
    return redirect(url_for("main.notifications"))


@bp.get("/rt/verifikasi-warga")
@roles_required("RT")
def verify_residents():
    status = request.args.get("status", "PENDING")
    if status not in {"PENDING", "ACTIVE", "INACTIVE"}:
        abort(400)
    pagination = db.paginate(select(User).where(User.role == "WARGA", User.rt_id == current_user.rt_id,
                                               User.rw_id == current_user.rw_id, User.status == status)
                             .order_by(User.created_at.desc()), per_page=15, error_out=False)
    return render_template("rt/residents.html", title="Verifikasi warga", active_page="residents", pagination=pagination, selected_status=status)


@bp.post("/rt/verifikasi-warga/<int:id>")
@roles_required("RT")
def verify_resident(id):
    user = db.session.scalar(select(User).where(User.id == id, User.role == "WARGA", User.rt_id == current_user.rt_id,
                                               User.rw_id == current_user.rw_id).with_for_update())
    if not user:
        abort(404)
    action = request.form.get("aksi")
    if action not in {"terima", "nonaktifkan"}:
        abort(400)
    user.status = "ACTIVE" if action == "terima" else "INACTIVE"
    db.session.add(Notifikasi(user_id=user.id, pesan="Akun Anda telah diverifikasi. Selamat bergabung di SiWarga!" if action == "terima" else "Akun Anda dinonaktifkan oleh pengurus RT. Hubungi pengurus untuk informasi."))
    db.session.commit()
    flash(f"Akun {user.nama} berhasil {'diaktifkan' if action == 'terima' else 'dinonaktifkan'}.", "success")
    return redirect(url_for("main.verify_residents"))
