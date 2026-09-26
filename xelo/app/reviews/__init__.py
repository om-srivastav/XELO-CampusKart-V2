from flask import Blueprint, abort, flash, g, redirect, render_template, request
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Notification, Product, Review
from ..services.security import member_required, product_access
from ..services.validation import field, integer

bp = Blueprint("reviews", __name__, url_prefix="/reviews")


@bp.post("/<int:pid>/confirm")
@member_required
def confirm(pid):
    p = product_access(pid)
    if p.buyer_id != g.user.id or p.status != "sold":
        abort(403)
    changed = Product.query.filter_by(id=pid, buyer_id=g.user.id, status="sold", sale_confirmed=False).update(
        {"sale_confirmed": True}
    )
    if not changed:
        db.session.rollback()
        abort(409, "The exchange has changed or was already confirmed.")
    db.session.add(
        Notification(
            user_id=p.seller_id,
            kind="sale",
            title="Exchange confirmed",
            body=p.title,
            link="/market/" + str(pid),
        )
    )
    db.session.commit()
    return redirect("/reviews/" + str(pid))


@bp.route("/<int:pid>", methods=["GET", "POST"])
@member_required
def review(pid):
    p = product_access(pid)
    if p.buyer_id != g.user.id or not p.sale_confirmed or p.status != "sold" or p.seller_id == g.user.id:
        abort(403)
    existing = Review.query.filter_by(product_id=pid).first()
    if request.method == "POST":
        if existing:
            abort(409, "You already reviewed this exchange.")
        rating = integer(request.form.get("rating"))
        if rating not in range(1, 6):
            abort(400, "Choose a rating from 1 to 5.")
        db.session.add(
            Review(
                product_id=pid,
                reviewer_id=g.user.id,
                seller_id=p.seller_id,
                rating=rating,
                body=field("body", 3, 1500),
            )
        )
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            abort(409, "This exchange already has a review.")
        flash("Your review is published.", "success")
        return redirect("/profile/" + str(p.seller_id))
    return render_template("review.html", product=p, existing=existing)
