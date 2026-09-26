import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy import case, func, or_
from sqlalchemy.orm import joinedload

from ..database import Session, get_db
from ..dependencies import prepare_request, require_member
from ..middleware.rate_limit import limit
from ..models import (
    Campus,
    Category,
    Conversation,
    Notification,
    Product,
    ProductImage,
    SearchHistory,
    User,
    Wishlist,
)
from ..schemas.responses import Suggestion
from ..services.security import product_access, visible_products
from ..services.storage import get_storage, remove_image, save_image
from ..services.validation import field, integer, money, phone, slug
from ..web import abort, flash, redirect, render, send_file

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market", tags=["marketplace"], dependencies=[Depends(prepare_request)])
CONDITIONS = ["new", "like_new", "good", "fair"]


def filtered_query(request: Request, db: Session):
    query = (
        visible_products(request, db)
        .join(Category)
        .join(Campus, Product.campus_id == Campus.id)
        .options(joinedload(Product.seller), joinedload(Product.category), joinedload(Product.campus))
    )
    q = request.query_params.get("q", "").strip()[:140]
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        term = "%" + escaped + "%"
        query = query.filter(
            or_(
                *[
                    column.ilike(term, escape="\\")
                    for column in [
                        Product.title,
                        Product.description,
                        Product.brand,
                        Product.city,
                        Category.name,
                        Campus.name,
                    ]
                ]
            )
        )
    for key, column in [
        ("college", Product.campus_id),
        ("category", Product.category_id),
        ("condition", Product.condition),
        ("city", Product.city),
        ("brand", Product.brand),
    ]:
        value = request.query_params.get(key)
        if value:
            query = query.filter(
                column == (integer(value) if key in ("category", "college") else value[:100])
            )
    for key, column in [("min_price", Product.price.__ge__), ("max_price", Product.price.__le__)]:
        if request.query_params.get(key):
            query = query.filter(column(money(request.query_params[key])))
    if request.query_params.get("negotiable") == "on":
        query = query.filter(Product.negotiable.is_(True))
    status = request.query_params.get("status", "available")
    if status in ("available", "reserved", "sold"):
        query = query.filter(Product.status == status)
    elif status != "all":
        abort(400, "Invalid listing status.")
    sort = request.query_params.get("sort", "newest")
    orders = {
        "newest": Product.created_at.desc(),
        "oldest": Product.created_at.asc(),
        "price_low": Product.price.asc(),
        "price_high": Product.price.desc(),
        "views": Product.views.desc(),
        "relevant": case(
            (Product.title.ilike("%" + q.replace("%", "\\%").replace("_", "\\_") + "%", escape="\\"), 0),
            else_=1,
        ),
    }
    return (query.order_by(orders.get(sort, orders["newest"]), Product.id.desc()), q)


@router.api_route("", methods=["GET"], dependencies=[Depends(require_member)], response_model=None)
def browse(request: Request, db: Session = Depends(get_db)):
    query, q = filtered_query(request, db)
    page = query.paginate(
        page=max(1, integer(request.query_params.get("page"), 1)), per_page=12, error_out=False
    )
    if q and request.state.user.search_history:
        db.add(SearchHistory(user_id=request.state.user.id, term=q))
        db.commit()
    saved = {
        r[0]
        for r in db.query(Wishlist.product_id)
        .filter(
            Wishlist.user_id == request.state.user.id, Wishlist.product_id.in_([p.id for p in page.items])
        )
        .all()
    }
    counts = dict(
        db.query(Product.category_id, func.count(Product.id))
        .select_from(Product)
        .join(Product.seller)
        .filter(
            Product.campus_id == request.state.user.campus_id,
            Product.status == "available",
            User.active.is_(True),
        )
        .group_by(Product.category_id)
        .all()
    )
    return render(
        request,
        "marketplace/browse.html",
        page=page,
        categories=db.query(Category).filter_by(active=True).order_by(Category.position).all(),
        saved=saved,
        counts=counts,
        conditions=CONDITIONS,
        q=q,
    )


@router.api_route(
    "/suggest",
    methods=["GET"],
    dependencies=[Depends(require_member), Depends(limit("60 per minute"))],
    response_model=list[Suggestion],
)
def suggest(request: Request, db: Session = Depends(get_db)):
    query, q = filtered_query(request, db)
    if len(q) < 2:
        return []
    return [{"title": p.title, "url": "/market/" + str(p.id)} for p in query.limit(6)]


