import re

from flask import Blueprint, abort, flash, g, redirect, render_template, request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from ..extensions import db
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
from ..services.security import admin_required
from ..services.validation import field, integer, slug

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("")
@admin_required
def index():
    section = request.args.get("section", "reports")
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
    page = model.query.order_by(model.id.desc()).paginate(per_page=25, error_out=False)
    stats = {
        "Users": User.query.count(),
        "Active users": User.query.filter_by(active=True).count(),
        "Listings": Product.query.count(),
        "Sold": Product.query.filter_by(status="sold").count(),
        "Open reports": Report.query.filter_by(status="open").count(),
        "Views": db.session.query(func.coalesce(func.sum(Product.views), 0)).scalar(),
        "Messages": Message.query.count(),
    }
    return render_template("admin.html", page=page, section=section, stats=stats)


@bp.post("/action")
@admin_required
def action():
    action = field("action", 1, 40)
    target = integer(request.form.get("target"))
    reason = field("reason", 3, 500)
    recipient = None
    if action in ("suspend_user", "activate_user"):
        user = db.get_or_404(User, target)
        if user.is_admin and action == "suspend_user":
            abort(400, "Administrators cannot be suspended through this action.")
        user.active = action == "activate_user"
        if not user.active:
            UserSession.query.filter_by(user_id=target).update({"revoked": True})
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
    db.session.add(AdminAction(admin_id=g.user.id, action=action, target=str(target), reason=reason))
    if recipient:
        db.session.add(
            Notification(
                user_id=recipient,
                kind="moderation",
                title="Moderation update",
                body="An item associated with your account was reviewed: " + action.replace("_", " ") + ".",
                link="/reports" if "report" in action else "/dashboard",
            )
        )
    db.session.commit()
    flash("Action applied and recorded in the audit log.", "success")
    return redirect("/admin")


@bp.post("/category")
@admin_required
def category():
    target = integer(request.form.get("id"))
    c = db.get_or_404(Category, target) if target else Category()
    c.name = field("name", 2, 80)
    c.slug = slug(c.name)
    c.description = field("description", 0, 300)
    c.icon = field("icon", 0, 10) or "◇"
    c.position = integer(request.form.get("position"))
    c.active = request.form.get("active") == "on"
    db.session.add(c)
    db.session.add(
        AdminAction(
            admin_id=g.user.id, action="save_category", target=str(target), reason=field("reason", 3, 500)
        )
    )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(400, "Category name already exists.")
    return redirect("/admin?section=categories")


@bp.post("/campus")
@admin_required
def campus():
    target = integer(request.form.get("id"))
    c = db.get_or_404(Campus, target) if target else Campus()
    c.name = field("name", 2, 120)
    c.city = field("city", 2, 100)
    domains = [s.strip().lower() for s in field("domains", 0, 500).split(",") if s.strip()]
    if any(not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,63}", s) for s in domains):
        abort(400, "Enter comma-separated email domains without @.")
    c.domains = ",".join(domains)
    c.active = request.form.get("active") == "on"
    db.session.add(c)
    db.session.add(
        AdminAction(
            admin_id=g.user.id, action="save_campus", target=str(target), reason=field("reason", 3, 500)
        )
    )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(400, "Campus name already exists.")
    return redirect("/admin?section=campuses")
