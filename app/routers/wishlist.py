import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import IntegrityError

from ..database import Session, get_db
from ..dependencies import prepare_request, require_member
from ..models import Product, Wishlist
from ..services.security import product_access, safe_next, visible_products
from ..services.validation import integer
from ..web import redirect, render

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/wishlist", tags=["wishlist"], dependencies=[Depends(prepare_request)])


@router.api_route("", methods=["GET"], dependencies=[Depends(require_member)], response_model=None)
def index(request: Request, db: Session = Depends(get_db)):
    page = (
        visible_products(request, db)
        .join(Wishlist, Wishlist.product_id == Product.id)
        .filter(Wishlist.user_id == request.state.user.id)
        .order_by(Wishlist.created_at.desc())
        .paginate(per_page=12, error_out=False, page=max(1, integer(request.query_params.get("page"), 1)))
    )
    return render(request, "wishlist.html", page=page, saved={p.id for p in page.items})


@router.api_route("/{pid:int}", methods=["POST"], dependencies=[Depends(require_member)], response_model=None)
def toggle(request: Request, pid: int, db: Session = Depends(get_db)):
    product_access(request, db, pid)
    record = db.query(Wishlist).filter_by(user_id=request.state.user.id, product_id=pid).first()
    if record:
        db.delete(record)
    else:
        db.add(Wishlist(user_id=request.state.user.id, product_id=pid))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return redirect(safe_next(request.state.form.get("next"), "/wishlist"))
