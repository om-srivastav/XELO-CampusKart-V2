from datetime import timedelta

from flask import Blueprint, g, redirect, render_template
from sqlalchemy import func

from ..extensions import db
from ..models import AnalyticsEvent, Conversation, Notification, Product, SearchHistory, Wishlist
from ..models.identity import now
from ..services.security import login_required

bp = Blueprint("dashboard", __name__)


@bp.get("/dashboard")
@login_required
def index():
    owned = Product.query.filter_by(seller_id=g.user.id)
    page = owned.order_by(Product.created_at.desc()).paginate(per_page=10, error_out=False)
    counts = dict(
        db.session.query(Product.status, func.count(Product.id))
        .filter_by(seller_id=g.user.id)
        .group_by(Product.status)
        .all()
    )
    views = (
        db.session.query(func.coalesce(func.sum(Product.views), 0)).filter_by(seller_id=g.user.id).scalar()
    )
    wish = (
        db.session.query(func.count(Wishlist.id))
        .join(Product, Wishlist.product_id == Product.id)
        .filter(Product.seller_id == g.user.id)
        .scalar()
    )
    clicks = (
        db.session.query(func.count(AnalyticsEvent.id))
        .join(Product)
        .filter(Product.seller_id == g.user.id, AnalyticsEvent.kind == "whatsapp")
        .scalar()
    )
    conversations = Conversation.query.filter_by(seller_id=g.user.id).count()
    start = now().date() - timedelta(days=13)
    rows = (
        db.session.query(
            func.date(AnalyticsEvent.created_at), AnalyticsEvent.kind, func.count(AnalyticsEvent.id)
        )
        .join(Product)
        .filter(Product.seller_id == g.user.id, AnalyticsEvent.created_at >= start)
        .group_by(func.date(AnalyticsEvent.created_at), AnalyticsEvent.kind)
        .all()
    )
    series = {(str(day), kind): n for day, kind, n in rows}
    trend = [
        {
            "day": str(start + timedelta(days=i)),
            "views": series.get((str(start + timedelta(days=i)), "view"), 0),
            "clicks": series.get((str(start + timedelta(days=i)), "whatsapp"), 0),
        }
        for i in range(14)
    ]
    ids = [p.id for p in page.items]
    saves = dict(
        db.session.query(Wishlist.product_id, func.count(Wishlist.id))
        .filter(Wishlist.product_id.in_(ids))
        .group_by(Wishlist.product_id)
        .all()
    )
    contacts = dict(
        db.session.query(AnalyticsEvent.product_id, func.count(AnalyticsEvent.id))
        .filter(AnalyticsEvent.product_id.in_(ids), AnalyticsEvent.kind == "whatsapp")
        .group_by(AnalyticsEvent.product_id)
        .all()
    )
    completion = round(
        sum(
            bool(getattr(g.user, f))
            for f in ["display_name", "department", "year", "city", "bio", "avatar"]
        )
        / 6
        * 100
    )
    recent = (
        Notification.query.filter_by(user_id=g.user.id)
        .order_by(Notification.created_at.desc())
        .limit(5)
        .all()
    )
    return render_template(
        "dashboard.html",
        page=page,
        counts=counts,
        views=views,
        wish=wish,
        clicks=clicks,
        conversations=conversations,
        trend=trend,
        saves=saves,
        contacts=contacts,
        completion=completion,
        recent=recent,
    )


@bp.route("/history")
@login_required
def history():
    page = (
        SearchHistory.query.filter_by(user_id=g.user.id)
        .order_by(SearchHistory.created_at.desc())
        .paginate(per_page=30, error_out=False)
    )
    return render_template("history.html", page=page)


@bp.post("/history/clear")
@login_required
def clear_history():
    SearchHistory.query.filter_by(user_id=g.user.id).delete()
    db.session.commit()
    return redirect("/history")
