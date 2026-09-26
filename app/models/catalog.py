from ..extensions import db
from .identity import now


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(300), default="", nullable=False)
    icon = db.Column(db.String(30), default="◇", nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    position = db.Column(db.Integer, default=0, nullable=False)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    campus_id = db.Column(db.Integer, db.ForeignKey("campus.id"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False, index=True)
    title = db.Column(db.String(140), nullable=False)
    slug = db.Column(db.String(180), default="", nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Numeric(12, 2), nullable=False, index=True)
    condition = db.Column(db.String(20), default="good", nullable=False)
    brand = db.Column(db.String(80), default="", nullable=False)
    city = db.Column(db.String(100), default="", nullable=False, index=True)
    negotiable = db.Column(db.Boolean, default=False, nullable=False)
    status = db.Column(db.String(20), default="draft", nullable=False)
    views = db.Column(db.Integer, default=0, nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    sale_confirmed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now, nullable=False)
    seller = db.relationship("User", foreign_keys=[seller_id])
    buyer = db.relationship("User", foreign_keys=[buyer_id])
    campus = db.relationship("Campus")
    category = db.relationship("Category")
    images = db.relationship(
        "ProductImage", cascade="all, delete-orphan", order_by="ProductImage.position", lazy="selectin"
    )
    __table_args__ = (
        db.CheckConstraint("price >= 0 AND price <= 99999999.99", name="valid_price"),
        db.CheckConstraint(
            "status IN ('draft','available','reserved','sold','hidden','removed')", name="valid_status"
        ),
        db.CheckConstraint("condition IN ('new','like_new','good','fair')", name="valid_condition"),
        db.Index("ix_product_discover", "campus_id", "status", "created_at"),
    )


class ProductImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    position = db.Column(db.Integer, nullable=False)
    __table_args__ = (db.UniqueConstraint("product_id", "position"),)


class Wishlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    __table_args__ = (db.UniqueConstraint("user_id", "product_id"),)


class ProductView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    day = db.Column(db.Date, nullable=False)
    __table_args__ = (db.UniqueConstraint("product_id", "user_id", "day"),)


class AnalyticsEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    kind = db.Column(db.String(30), nullable=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False, index=True)
