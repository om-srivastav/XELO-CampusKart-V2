import sqlalchemy as sa
from sqlalchemy.orm import relationship

from ..database import Base
from .identity import now


class Conversation(Base):
    __tablename__ = "conversation"
    id = sa.Column(sa.Integer, primary_key=True)
    product_id = sa.Column(sa.Integer, sa.ForeignKey("product.id"), nullable=False)
    buyer_id = sa.Column(sa.Integer, sa.ForeignKey("user.id"), nullable=False, index=True)
    seller_id = sa.Column(sa.Integer, sa.ForeignKey("user.id"), nullable=False, index=True)
    created_at = sa.Column(sa.DateTime, default=now, nullable=False)
    updated_at = sa.Column(sa.DateTime, default=now, nullable=False)
    product = relationship("Product")
    buyer = relationship("User", foreign_keys=[buyer_id])
    seller = relationship("User", foreign_keys=[seller_id])
    __table_args__ = (
        sa.UniqueConstraint("product_id", "buyer_id", "seller_id"),
        sa.CheckConstraint("buyer_id != seller_id", name="not_self"),
    )


class Message(Base):
    __tablename__ = "message"
    id = sa.Column(sa.Integer, primary_key=True)
    conversation_id = sa.Column(sa.Integer, sa.ForeignKey("conversation.id"), nullable=False, index=True)
    sender_id = sa.Column(sa.Integer, sa.ForeignKey("user.id"), nullable=False)
    body = sa.Column(sa.String(3000), nullable=False)
    created_at = sa.Column(sa.DateTime, default=now, nullable=False)
    read_at = sa.Column(sa.DateTime)
    sender = relationship("User")
    conversation = relationship("Conversation")


class Notification(Base):
    __tablename__ = "notification"
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey("user.id"), nullable=False, index=True)
    kind = sa.Column(sa.String(30), nullable=False)
    title = sa.Column(sa.String(180), nullable=False)
    body = sa.Column(sa.String(500), default="", nullable=False)
    link = sa.Column(sa.String(200), default="/dashboard", nullable=False)
    read_at = sa.Column(sa.DateTime)
    created_at = sa.Column(sa.DateTime, default=now, nullable=False)
    __table_args__ = (sa.Index("ix_notification_unread", "user_id", "read_at"),)


class Review(Base):
    __tablename__ = "review"
    id = sa.Column(sa.Integer, primary_key=True)
    product_id = sa.Column(sa.Integer, sa.ForeignKey("product.id"), unique=True, nullable=False)
    reviewer_id = sa.Column(sa.Integer, sa.ForeignKey("user.id"), nullable=False)
    seller_id = sa.Column(sa.Integer, sa.ForeignKey("user.id"), nullable=False, index=True)
    rating = sa.Column(sa.Integer, nullable=False)
    body = sa.Column(sa.String(1500), nullable=False)
    hidden = sa.Column(sa.Boolean, default=False, nullable=False)
    created_at = sa.Column(sa.DateTime, default=now, nullable=False)
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    __table_args__ = (
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="rating_range"),
        sa.CheckConstraint("reviewer_id != seller_id", name="not_self"),
    )


class Report(Base):
    __tablename__ = "report"
    id = sa.Column(sa.Integer, primary_key=True)
    reporter_id = sa.Column(sa.Integer, sa.ForeignKey("user.id"), nullable=False, index=True)
    kind = sa.Column(sa.String(20), nullable=False)
    target_id = sa.Column(sa.Integer, nullable=False)
    reason = sa.Column(sa.String(40), nullable=False)
    description = sa.Column(sa.String(2000), default="", nullable=False)
    status = sa.Column(sa.String(20), default="open", nullable=False, index=True)
    created_at = sa.Column(sa.DateTime, default=now, nullable=False)


class AdminAction(Base):
    __tablename__ = "admin_action"
    id = sa.Column(sa.Integer, primary_key=True)
    admin_id = sa.Column(sa.Integer, sa.ForeignKey("user.id"), nullable=False)
    action = sa.Column(sa.String(80), nullable=False)
    target = sa.Column(sa.String(80), nullable=False)
    reason = sa.Column(sa.String(500), nullable=False)
    created_at = sa.Column(sa.DateTime, default=now, nullable=False)


class SearchHistory(Base):
    __tablename__ = "search_history"
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey("user.id"), nullable=False, index=True)
    term = sa.Column("query", sa.String(140), nullable=False)
    created_at = sa.Column(sa.DateTime, default=now, nullable=False)
