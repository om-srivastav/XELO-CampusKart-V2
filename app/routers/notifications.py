import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy import or_

from ..database import Session, get_db
from ..dependencies import prepare_request, require_login
from ..models import Conversation, Message, Notification
from ..models.identity import now
from ..schemas.responses import NotificationCounts
from ..services.validation import integer
from ..web import abort, redirect, render

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notifications", tags=["notifications"], dependencies=[Depends(prepare_request)])


@router.api_route("", methods=["GET"], dependencies=[Depends(require_login)], response_model=None)
def index(request: Request, db: Session = Depends(get_db)):
    page = (
        db.query(Notification)
        .filter_by(user_id=request.state.user.id)
        .order_by(Notification.created_at.desc())
        .paginate(per_page=20, error_out=False, page=max(1, integer(request.query_params.get("page"), 1)))
    )
    return render(request, "notifications.html", page=page)


@router.api_route(
    "/counts", methods=["GET"], dependencies=[Depends(require_login)], response_model=NotificationCounts
)
def counts(request: Request, db: Session = Depends(get_db)):
    unread = (
        db.query(Message)
        .join(Conversation)
        .filter(
            or_(
                Conversation.buyer_id == request.state.user.id,
                Conversation.seller_id == request.state.user.id,
            ),
            Message.sender_id != request.state.user.id,
            Message.read_at.is_(None),
        )
        .count()
    )
    return {
        "notifications": db.query(Notification)
        .filter_by(user_id=request.state.user.id, read_at=None)
        .count(),
        "messages": unread,
    }


@router.api_route(
    "/{nid:int}/read", methods=["POST"], dependencies=[Depends(require_login)], response_model=None
)
def read(request: Request, nid: int, db: Session = Depends(get_db)):
    note = db.get_or_404(Notification, nid)
    if note.user_id != request.state.user.id:
        abort(404)
    note.read_at = now()
    db.commit()
    return redirect(note.link)


@router.api_route("/read-all", methods=["POST"], dependencies=[Depends(require_login)], response_model=None)
def read_all(request: Request, db: Session = Depends(get_db)):
    db.query(Notification).filter_by(user_id=request.state.user.id, read_at=None).update({"read_at": now()})
    db.commit()
    return redirect("/notifications")
