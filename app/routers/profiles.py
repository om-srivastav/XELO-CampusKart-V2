import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func

from ..database import Session, get_db
from ..dependencies import prepare_request, require_login, require_member
from ..models import Product, Review, User
from ..services.security import visible_products
from ..services.storage import get_storage, remove_image, save_image
from ..services.validation import field, integer, phone
from ..web import abort, flash, redirect, render, send_file

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/profile", tags=["profiles"], dependencies=[Depends(prepare_request)])


@router.api_route(
    "/edit",
    methods=["GET"],
    dependencies=[Depends(require_login)],
    response_model=None,
    operation_id="profiles_edit_get",
)
@router.api_route(
    "/edit",
    methods=["POST"],
    dependencies=[Depends(require_login)],
    response_model=None,
    operation_id="profiles_edit_post",
)
def edit(request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        user = request.state.user
        user.display_name = field(request, "display_name", 2, 80)
        for name, size in [("department", 100), ("year", 20), ("city", 100), ("bio", 1000)]:
            setattr(user, name, field(request, name, 0, size))
        user.phone = phone(field(request, "phone", 0, 30))
        user.whatsapp = phone(field(request, "whatsapp", 0, 30))
        for name in ["show_phone", "show_whatsapp", "profile_visible", "contact_visible", "search_history"]:
            setattr(user, name, request.state.form.get(name) == "on")
        if user.show_whatsapp and (not user.whatsapp):
            abort(400, "Add a WhatsApp number before enabling contact.")
        new_keys = []
        old_keys = []
        try:
            for name in ("avatar", "cover"):
                upload = request.state.files.get(name)
                if upload and upload.filename:
                    key = save_image(upload, request.app.state.settings)
                    new_keys.append(key)
                    old_keys.append(getattr(user, name))
                    setattr(user, name, key)
                elif request.state.form.get("remove_" + name) == "on":
                    old_keys.append(getattr(user, name))
                    setattr(user, name, None)
            db.commit()
        except Exception:
            db.rollback()
            for key in new_keys:
                remove_image(key, request.app.state.settings)
            raise
        for key in old_keys:
            remove_image(key, request.app.state.settings)
        flash(request, "Profile updated.", "success")
        return redirect("/profile/edit")
    return render(request, "profiles/edit.html")


@router.api_route("/{uid:int}", methods=["GET"], dependencies=[Depends(require_member)], response_model=None)
def show(request: Request, uid: int, db: Session = Depends(get_db)):
    user = db.get_or_404(User, uid)
    if (
        user.campus_id != request.state.user.campus_id
        or not user.active
        or (not user.profile_visible and user.id != request.state.user.id)
    ):
        abort(404)
    products = (
        visible_products(request, db)
        .filter(Product.seller_id == user.id)
        .order_by(Product.created_at.desc())
        .paginate(per_page=12, error_out=False, page=max(1, integer(request.query_params.get("page"), 1)))
    )
    reviews = (
        db.query(Review)
        .filter_by(seller_id=user.id, hidden=False)
        .order_by(Review.created_at.desc())
        .limit(20)
        .all()
    )
    rating = db.query(func.avg(Review.rating)).filter_by(seller_id=user.id, hidden=False).scalar()
    sold = db.query(Product).filter_by(seller_id=user.id, status="sold").count()
    active = db.query(Product).filter_by(seller_id=user.id, status="available").count()
    return render(
        request,
        "profiles/show.html",
        seller=user,
        products=products,
        reviews=reviews,
        rating=rating,
        sold=sold,
        active=active,
    )


@router.api_route(
    "/{uid:int}/image/{kind}", methods=["GET"], dependencies=[Depends(require_member)], response_model=None
)
def image(request: Request, uid: int, kind: str, db: Session = Depends(get_db)):
    user = db.get_or_404(User, uid)
    if (
        kind not in ("avatar", "cover")
        or user.campus_id != request.state.user.campus_id
        or (not user.active)
        or (not user.profile_visible and user.id != request.state.user.id)
    ):
        abort(404)
    key = getattr(user, kind)
    if not key:
        abort(404)
    path = get_storage(request.app.state.settings).path(key)
    if not path.is_file():
        abort(404)
    response = send_file(path, mimetype="image/webp")
    response.headers["Cache-Control"] = "private, no-store"
    return response
