from fastapi import Request
from sqlalchemy.exc import IntegrityError

from ..database import Session
from ..models import AnalyticsEvent, Product, ProductView
from ..models.identity import now


def track_view(request: Request, db: Session, product):
    if product.seller_id == request.state.user.id:
        return
    day = now().date()
    if db.query(ProductView).filter_by(product_id=product.id, user_id=request.state.user.id, day=day).first():
        return
    try:
        db.add(ProductView(product_id=product.id, user_id=request.state.user.id, day=day))
        db.flush()
        db.query(Product).filter_by(id=product.id).update(
            {"views": Product.views + 1, "updated_at": Product.updated_at}
        )
        db.add(AnalyticsEvent(product_id=product.id, kind="view"))
        db.commit()
    except IntegrityError:
        db.rollback()
