import logging
import re

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from ..database import Session, get_db
from ..dependencies import prepare_request, require_admin
from ..models import (
    AdminAction,
    Campus,
    Category,
    Conversation,
    Message,
    Notification,
    Product,
    Report,
    Review,
    User,
    UserSession,
)
from ..services.validation import field, integer, slug
from ..web import abort, flash, redirect, render

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(prepare_request)])


@router.api_route("", methods=["GET"], dependencies=[Depends(require_admin)], response_model=None)
def index(request: Request, db: Session = Depends(get_db)):
    section = request.query_params.get("section", "reports")
    models = {
        "users": User,
        "products": Product,
        "categories": Category,
        "campuses": Campus,
        "reports": Report,
        "reviews": Review,
        "audit": AdminAction,
        "conversations": Conversation,
    }
    model = models.get(section)
    if not model:
        abort(400)
    page = (
        db.query(model)
        .order_by(model.id.desc())
        .paginate(per_page=25, error_out=False, page=max(1, integer(request.query_params.get("page"), 1)))
    )
    stats = {
        "Users": db.query(User).count(),
        "Active users": db.query(User).filter_by(active=True).count(),
        "Listings": db.query(Product).count(),
        "Sold": db.query(Product).filter_by(status="sold").count(),
        "Open reports": db.query(Report).filter_by(status="open").count(),
        "Views": db.query(func.coalesce(func.sum(Product.views), 0)).scalar(),
        "Messages": db.query(Message).count(),
    }
    return render(request, "admin.html", page=page, section=section, stats=stats)


@router.api_route("/action", methods=["POST"], dependencies=[Depends(require_admin)], response_model=None)
def action(request: Request, db: Session = Depends(get_db)):
    action = field(request, "action", 1, 40)
    target = integer(request.state.form.get("target"))
    reason = field(request, "reason", 3, 500)
    recipient = None
    if action in ("suspend_user", "activate_user"):
        user = db.get_or_404(User, target)
        if user.is_admin and action == "suspend_user":
            abort(400, "Administrators cannot be suspended through this action.")
        user.active = action == "activate_user"
        if not user.active:
            db.query(UserSession).filter_by(user_id=target).update({"revoked": True})
        recipient = user.id
    elif action in ("remove_product", "restore_product"):
        p = db.get_or_404(Product, target)
        p.status = "removed" if action == "remove_product" else "hidden"
        recipient = p.seller_id
    elif action in ("resolve_report", "dismiss_report"):
        report = db.get_or_404(Report, target)
        report.status = "resolved" if action == "resolve_report" else "dismissed"
        recipient = report.reporter_id
    elif action in ("hide_review", "restore_review"):
        review = db.get_or_404(Review, target)
        review.hidden = action == "hide_review"
        recipient = review.reviewer_id
    else:
        abort(400, "Unknown administrative action.")
    db.add(AdminAction(admin_id=request.state.user.id, action=action, target=str(target), reason=reason))
    if recipient:
        db.add(
            Notification(
                user_id=recipient,
                kind="moderation",
                title="Moderation update",
                body="An item associated with your account was reviewed: " + action.replace("_", " ") + ".",
                link="/reports" if "report" in action else "/dashboard",
            )
        )
    db.commit()
    flash(request, "Action applied and recorded in the audit log.", "success")
    return redirect("/admin")


@router.api_route("/category", methods=["POST"], dependencies=[Depends(require_admin)], response_model=None)
def category(request: Request, db: Session = Depends(get_db)):
    target = integer(request.state.form.get("id"))
    c = db.get_or_404(Category, target) if target else Category()
    c.name = field(request, "name", 2, 80)
    c.slug = slug(c.name)
    c.description = field(request, "description", 0, 300)
    c.icon = field(request, "icon", 0, 10) or "◇"
    c.position = integer(request.state.form.get("position"))
    c.active = request.state.form.get("active") == "on"
    db.add(c)
    db.add(
        AdminAction(
            admin_id=request.state.user.id,
            action="save_category",
            target=str(target),
            reason=field(request, "reason", 3, 500),
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        abort(400, "Category name already exists.")
    return redirect("/admin?section=categories")


@router.api_route("/campus", methods=["POST"], dependencies=[Depends(require_admin)], response_model=None)
def campus(request: Request, db: Session = Depends(get_db)):
    target = integer(request.state.form.get("id"))
    c = db.get_or_404(Campus, target) if target else Campus()
    c.name = field(request, "name", 2, 120)
    c.city = field(request, "city", 2, 100)
    domains = [s.strip().lower() for s in field(request, "domains", 0, 500).split(",") if s.strip()]
    if any((not re.fullmatch("[a-z0-9.-]+\\.[a-z]{2,63}", s) for s in domains)):
        abort(400, "Enter comma-separated email domains without @.")
    c.domains = ",".join(domains)
    c.active = request.state.form.get("active") == "on"
    db.add(c)
    db.add(
        AdminAction(
            admin_id=request.state.user.id,
            action="save_campus",
            target=str(target),
            reason=field(request, "reason", 3, 500),
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        abort(400, "Campus name already exists.")
    return redirect("/admin?section=campuses")
