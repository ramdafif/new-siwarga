from email_validator import EmailNotValidError, validate_email
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from .models import Kategori, Pengaduan, RT, RW, User, db
from .permissions import roles_required
from .tickets import integer_field, required_text

bp = Blueprint("admin", __name__, url_prefix="/admin")


def save(message, endpoint):
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(409, description="Data sudah digunakan atau duplikat. Periksa nomor wilayah, nama kategori, atau email.")
    flash(message, "success")
    return redirect(url_for(endpoint))


def region_number():
    number = required_text("nomor", 1, 3)
    if not number.isascii() or not number.isdigit() or int(number) < 1:
        abort(400, description="Nomor wilayah harus berupa angka 1-999.")
    return number.zfill(2)


@bp.get("/wilayah")
@roles_required("SUPERADMIN")
def regions():
    rws = db.session.scalars(select(RW).order_by(RW.nomor)).all()
    users_per_rw = dict(db.session.execute(select(User.rw_id, func.count()).group_by(User.rw_id)).all())
    return render_template("admin/regions.html", title="Kelola wilayah", active_page="regions", rws=rws, users_per_rw=users_per_rw)


@bp.post("/rw")
@roles_required("SUPERADMIN")
def create_rw():
    db.session.add(RW(nomor=region_number(), nama_wilayah=required_text("nama_wilayah", 3, 120)))
    return save("RW baru berhasil ditambahkan.", "admin.regions")


@bp.post("/rw/<int:id>")
@roles_required("SUPERADMIN")
def edit_rw(id):
    rw = db.get_or_404(RW, id)
    if request.form.get("aksi") == "hapus":
        if rw.rts or db.session.scalar(select(User.id).where(User.rw_id == id).limit(1)):
            abort(409, description="RW masih memiliki RT atau pengguna. Data tidak dapat dihapus.")
        db.session.delete(rw)
    else:
        rw.nomor = region_number()
        rw.nama_wilayah = required_text("nama_wilayah", 3, 120)
    return save("Data RW berhasil diperbarui.", "admin.regions")


@bp.post("/rt")
@roles_required("SUPERADMIN")
def create_rt():
    rw_id = integer_field("rw_id")
    db.get_or_404(RW, rw_id)
    db.session.add(RT(rw_id=rw_id, nomor=region_number()))
    return save("RT baru berhasil ditambahkan.", "admin.regions")


@bp.post("/rt/<int:id>")
@roles_required("SUPERADMIN")
def edit_rt(id):
    rt = db.get_or_404(RT, id)
    if request.form.get("aksi") == "hapus":
        if db.session.scalar(select(User.id).where(User.rt_id == id).limit(1)) or db.session.scalar(select(Pengaduan.id).where(Pengaduan.rt_id == id).limit(1)):
            abort(409, description="RT masih digunakan oleh warga atau pengaduan. Data tidak dapat dihapus.")
        db.session.delete(rt)
    else:
        rt.nomor = region_number()
    return save("Data RT berhasil diperbarui.", "admin.regions")


@bp.get("/kategori")
@roles_required("SUPERADMIN")
def categories():
    categories = db.session.scalars(select(Kategori).order_by(Kategori.nama)).all()
    return render_template("admin/categories.html", title="Kategori pengaduan", active_page="categories", categories=categories)


@bp.post("/kategori")
@roles_required("SUPERADMIN")
def create_category():
    db.session.add(Kategori(nama=required_text("nama", 3, 80), deskripsi=request.form.get("deskripsi", "").strip()[:255], aktif=True))
    return save("Kategori berhasil ditambahkan.", "admin.categories")


@bp.post("/kategori/<int:id>")
@roles_required("SUPERADMIN")
def edit_category(id):
    category = db.get_or_404(Kategori, id)
    if request.form.get("aksi") == "hapus":
        if db.session.scalar(select(Pengaduan.id).where(Pengaduan.kategori_id == id).limit(1)):
            abort(409, description="Kategori sudah digunakan. Nonaktifkan kategori untuk menjaga riwayat laporan.")
        db.session.delete(category)
    else:
        category.nama = required_text("nama", 3, 80)
        category.deskripsi = request.form.get("deskripsi", "").strip()[:255]
        category.aktif = "aktif" in request.form
    return save("Kategori berhasil diperbarui.", "admin.categories")


def fill_user(user, creating=False):
    user.nama = required_text("nama", 2, 100)
    try:
        user.email = validate_email(required_text("email", 5, 190), check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        abort(400, description="Alamat email tidak valid.")
    role = request.form.get("role", user.role)
    allowed_roles = {"RW", "RT", "KARANG_TARUNA"} if creating or user.role != "WARGA" else {"WARGA"}
    if role not in allowed_roles:
        abort(400, description="Peran tidak valid. Akun warga dibuat melalui registrasi mandiri.")
    rw_id = integer_field("rw_id")
    db.get_or_404(RW, rw_id)
    rt_id = integer_field("rt_id") if role in {"RT", "WARGA"} else None
    if rt_id:
        rt = db.get_or_404(RT, rt_id)
        if rt.rw_id != rw_id:
            abort(400, description="RT tidak berada di RW yang dipilih.")
    user.role, user.rw_id, user.rt_id = role, rw_id, rt_id
    password = request.form.get("password", "")
    if creating or password:
        if not 10 <= len(password) <= 128:
            abort(400, description="Kata sandi awal harus terdiri dari 10-128 karakter.")
        user.set_password(password)
        user.must_change_password = True
    if creating:
        user.status = "ACTIVE"


@bp.route("/pengurus", methods=["GET", "POST"])
@roles_required("SUPERADMIN")
def users():
    if request.method == "POST":
        user = User()
        fill_user(user, creating=True)
        db.session.add(user)
        return save("Akun pengurus dibuat. Pengguna wajib mengganti kata sandi saat masuk pertama kali.", "admin.users")
    statement = select(User).order_by(User.created_at.desc(), User.id.desc())
    role = request.args.get("role", "")
    if role in {"SUPERADMIN", "RW", "RT", "KARANG_TARUNA", "WARGA"}:
        statement = statement.where(User.role == role)
    pagination = db.paginate(statement, per_page=12, error_out=False)
    rws = db.session.scalars(select(RW).order_by(RW.nomor)).all()
    rts = db.session.scalars(select(RT).order_by(RT.rw_id, RT.nomor)).all()
    return render_template("admin/users.html", title="Pengurus & akun", active_page="users", pagination=pagination, rws=rws, rts=rts)


@bp.post("/pengurus/<int:id>")
@roles_required("SUPERADMIN")
def edit_user(id):
    user = db.get_or_404(User, id)
    if user.role == "SUPERADMIN":
        abort(403, description="Akun superadmin tidak dapat diubah dari pengelolaan pengurus.")
    if request.form.get("aksi") == "toggle":
        user.status = "INACTIVE" if user.status == "ACTIVE" else "ACTIVE"
    else:
        fill_user(user)
    return save("Data akun berhasil diperbarui.", "admin.users")
