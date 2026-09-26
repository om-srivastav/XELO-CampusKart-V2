import hashlib
from datetime import timedelta
from functools import wraps

from flask import abort, current_app, g, redirect, request, session

from ..extensions import db
from ..models import Product, User, UserSession
from ..models.identity import now


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def load_user():
    g.user = None
    g.login_session = None
    raw = session.get("sid")
    if not raw:
        return
    record = UserSession.query.filter_by(token_hash=digest(raw), revoked=False).first()
    if (
        not record
        or record.expires_at <= now()
        or record.last_seen < now() - timedelta(hours=current_app.config["SESSION_IDLE_HOURS"])
        or not record.user.active
    ):
        session.clear()
        return
    g.user, g.login_session = record.user, record
    if record.last_seen < now() - timedelta(minutes=5):
        record.last_seen = now()
        db.session.commit()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.user:
            return redirect("/auth/login?next=" + request.path)
        return fn(*args, **kwargs)

    return wrapper


def member_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if not g.user.campus.active:
            abort(403, "This campus is currently unavailable.")
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if not g.user.is_admin:
            abort(403)
        return fn(*args, **kwargs)

    return wrapper


def product_access(product_id, owner=False):
    p = db.get_or_404(Product, product_id)
    if p.campus_id != g.user.campus_id or not p.seller.active:
        abort(404)
    if owner:
        if p.seller_id != g.user.id:
            abort(403)
        if p.status == "removed":
            abort(403, "A moderator removed this listing.")
    elif p.status not in ("available", "reserved", "sold") and p.seller_id != g.user.id:
        abort(404)
    if p.status == "removed":
        abort(404)
    return p


def visible_products():
    return Product.query.join(User, Product.seller_id == User.id).filter(
        Product.campus_id == g.user.campus_id,
        User.active.is_(True),
        Product.status.in_(["available", "reserved", "sold"]),
    )


def safe_next(value, default="/dashboard"):
    return (
        value
        if value
        and value.startswith("/")
        and not value.startswith("//")
        and "\\" not in value
        and not any(ord(c) < 32 for c in value)
        else default
    )
