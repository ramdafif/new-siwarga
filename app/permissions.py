from functools import wraps

from flask import abort
from flask_login import current_user, login_required
from sqlalchemy import select

from .models import Pengaduan, RT, db


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.status != "ACTIVE" or current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def scoped_tickets(user=None):
    user = user or current_user
    statement = select(Pengaduan).join(RT, Pengaduan.rt_id == RT.id)
    if user.status != "ACTIVE":
        return statement.where(False)
    if user.role == "SUPERADMIN":
        return statement
    if user.role == "WARGA":
        return statement.where(Pengaduan.pelapor_id == user.id)
    if user.role == "RT":
        return statement.where(Pengaduan.rt_id == user.rt_id, RT.rw_id == user.rw_id)
    if user.role == "RW":
        return statement.where(RT.rw_id == user.rw_id)
    if user.role == "KARANG_TARUNA":
        return statement.where(Pengaduan.ditugaskan_ke_id == user.id, RT.rw_id == user.rw_id)
    return statement.where(False)


def get_ticket(ticket_id, lock=False):
    statement = scoped_tickets().where(Pengaduan.id == ticket_id)
    if lock:
        statement = statement.with_for_update()
    ticket = db.session.execute(statement).unique().scalar_one_or_none()
    if ticket is None:
        abort(404)
    return ticket
