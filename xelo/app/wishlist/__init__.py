from flask import Blueprint, g, redirect, render_template, request
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Product, Wishlist
from ..services.security import member_required, product_access, safe_next, visible_products

bp = Blueprint("wishlist", __name__, url_prefix="/wishlist")


@bp.get("")
@member_required
def index():
    page = (
        visible_products()
        .join(Wishlist, Wishlist.product_id == Product.id)
        .filter(Wishlist.user_id == g.user.id)
        .order_by(Wishlist.created_at.desc())
        .paginate(per_page=12, error_out=False)
    )
    return render_template("wishlist.html", page=page, saved={p.id for p in page.items})


@bp.post("/<int:pid>")
@member_required
def toggle(pid):
    product_access(pid)
    record = Wishlist.query.filter_by(user_id=g.user.id, product_id=pid).first()
    if record:
        db.session.delete(record)
    else:
        db.session.add(Wishlist(user_id=g.user.id, product_id=pid))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
    return redirect(safe_next(request.form.get("next"), "/wishlist"))
