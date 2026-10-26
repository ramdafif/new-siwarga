import secrets
from datetime import datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, send_from_directory, current_app, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from .constants import STATUSES
from .forms import ComplaintForm
from .models import Kategori, Komentar, Lampiran, Notifikasi, Pengaduan, RT, RiwayatStatus, TindakLanjut, User, db, utcnow
from .permissions import get_ticket, require_ticket_access, roles_required, scoped_tickets
from .uploads import commit_with_uploads, validate_uploads, variant_filename
from .security import issue_submission_token, read_submission_token
from .query_options import summary_options

bp = Blueprint("tickets", __name__)


def required_text(name, minimum=5, maximum=3000):
    value = request.form.get(name, "").strip()
    if not minimum <= len(value) <= maximum:
        abort(400, description=f"Isian {name.replace('_', ' ')} harus terdiri dari {minimum}-{maximum} karakter.")
    return value


def integer_field(name):
    try:
        value = int(request.form.get(name, ""))
        if value <= 0:
            raise ValueError
        return value
    except ValueError:
        abort(400, description="Pilihan data tidak valid.")


def audit(ticket, note, previous=None):
    db.session.add(RiwayatStatus(pengaduan_id=ticket.id, aktor_id=current_user.id,
                                status_lama=previous or ticket.status, status_baru=ticket.status, catatan=note))
    ticket.updated_at = utcnow()


def notify(ticket, message, include_managers=False):
    recipients = {ticket.pelapor_id}
    if ticket.ditugaskan_ke_id:
        recipients.add(ticket.ditugaskan_ke_id)
    if include_managers:
        managers = db.session.scalars(select(User.id).where(
            User.status == "ACTIVE", User.rw_id == ticket.rt.rw_id,
            or_(User.role == "RW", (User.role == "RT") & (User.rt_id == ticket.rt_id))))
        recipients.update(managers)
    for user_id in recipients - {current_user.id}:
        db.session.add(Notifikasi(user_id=user_id, pengaduan_id=ticket.id, pesan=message[:255]))


def ensure_processing(ticket):
    if ticket.status != "DIPROSES":
        abort(409, description="Tindakan ini hanya dapat dilakukan pada pengaduan berstatus sedang diproses.")


@bp.get("/pengaduan")
@login_required
def index():
    statement = scoped_tickets().options(*summary_options())
    query = request.args.get("q", "").strip()[:160]
    if query:
        statement = statement.where(or_(Pengaduan.judul.contains(query, autoescape=True),
                                        Pengaduan.nomor_tiket.contains(query, autoescape=True)))
    status = request.args.get("status", "")
    if status:
        if status not in STATUSES:
            abort(400, description="Filter status tidak valid.")
        statement = statement.where(Pengaduan.status == status)
    category_id = request.args.get("kategori", type=int)
    if category_id:
        statement = statement.where(Pengaduan.kategori_id == category_id)
    rt_id = request.args.get("rt", type=int)
    if rt_id:
        statement = statement.where(Pengaduan.rt_id == rt_id)
    for name, column, end_of_day in (("dari", Pengaduan.created_at, False), ("sampai", Pengaduan.created_at, True)):
        value = request.args.get(name)
        if value:
            try:
                date = datetime.strptime(value, "%Y-%m-%d") - timedelta(hours=7)
            except ValueError:
                abort(400, description="Tanggal filter tidak valid.")
            statement = statement.where(column < date + timedelta(days=1)) if end_of_day else statement.where(column >= date)
    pagination = db.paginate(statement.order_by(Pengaduan.created_at.desc(), Pengaduan.id.desc()), per_page=10, error_out=False)
    categories = db.session.scalars(select(Kategori).order_by(Kategori.nama)).all()
    rt_statement = select(RT).order_by(RT.nomor)
    if current_user.role != "SUPERADMIN":
        rt_statement = rt_statement.where(RT.rw_id == current_user.rw_id)
    rts = db.session.scalars(rt_statement).all()
    page_links = {page: url_for("tickets.index", **dict(request.args.to_dict(), page=page)) for page in pagination.iter_pages() if page}
    return render_template("pengaduan/index.html", title="Tugas saya" if current_user.role == "KARANG_TARUNA" else "Pengaduan",
                           active_page="tickets", pagination=pagination, categories=categories, rts=rts, page_links=page_links)


