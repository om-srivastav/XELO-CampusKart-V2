from flask import Blueprint, abort, flash, g, redirect, render_template, request, send_file
from sqlalchemy import func

from ..extensions import db
from ..models import Product, Review, User
from ..services.security import login_required, member_required, visible_products
from ..services.storage import LocalImageStorage, remove_image, save_image
from ..services.validation import field, phone

bp = Blueprint("profiles", __name__, url_prefix="/profile")


@bp.route("/edit", methods=["GET", "POST"])
@login_required
def edit():
    if request.method == "POST":
        user = g.user
        user.display_name = field("display_name", 2, 80)
        for name, size in [("department", 100), ("year", 20), ("city", 100), ("bio", 1000)]:
            setattr(user, name, field(name, 0, size))
        user.phone = phone(field("phone", 0, 30))
        user.whatsapp = phone(field("whatsapp", 0, 30))
        for name in ["show_phone", "show_whatsapp", "profile_visible", "contact_visible", "search_history"]:
            setattr(user, name, request.form.get(name) == "on")
        if user.show_whatsapp and not user.whatsapp:
            abort(400, "Add a WhatsApp number before enabling contact.")
        new_keys = []
        old_keys = []
        try:
            for name in ("avatar", "cover"):
                upload = request.files.get(name)
                if upload and upload.filename:
                    key = save_image(upload)
                    new_keys.append(key)
                    old_keys.append(getattr(user, name))
                    setattr(user, name, key)
                elif request.form.get("remove_" + name) == "on":
                    old_keys.append(getattr(user, name))
                    setattr(user, name, None)
            db.session.commit()
        except Exception:
            db.session.rollback()
            for key in new_keys:
                remove_image(key)
            raise
        for key in old_keys:
            remove_image(key)
        flash("Profile updated.", "success")
        return redirect("/profile/edit")
    return render_template("profiles/edit.html")


@bp.get("/<int:uid>")
@member_required
def show(uid):
    user = db.get_or_404(User, uid)
    if (
        user.campus_id != g.user.campus_id
        or not user.active
        or (not user.profile_visible and user.id != g.user.id)
    ):
        abort(404)
    products = (
        visible_products()
        .filter(Product.seller_id == user.id)
        .order_by(Product.created_at.desc())
        .paginate(per_page=12, error_out=False)
    )
    reviews = (
        Review.query.filter_by(seller_id=user.id, hidden=False)
        .order_by(Review.created_at.desc())
        .limit(20)
        .all()
    )
    rating = db.session.query(func.avg(Review.rating)).filter_by(seller_id=user.id, hidden=False).scalar()
    sold = Product.query.filter_by(seller_id=user.id, status="sold").count()
    active = Product.query.filter_by(seller_id=user.id, status="available").count()
    return render_template(
        "profiles/show.html",
        seller=user,
        products=products,
        reviews=reviews,
        rating=rating,
        sold=sold,
        active=active,
    )


@bp.get("/<int:uid>/image/<kind>")
@member_required
def image(uid, kind):
    user = db.get_or_404(User, uid)
    if (
        kind not in ("avatar", "cover")
        or user.campus_id != g.user.campus_id
        or not user.active
        or (not user.profile_visible and user.id != g.user.id)
    ):
        abort(404)
    key = getattr(user, kind)
    if not key:
        abort(404)
    path = LocalImageStorage().path(key)
    if not path.is_file():
        abort(404)
    response = send_file(path, mimetype="image/webp")
    response.headers["Cache-Control"] = "private, no-store"
    return response
