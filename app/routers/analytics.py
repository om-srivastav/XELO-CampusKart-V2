import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func

from ..database import Session, get_db
from ..dependencies import prepare_request, require_login
from ..models import AnalyticsEvent, Conversation, Notification, Product, SearchHistory, Wishlist
from ..models.identity import now
from ..services.validation import integer
from ..web import redirect, render

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["analytics"], dependencies=[Depends(prepare_request)])


@router.api_route("/dashboard", methods=["GET"], dependencies=[Depends(require_login)], response_model=None)
def index(request: Request, db: Session = Depends(get_db)):
    owned = db.query(Product).filter_by(seller_id=request.state.user.id)
    page = owned.order_by(Product.created_at.desc()).paginate(
        per_page=10, error_out=False, page=max(1, integer(request.query_params.get("page"), 1))
    )
    counts = dict(
        db.query(Product.status, func.count(Product.id))
        .filter_by(seller_id=request.state.user.id)
        .group_by(Product.status)
        .all()
    )
    views = (
        db.query(func.coalesce(func.sum(Product.views), 0))
        .filter_by(seller_id=request.state.user.id)
        .scalar()
    )
    wish = (
        db.query(func.count(Wishlist.id))
        .join(Product, Wishlist.product_id == Product.id)
        .filter(Product.seller_id == request.state.user.id)
        .scalar()
    )
    clicks = (
        db.query(func.count(AnalyticsEvent.id))
        .join(Product)
        .filter(Product.seller_id == request.state.user.id, AnalyticsEvent.kind == "whatsapp")
        .scalar()
    )
    conversations = db.query(Conversation).filter_by(seller_id=request.state.user.id).count()
    start = now().date() - timedelta(days=13)
    rows = (
        db.query(func.date(AnalyticsEvent.created_at), AnalyticsEvent.kind, func.count(AnalyticsEvent.id))
        .join(Product)
        .filter(Product.seller_id == request.state.user.id, AnalyticsEvent.created_at >= start)
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
        db.query(Wishlist.product_id, func.count(Wishlist.id))
        .filter(Wishlist.product_id.in_(ids))
        .group_by(Wishlist.product_id)
        .all()
    )
    contacts = dict(
        db.query(AnalyticsEvent.product_id, func.count(AnalyticsEvent.id))
        .filter(AnalyticsEvent.product_id.in_(ids), AnalyticsEvent.kind == "whatsapp")
        .group_by(AnalyticsEvent.product_id)
        .all()
    )
    completion = round(
        sum(
            (
                bool(getattr(request.state.user, f))
                for f in ["display_name", "department", "year", "city", "bio", "avatar"]
            )
        )
        / 6
        * 100
    )
    recent = (
        db.query(Notification)
        .filter_by(user_id=request.state.user.id)
        .order_by(Notification.created_at.desc())
        .limit(5)
        .all()
    )
    return render(
        request,
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


@router.api_route("/history", methods=["GET"], dependencies=[Depends(require_login)], response_model=None)
def history(request: Request, db: Session = Depends(get_db)):
    page = (
        db.query(SearchHistory)
        .filter_by(user_id=request.state.user.id)
        .order_by(SearchHistory.created_at.desc())
        .paginate(per_page=30, error_out=False, page=max(1, integer(request.query_params.get("page"), 1)))
    )
    return render(request, "history.html", page=page)


@router.api_route(
    "/history/clear", methods=["POST"], dependencies=[Depends(require_login)], response_model=None
)
def clear_history(request: Request, db: Session = Depends(get_db)):
    db.query(SearchHistory).filter_by(user_id=request.state.user.id).delete()
    db.commit()
    return redirect("/history")