@bp.get("/pengaduan/baru")
@bp.post("/pengaduan")
@roles_required("WARGA")
def create():
    form = ComplaintForm()
    if request.method == "GET":
        form.submission_token.data = issue_submission_token(current_user.id)
    categories = db.session.scalars(select(Kategori).where(Kategori.aktif.is_(True)).order_by(Kategori.nama)).all()
    form.kategori_id.choices = [(0, "Pilih kategori pengaduan")] + [(item.id, item.nama) for item in categories]
    if request.method == "POST":
        submission = read_submission_token(form.submission_token.data, current_user.id)
        existing_id = db.session.scalar(select(Pengaduan.id).where(Pengaduan.pelapor_id == current_user.id, Pengaduan.submission_token == submission))
        if existing_id:
            return redirect(url_for("tickets.detail", id=existing_id))
    if form.validate_on_submit():
        prepared = validate_uploads(request.files.getlist("foto"))
        rt = db.session.get(RT, current_user.rt_id)
        if not rt or rt.rw_id != current_user.rw_id:
            abort(403)
        ticket = Pengaduan(nomor_tiket=f"SW-{utcnow():%Y%m}-{secrets.token_hex(5).upper()}",
                           pelapor_id=current_user.id, submission_token=submission, rt_id=current_user.rt_id, kategori_id=form.kategori_id.data,
                           judul=form.judul.data.strip(), deskripsi=form.deskripsi.data.strip(),
                           lokasi_teks=form.lokasi_teks.data.strip(), status="MENUNGGU_VERIFIKASI")
        db.session.add(ticket)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            existing_id = db.session.scalar(select(Pengaduan.id).where(Pengaduan.pelapor_id == current_user.id, Pengaduan.submission_token == submission))
            if existing_id:
                return redirect(url_for("tickets.detail", id=existing_id))
            raise
        db.session.add(RiwayatStatus(pengaduan_id=ticket.id, aktor_id=current_user.id, status_lama=None,
                                    status_baru=ticket.status, catatan="Pengaduan dikirim. Menunggu verifikasi pengurus RT."))
        notify(ticket, f"Pengaduan baru {ticket.nomor_tiket}: {ticket.judul}", include_managers=True)
        commit_with_uploads(ticket, prepared, "LAPORAN")
        flash("Pengaduan berhasil dikirim. Terima kasih sudah peduli lingkungan!", "success")
        return redirect(url_for("tickets.detail", id=ticket.id))
    return render_template("pengaduan/create.html", form=form, title="Buat pengaduan", active_page="new")


@bp.get("/pengaduan/<int:id>")
@login_required
def detail(id):
    ticket = get_ticket(id)
    members = []
    if current_user.role in {"RT", "RW"}:
        members = db.session.scalars(select(User).where(User.role == "KARANG_TARUNA", User.status == "ACTIVE",
                                                       User.rw_id == ticket.rt.rw_id).order_by(User.nama)).all()
    return render_template("pengaduan/detail.html", ticket=ticket, members=members, title="Detail pengaduan", active_page="tickets")


@bp.post("/pengaduan/<int:id>/verifikasi")
@roles_required("RT")
def verify(id):
    ticket = get_ticket(id, lock=True)
    if ticket.status != "MENUNGGU_VERIFIKASI":
        abort(409, description="Pengaduan ini sudah diverifikasi. Status tidak dapat diubah kembali.")
    action = request.form.get("aksi")
    old_status = ticket.status
    if action == "terima":
        ticket.status = "DIPROSES"
        note = "Pengaduan telah diverifikasi dan diterima oleh pengurus RT."
    elif action == "tolak":
        note = required_text("alasan", minimum=10)
        ticket.alasan_penolakan = note
        ticket.status = "DITOLAK"
    else:
        abort(400, description="Tindakan verifikasi tidak valid.")
    audit(ticket, note, old_status)
    notify(ticket, f"{ticket.nomor_tiket}: pengaduan {'diterima dan diproses' if action == 'terima' else 'ditolak'}. {note}", True)
    db.session.commit()
    flash("Verifikasi pengaduan berhasil disimpan.", "success")
    return redirect(url_for("tickets.detail", id=id))


