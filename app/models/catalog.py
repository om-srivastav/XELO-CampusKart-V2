import sqlalchemy as sa
from sqlalchemy.orm import relationship

from ..database import Base
from .identity import now


class Category(Base):
    __tablename__ = "category"
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(80), unique=True, nullable=False)
    slug = sa.Column(sa.String(100), unique=True, nullable=False)
    description = sa.Column(sa.String(300), default="", nullable=False)
    icon = sa.Column(sa.String(30), default="◇", nullable=False)
    active = sa.Column(sa.Boolean, default=True, nullable=False)
    position = sa.Column(sa.Integer, default=0, nullable=False)


class Product(Base):
    __tablename__ = "product"
    id = sa.Column(sa.Integer, primary_key=True)
    seller_id = sa.Column(sa.Integer, sa.ForeignKey("user.id"), nullable=False, index=True)
    campus_id = sa.Column(sa.Integer, sa.ForeignKey("campus.id"), nullable=False, index=True)
    category_id = sa.Column(sa.Integer, sa.ForeignKey("category.id"), nullable=False, index=True)
    title = sa.Column(sa.String(140), nullable=False)
    slug = sa.Column(sa.String(180), default="", nullable=False)
    description = sa.Column(sa.Text, nullable=False)
    price = sa.Column(sa.Numeric(12, 2), nullable=False, index=True)
    condition = sa.Column(sa.String(20), default="good", nullable=False)
    brand = sa.Column(sa.String(80), default="", nullable=False)
    city = sa.Column(sa.String(100), default="", nullable=False, index=True)
    negotiable = sa.Column(sa.Boolean, default=False, nullable=False)
    status = sa.Column(sa.String(20), default="draft", nullable=False)
    views = sa.Column(sa.Integer, default=0, nullable=False)
    buyer_id = sa.Column(sa.Integer, sa.ForeignKey("user.id"))
    sale_confirmed = sa.Column(sa.Boolean, default=False, nullable=False)
    created_at = sa.Column(sa.DateTime, default=now, nullable=False)
    updated_at = sa.Column(sa.DateTime, default=now, onupdate=now, nullable=False)
    seller = relationship("User", foreign_keys=[seller_id])
    buyer = relationship("User", foreign_keys=[buyer_id])
    campus = relationship("Campus")
    category = relationship("Category")
    images = relationship(
        "ProductImage", cascade="all, delete-orphan", order_by="ProductImage.position", lazy="selectin"
    )
    __table_args__ = (
        sa.CheckConstraint("price >= 0 AND price <= 99999999.99", name="valid_price"),
        sa.CheckConstraint(
            "status IN ('draft','available','reserved','sold','hidden','removed')", name="valid_status"
        ),
        sa.CheckConstraint("condition IN ('new','like_new','good','fair')", name="valid_condition"),
        sa.Index("ix_product_discover", "campus_id", "status", "created_at"),
    )


class ProductImage(Base):
    __tablename__ = "product_image"
    id = sa.Column(sa.Integer, primary_key=True)
    product_id = sa.Column(sa.Integer, sa.ForeignKey("product.id"), nullable=False, index=True)
    key = sa.Column(sa.String(64), unique=True, nullable=False)
    position = sa.Column(sa.Integer, nullable=False)
    __table_args__ = (sa.UniqueConstraint("product_id", "position"),)


class Wishlist(Base):
    __tablename__ = "wishlist"
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey("user.id"), nullable=False, index=True)
    product_id = sa.Column(sa.Integer, sa.ForeignKey("product.id"), nullable=False, index=True)
    created_at = sa.Column(sa.DateTime, default=now, nullable=False)
    __table_args__ = (sa.UniqueConstraint("user_id", "product_id"),)


class ProductView(Base):
    __tablename__ = "product_view"
    id = sa.Column(sa.Integer, primary_key=True)
    product_id = sa.Column(sa.Integer, sa.ForeignKey("product.id"), nullable=False, index=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey("user.id"), nullable=False)
    day = sa.Column(sa.Date, nullable=False)
    __table_args__ = (sa.UniqueConstraint("product_id", "user_id", "day"),)


class AnalyticsEvent(Base):
    __tablename__ = "analytics_event"
    id = sa.Column(sa.Integer, primary_key=True)
    product_id = sa.Column(sa.Integer, sa.ForeignKey("product.id"), nullable=False, index=True)
    kind = sa.Column(sa.String(30), nullable=False)
    created_at = sa.Column(sa.DateTime, default=now, nullable=False, index=True)
