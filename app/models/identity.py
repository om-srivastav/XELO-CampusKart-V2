from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import relationship

from ..database import Base


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Campus(Base):
    __tablename__ = "campus"
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(120), unique=True, nullable=False)
    city = sa.Column(sa.String(100), nullable=False)
    domains = sa.Column(sa.String(500), default="", nullable=False)
    active = sa.Column(sa.Boolean, default=True, nullable=False)


class User(Base):
    __tablename__ = "user"
    id = sa.Column(sa.Integer, primary_key=True)
    username = sa.Column(sa.String(40), unique=True, nullable=False)
    email = sa.Column(sa.String(254), unique=True, nullable=False)
    password_hash = sa.Column(sa.String(255), nullable=False)
    display_name = sa.Column(sa.String(80), nullable=False)
    campus_id = sa.Column(sa.Integer, sa.ForeignKey("campus.id"), nullable=False, index=True)
    campus = relationship("Campus")
    # Legacy database field; no longer used for access or displayed as a trust claim.
    verified = sa.Column(sa.Boolean, default=False, nullable=False)
    active = sa.Column(sa.Boolean, default=True, nullable=False)
    is_admin = sa.Column(sa.Boolean, default=False, nullable=False)
    department = sa.Column(sa.String(100), default="", nullable=False)
    year = sa.Column(sa.String(20), default="", nullable=False)
    city = sa.Column(sa.String(100), default="", nullable=False)
    bio = sa.Column(sa.String(1000), default="", nullable=False)
    phone = sa.Column(sa.String(16), default="", nullable=False)
    whatsapp = sa.Column(sa.String(16), default="", nullable=False)
    show_phone = sa.Column(sa.Boolean, default=False, nullable=False)
    show_whatsapp = sa.Column(sa.Boolean, default=False, nullable=False)
    profile_visible = sa.Column(sa.Boolean, default=True, nullable=False)
    contact_visible = sa.Column(sa.Boolean, default=True, nullable=False)
    search_history = sa.Column(sa.Boolean, default=False, nullable=False)
    avatar = sa.Column(sa.String(64))
    cover = sa.Column(sa.String(64))
    created_at = sa.Column(sa.DateTime, default=now, nullable=False)


class UserSession(Base):
    __tablename__ = "user_session"
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey("user.id"), nullable=False, index=True)
    token_hash = sa.Column(sa.String(64), unique=True, nullable=False)
    created_at = sa.Column(sa.DateTime, default=now, nullable=False)
    last_seen = sa.Column(sa.DateTime, default=now, nullable=False)
    expires_at = sa.Column(sa.DateTime, nullable=False)
    revoked = sa.Column(sa.Boolean, default=False, nullable=False)
    user = relationship("User")


class AccountToken(Base):
    __tablename__ = "account_token"
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey("user.id"), nullable=False)
    token_hash = sa.Column(sa.String(64), unique=True, nullable=False)
    purpose = sa.Column(sa.String(20), nullable=False)
    expires_at = sa.Column(sa.DateTime, nullable=False)
    used = sa.Column(sa.Boolean, default=False, nullable=False)


class LoginHistory(Base):
    __tablename__ = "login_history"
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey("user.id"), index=True)
    success = sa.Column(sa.Boolean, nullable=False)
    created_at = sa.Column(sa.DateTime, default=now, nullable=False)