def assign_fields(request: Request, db: Session, p):
    p.title = field(request, "title", 3, 140)
    p.slug = slug(p.title)
    p.description = field(request, "description", 15, 5000)
    category = db.get(Category, integer(request.state.form.get("category_id")))
    if not category or not category.active:
        abort(400, "Select an active category.")
    p.category_id = category.id
    p.price = money(request.state.form.get("price"))
    p.condition = field(request, "condition", 1, 20)
    if p.condition not in CONDITIONS:
        abort(400, "Invalid condition.")
    p.brand = field(request, "brand", 0, 80)
    p.city = field(request, "city", 1, 100)
    p.negotiable = request.state.form.get("negotiable") == "on"
    if "whatsapp" in request.state.form:
        request.state.user.whatsapp = phone(field(request, "whatsapp", 1, 30))
        request.state.user.show_whatsapp = request.state.form.get("whatsapp_contact") == "on"
        if request.state.user.show_whatsapp:
            request.state.user.contact_visible = True
            request.state.user.profile_visible = True


def append_images(request: Request, db: Session, p):
    files = [f for f in request.state.files.getlist("images") if f.filename]
    if len(files) + len(p.images) > 6:
        abort(400, "Use up to six images.")
    keys = []
    try:
        for f in files:
            keys.append(save_image(f, request.app.state.settings))
        for key in keys:
            p.images.append(ProductImage(key=key, position=len(p.images)))
        if not p.images:
            abort(400, "Add at least one product image.")
        db.add(p)
        db.commit()
    except Exception:
        db.rollback()
        for key in keys:
            remove_image(key, request.app.state.settings)
        raise


