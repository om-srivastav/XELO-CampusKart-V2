import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import IntegrityError

from ..database import Session, get_db
from ..dependencies import prepare_request, require_member
from ..models import Notification, Product, Review
from ..services.security import product_access
from ..services.validation import field, integer
from ..web import abort, flash, redirect, render

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reviews", tags=["reviews"], dependencies=[Depends(prepare_request)])


@router.api_route(
    "/{pid:int}/confirm", methods=["POST"], dependencies=[Depends(require_member)], response_model=None
)
def confirm(request: Request, pid: int, db: Session = Depends(get_db)):
    p = product_access(request, db, pid)
    if p.buyer_id != request.state.user.id or p.status != "sold":
        abort(403)
    changed = (
        db.query(Product)
        .filter_by(id=pid, buyer_id=request.state.user.id, status="sold", sale_confirmed=False)
        .update({"sale_confirmed": True})
    )
    if not changed:
        db.rollback()
        abort(409, "The exchange has changed or was already confirmed.")
    db.add(
        Notification(
            user_id=p.seller_id,
            kind="sale",
            title="Exchange confirmed",
            body=p.title,
            link="/market/" + str(pid),
        )
    )
    db.commit()
    return redirect("/reviews/" + str(pid))


@router.api_route(
    "/{pid:int}",
    methods=["GET"],
    dependencies=[Depends(require_member)],
    response_model=None,
    operation_id="reviews_review_get",
)
@router.api_route(
    "/{pid:int}",
    methods=["POST"],
    dependencies=[Depends(require_member)],
    response_model=None,
    operation_id="reviews_review_post",
)
def review(request: Request, pid: int, db: Session = Depends(get_db)):
    p = product_access(request, db, pid)
    if (
        p.buyer_id != request.state.user.id
        or not p.sale_confirmed
        or p.status != "sold"
        or (p.seller_id == request.state.user.id)
    ):
        abort(403)
    existing = db.query(Review).filter_by(product_id=pid).first()
    if request.method == "POST":
        if existing:
            abort(409, "You already reviewed this exchange.")
        rating = integer(request.state.form.get("rating"))
        if rating not in range(1, 6):
            abort(400, "Choose a rating from 1 to 5.")
        db.add(
            Review(
                product_id=pid,
                reviewer_id=request.state.user.id,
                seller_id=p.seller_id,
                rating=rating,
                body=field(request, "body", 3, 1500),
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            abort(409, "This exchange already has a review.")
        flash(request, "Your review is published.", "success")
        return redirect("/profile/" + str(p.seller_id))
    return render(request, "review.html", product=p, existing=existing)