@bp.post("/pengaduan/<int:id>/tugaskan")
@roles_required("RT", "RW")
def assign(id):
    ticket = get_ticket(id, lock=True)
    ensure_processing(ticket)
    member = db.session.scalar(select(User).where(User.id == integer_field("petugas_id"), User.role == "KARANG_TARUNA",
                                                  User.status == "ACTIVE", User.rw_id == ticket.rt.rw_id).with_for_update())
    if not member:
        abort(400, description="Pilih anggota Karang Taruna aktif dari RW yang sama.")
    previous_assignee = ticket.ditugaskan_ke_id
    ticket.ditugaskan_ke_id = member.id
    note = f"Pengaduan ditugaskan kepada {member.nama} (Karang Taruna)."
    audit(ticket, note)
    notify(ticket, f"{ticket.nomor_tiket}: {note}", True)
    if previous_assignee and previous_assignee != member.id:
        db.session.add(Notifikasi(user_id=previous_assignee, pesan=f"Penugasan {ticket.nomor_tiket} telah dialihkan oleh pengurus."))
    db.session.commit()
    flash("Penugasan Karang Taruna berhasil diperbarui.", "success")
    return redirect(url_for("tickets.detail", id=id))


@bp.post("/pengaduan/<int:id>/tindak-lanjut")
@roles_required("RT", "RW", "KARANG_TARUNA")
def progress(id):
    ticket = get_ticket(id, lock=True)
    ensure_processing(ticket)
    note = required_text("catatan", minimum=10)
    prepared = validate_uploads(request.files.getlist("foto"))
    db.session.add(TindakLanjut(pengaduan_id=ticket.id, petugas_id=current_user.id, catatan=note))
    audit(ticket, f"Catatan tindak lanjut: {note}")
    notify(ticket, f"{ticket.nomor_tiket}: ada pembaruan progres dari {current_user.nama}.", True)
    commit_with_uploads(ticket, prepared, "PROGRES")
    flash("Progres penanganan berhasil ditambahkan.", "success")
    return redirect(url_for("tickets.detail", id=id))


@bp.post("/pengaduan/<int:id>/selesai")
@roles_required("RT", "RW")
def complete(id):
    ticket = get_ticket(id, lock=True)
    ensure_processing(ticket)
    note = required_text("catatan", minimum=10)
    prepared = validate_uploads(request.files.getlist("foto"))
    previous = ticket.status
    ticket.status = "SELESAI"
    ticket.selesai_at = utcnow()
    audit(ticket, note, previous)
    notify(ticket, f"{ticket.nomor_tiket}: pengaduan telah selesai. {note}", True)
    commit_with_uploads(ticket, prepared, "PENYELESAIAN")
    flash("Pengaduan ditandai selesai. Terima kasih atas kerja samanya!", "success")
    return redirect(url_for("tickets.detail", id=id))


@bp.post("/pengaduan/<int:id>/komentar")
@roles_required("WARGA", "RT", "RW", "KARANG_TARUNA")
def comment(id):
    ticket = get_ticket(id, lock=True)
    text = required_text("isi", minimum=2, maximum=2000)
    db.session.add(Komentar(pengaduan_id=ticket.id, user_id=current_user.id, isi=text))
    notify(ticket, f"{ticket.nomor_tiket}: {current_user.nama} menambahkan komentar.", True)
    db.session.commit()
    flash("Komentar Anda berhasil dikirim.", "success")
    return redirect(url_for("tickets.detail", id=id, _anchor="diskusi"))


@bp.get("/lampiran/<int:id>")
@login_required
def attachment(id):
    file = db.session.get(Lampiran, id)
    if not file:
        abort(404)
    require_ticket_access(file.pengaduan_id)
    variant = request.args.get("variant", "original")
    if variant not in {"original", "thumbnail", "display"}:
        abort(400, description="Varian foto tidak valid.")
    stored = file.nama_tersimpan if variant == "original" else variant_filename(file.nama_tersimpan, variant)
    response = send_from_directory(current_app.config["UPLOAD_FOLDER"], stored,
                                   download_name=file.nama_asli if variant == "original" else stored,
                                   mimetype="image/webp" if variant != "original" else None, max_age=0)
    response.headers["Cache-Control"] = "private, no-store"
    return response
