from flask import Blueprint, abort, flash, g, redirect, render_template, request

from ..extensions import db, limiter
from ..models import Message, Report, User
from ..services.security import member_required, product_access
from ..services.validation import field, integer

bp = Blueprint("reports", __name__, url_prefix="/reports")
REASONS = ["scam", "fake_listing", "spam", "wrong_category", "prohibited_item", "harassment", "other"]


@bp.route("/new", methods=["GET", "POST"])
@member_required
@limiter.limit("10 per hour", methods=["POST"])
def create():
    kind = request.args.get("kind")
    target = integer(request.args.get("target"))
    if kind == "product":
        product_access(target)
    elif kind == "user":
        u = db.get_or_404(User, target)
        if u.campus_id != g.user.campus_id or not u.active:
            abort(404)
    elif kind == "message":
        m = db.get_or_404(Message, target)
        from ..messaging import access

        access(m.conversation_id)
    else:
        abort(400, "Invalid report target.")
    if request.method == "POST":
        reason = field("reason", 1, 40)
        if reason not in REASONS:
            abort(400, "Choose a report reason.")
        db.session.add(
            Report(
                reporter_id=g.user.id,
                kind=kind,
                target_id=target,
                reason=reason,
                description=field("description", 0, 2000),
            )
        )
        db.session.commit()
        flash("Report received. Our moderators will review it.", "success")
        return redirect("/reports")
    return render_template("report.html", kind=kind, reasons=REASONS)


@bp.get("")
@member_required
def index():
    page = (
        Report.query.filter_by(reporter_id=g.user.id)
        .order_by(Report.created_at.desc())
        .paginate(per_page=20, error_out=False)
    )
    return render_template("reports.html", page=page)
