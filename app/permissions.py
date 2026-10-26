from functools import wraps

from flask import abort
from flask_login import current_user, login_required
from sqlalchemy import and_, select
from sqlalchemy.orm import lazyload

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


def ticket_scope_filter(user=None, joined_region=False):
    user = user or current_user
    if user.status != "ACTIVE":
        return False
    if user.role == "SUPERADMIN":
        return True
    if user.role == "WARGA":
        return Pengaduan.pelapor_id == user.id
    region = RT.rw_id == user.rw_id if joined_region else Pengaduan.rt.has(RT.rw_id == user.rw_id)
    if user.role == "RT":
        return and_(Pengaduan.rt_id == user.rt_id, region)
    if user.role == "RW":
        return region
    if user.role == "KARANG_TARUNA":
        return and_(Pengaduan.ditugaskan_ke_id == user.id, region)
    return False


def scoped_tickets(user=None):
    return select(Pengaduan).join(RT, Pengaduan.rt_id == RT.id).where(ticket_scope_filter(user, joined_region=True))


def require_ticket_access(ticket_id):
    ticket_id = db.session.scalar(scoped_tickets().with_only_columns(Pengaduan.id).where(Pengaduan.id == ticket_id))
    if ticket_id is None:
        abort(404)


def get_ticket(ticket_id, lock=False):
    if lock:
        statement = (select(Pengaduan).where(Pengaduan.id == ticket_id, ticket_scope_filter())
                     .options(lazyload("*")).with_for_update().execution_options(populate_existing=True))
    else:
        statement = scoped_tickets().where(Pengaduan.id == ticket_id)
    ticket = db.session.execute(statement).unique().scalar_one_or_none()
    if ticket is None:
        abort(404)
    return ticket