@router.api_route(
    "/new",
    methods=["GET"],
    dependencies=[Depends(require_member), Depends(limit("20 per hour", methods=["POST"]))],
    response_model=None,
    operation_id="marketplace_create_get",
)
@router.api_route(
    "/new",
    methods=["POST"],
    dependencies=[Depends(require_member), Depends(limit("20 per hour", methods=["POST"]))],
    response_model=None,
    operation_id="marketplace_create_post",
)
def create(request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        p = Product(
            seller_id=request.state.user.id, campus_id=request.state.user.campus_id, status="available"
        )
        assign_fields(request, db, p)
        if request.state.form.get("status") == "draft":
            p.status = "draft"
        append_images(request, db, p)
        flash(
            request, "Listing saved." if p.status == "draft" else "Your listing is live on campus.", "success"
        )
        return redirect("/market/" + str(p.id))
    return render(
        request,
        "marketplace/form.html",
        product=None,
        categories=db.query(Category).filter_by(active=True).order_by(Category.position).all(),
        conditions=CONDITIONS,
    )


@router.api_route(
    "/{pid:int}/edit",
    methods=["GET"],
    dependencies=[Depends(require_member)],
    response_model=None,
    operation_id="marketplace_edit_get",
)
@router.api_route(
    "/{pid:int}/edit",
    methods=["POST"],
    dependencies=[Depends(require_member)],
    response_model=None,
    operation_id="marketplace_edit_post",
)
def edit(request: Request, pid: int, db: Session = Depends(get_db)):
    p = product_access(request, db, pid, owner=True)
    if request.method == "POST":
        assign_fields(request, db, p)
        append_images(request, db, p)
        flash(request, "Listing updated.", "success")
        return redirect("/market/" + str(p.id))
    return render(
        request,
        "marketplace/form.html",
        product=p,
        categories=db.query(Category).filter_by(active=True).order_by(Category.position).all(),
        conditions=CONDITIONS,
    )


@router.api_route(
    "/{pid:int}/images", methods=["POST"], dependencies=[Depends(require_member)], response_model=None
)
def images(request: Request, pid: int, db: Session = Depends(get_db)):
    p = product_access(request, db, pid, owner=True)
    ids = [integer(s, -1) for s in field(request, "order", 1, 200).split(",")]
    originals = {i.id: i for i in p.images}
    if not ids or len(ids) != len(set(ids)) or (not set(ids) <= set(originals)):
        abort(400, "Invalid image order.")
    removed = []
    for i in p.images:
        i.position = -i.id
        if i.id not in ids:
            removed.append(i.key)
            db.delete(i)
    db.flush()
    for position, i in enumerate(ids):
        originals[i].position = position
    db.commit()
    for key in removed:
        remove_image(key, request.app.state.settings)
    return redirect("/market/" + str(pid) + "/edit")


@router.api_route(
    "/{pid:int}/status", methods=["POST"], dependencies=[Depends(require_member)], response_model=None
)
def status(request: Request, pid: int, db: Session = Depends(get_db)):
    p = product_access(request, db, pid, owner=True)
    value = field(request, "status", 1, 20)
    if value not in ("available", "reserved", "sold", "hidden"):
        abort(400, "Invalid status.")
    if p.sale_confirmed:
        abort(400, "Confirmed sales cannot be reopened.")
    buyer = integer(request.state.form.get("buyer_id"))
    if value == "sold" and buyer:
        c = (
            db.query(Conversation)
            .filter_by(product_id=p.id, buyer_id=buyer, seller_id=request.state.user.id)
            .first()
        )
        if not c:
            abort(400, "Choose a buyer who contacted you about this listing.")
        selected_buyer = buyer
        db.add(
            Notification(
                user_id=buyer,
                kind="sale",
                title="Confirm your exchange",
                body=p.title,
                link="/market/" + str(p.id),
            )
        )
    else:
        selected_buyer = p.buyer_id if value == "sold" else None
    changed = (
        db.query(Product)
        .filter_by(id=pid, sale_confirmed=False)
        .update({"status": value, "buyer_id": selected_buyer})
    )
    if not changed:
        db.rollback()
        abort(409, "This sale has already been confirmed.")
    for (uid,) in db.query(Wishlist.user_id).filter_by(product_id=pid).limit(1000):
        db.add(
            Notification(
                user_id=uid,
                kind="listing",
                title="A saved listing changed status",
                body=p.title + " is " + value,
                link="/market/" + str(pid),
            )
        )
    db.commit()
    return redirect("/market/" + str(pid))


@router.api_route(
    "/{pid:int}/delete", methods=["POST"], dependencies=[Depends(require_member)], response_model=None
)
def delete(request: Request, pid: int, db: Session = Depends(get_db)):
    p = product_access(request, db, pid, owner=True)
    p.status = "removed"
    db.commit()
    return redirect("/dashboard")


@router.api_route("/{pid:int}", methods=["GET"], dependencies=[Depends(require_member)], response_model=None)
def detail(request: Request, pid: int, db: Session = Depends(get_db)):
    p = product_access(request, db, pid)
    from ..services.events import track_view

    track_view(request, db, p)
    saved = db.query(Wishlist).filter_by(user_id=request.state.user.id, product_id=p.id).first() is not None
    related = (
        visible_products(request, db)
        .filter(Product.category_id == p.category_id, Product.id != p.id, Product.status == "available")
        .order_by(Product.created_at.desc())
        .limit(3)
        .all()
    )
    conversations = (
        db.query(Conversation).filter_by(product_id=pid, seller_id=request.state.user.id).all()
        if request.state.user.id == p.seller_id
        else []
    )
    return render(
        request,
        "marketplace/detail.html",
        product=p,
        saved=saved,
        related=related,
        conversations=conversations,
    )


@router.api_route(
    "/{pid:int}/whatsapp",
    methods=["POST"],
    dependencies=[Depends(require_member), Depends(limit("15 per minute"))],
    response_model=None,
)
def whatsapp(request: Request, pid: int, db: Session = Depends(get_db)):
    from urllib.parse import urlencode

    from ..models import AnalyticsEvent
    from ..services.validation import phone

    p = product_access(request, db, pid)
    u = p.seller
    if (
        not u.profile_visible
        or not u.contact_visible
        or (not u.show_whatsapp)
        or (not u.whatsapp)
        or (p.status not in ("available", "reserved"))
    ):
        abort(404)
    number = phone(u.whatsapp)
    if p.seller_id != request.state.user.id:
        db.add(AnalyticsEvent(product_id=p.id, kind="whatsapp"))
        db.commit()
    message = f"Hi, I found your listing '{p.title}' on XELO CampusKart. Is it still available?"
    return redirect("https://wa.me/" + number + "?" + urlencode({"text": message}))


@router.api_route(
    "/image/{key}", methods=["GET"], dependencies=[Depends(require_member)], response_model=None
)
def image(request: Request, key: str, db: Session = Depends(get_db)):
    original = key.removeprefix("thumb-")
    entry = db.query(ProductImage).filter_by(key=original).first_or_404()
    product_access(request, db, entry.product_id)
    path = get_storage(request.app.state.settings).path(key)
    if not path.is_file():
        abort(404)
    response = send_file(path, mimetype="image/webp")
    response.headers["Cache-Control"] = "private, no-store"
    return response
