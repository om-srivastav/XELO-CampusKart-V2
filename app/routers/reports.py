import logging

from fastapi import APIRouter, Depends, Request

from ..database import Session, get_db
from ..dependencies import prepare_request, require_member
from ..middleware.rate_limit import limit
from ..models import Message, Report, User
from ..services.security import product_access
from ..services.validation import field, integer
from ..web import abort, flash, redirect, render

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(prepare_request)])
REASONS = ["scam", "fake_listing", "spam", "wrong_category", "prohibited_item", "harassment", "other"]


@router.api_route(
    "/new",
    methods=["GET"],
    dependencies=[Depends(require_member), Depends(limit("10 per hour", methods=["POST"]))],
    response_model=None,
    operation_id="reports_create_get",
)
@router.api_route(
    "/new",
    methods=["POST"],
    dependencies=[Depends(require_member), Depends(limit("10 per hour", methods=["POST"]))],
    response_model=None,
    operation_id="reports_create_post",
)
def create(request: Request, db: Session = Depends(get_db)):
    kind = request.query_params.get("kind")
    target = integer(request.query_params.get("target"))
    if kind == "product":
        product_access(request, db, target)
    elif kind == "user":
        u = db.get_or_404(User, target)
        if u.campus_id != request.state.user.campus_id or not u.active:
            abort(404)
    elif kind == "message":
        m = db.get_or_404(Message, target)
        from ..routers.messaging import access

        access(request, db, m.conversation_id)
    else:
        abort(400, "Invalid report target.")
    if request.method == "POST":
        reason = field(request, "reason", 1, 40)
        if reason not in REASONS:
            abort(400, "Choose a report reason.")
        db.add(
            Report(
                reporter_id=request.state.user.id,
                kind=kind,
                target_id=target,
                reason=reason,
                description=field(request, "description", 0, 2000),
            )
        )
        db.commit()
        flash(request, "Report received. Our moderators will review it.", "success")
        return redirect("/reports")
    return render(request, "report.html", kind=kind, reasons=REASONS)


@router.api_route("", methods=["GET"], dependencies=[Depends(require_member)], response_model=None)
def index(request: Request, db: Session = Depends(get_db)):
    page = (
        db.query(Report)
        .filter_by(reporter_id=request.state.user.id)
        .order_by(Report.created_at.desc())
        .paginate(per_page=20, error_out=False, page=max(1, integer(request.query_params.get("page"), 1)))
    )
    return render(request, "reports.html", page=page)
