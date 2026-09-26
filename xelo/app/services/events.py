from flask import g
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import AnalyticsEvent, Product, ProductView
from ..models.identity import now


def track_view(product):
    if product.seller_id == g.user.id:
        return
    day = now().date()
    if ProductView.query.filter_by(product_id=product.id, user_id=g.user.id, day=day).first():
        return
    try:
        db.session.add(ProductView(product_id=product.id, user_id=g.user.id, day=day))
        db.session.flush()
        Product.query.filter_by(id=product.id).update(
            {"views": Product.views + 1, "updated_at": Product.updated_at}
        )
        db.session.add(AnalyticsEvent(product_id=product.id, kind="view"))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
