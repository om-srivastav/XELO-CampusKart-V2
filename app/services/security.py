from ..models import Product, User
from ..web import abort


def product_access(request, db, product_id, owner=False):
    p = db.get_or_404(Product, product_id)
    user = request.state.user
    if p.campus_id != user.campus_id or not p.seller.active:
        abort(404)
    if owner:
        if p.seller_id != user.id:
            abort(403)
        if p.status == "removed":
            abort(403, "A moderator removed this listing.")
    elif p.status not in ("available", "reserved", "sold") and p.seller_id != user.id:
        abort(404)
    if p.status == "removed":
        abort(404)
    return p


def visible_products(request, db):
    return (
        db.query(Product)
        .join(User, Product.seller_id == User.id)
        .filter(
            Product.campus_id == request.state.user.campus_id,
            User.active.is_(True),
            Product.status.in_(["available", "reserved", "sold"]),
        )
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
