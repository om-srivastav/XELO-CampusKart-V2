from datetime import datetime, timezone

from ..extensions import db


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Campus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    city = db.Column(db.String(100), nullable=False)
    domains = db.Column(db.String(500), default="", nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), unique=True, nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(80), nullable=False)
    campus_id = db.Column(db.Integer, db.ForeignKey("campus.id"), nullable=False, index=True)
    campus = db.relationship("Campus")
    # Legacy database field; no longer used for access or displayed as a trust claim.
    verified = db.Column(db.Boolean, default=False, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    department = db.Column(db.String(100), default="", nullable=False)
    year = db.Column(db.String(20), default="", nullable=False)
    city = db.Column(db.String(100), default="", nullable=False)
    bio = db.Column(db.String(1000), default="", nullable=False)
    phone = db.Column(db.String(16), default="", nullable=False)
    whatsapp = db.Column(db.String(16), default="", nullable=False)
    show_phone = db.Column(db.Boolean, default=False, nullable=False)
    show_whatsapp = db.Column(db.Boolean, default=False, nullable=False)
    profile_visible = db.Column(db.Boolean, default=True, nullable=False)
    contact_visible = db.Column(db.Boolean, default=True, nullable=False)
    search_history = db.Column(db.Boolean, default=False, nullable=False)
    avatar = db.Column(db.String(64))
    cover = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=now, nullable=False)


class UserSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    last_seen = db.Column(db.DateTime, default=now, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked = db.Column(db.Boolean, default=False, nullable=False)
    user = db.relationship("User")


class AccountToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    purpose = db.Column(db.String(20), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)


class LoginHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    success = db.Column(db.Boolean, nullable=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
