import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from ..database import Session, get_db
from ..dependencies import prepare_request, require_member
from ..middleware.rate_limit import limit
from ..models import Conversation, Message, Notification
from ..models.identity import now
from ..schemas.responses import MessagePoll
from ..services.security import product_access
from ..services.validation import field, integer
from ..web import abort, redirect, render

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/messages", tags=["messaging"], dependencies=[Depends(prepare_request)])


def access(request: Request, db: Session, cid):
    c = db.get_or_404(Conversation, cid)
    if (
        request.state.user.id not in (c.buyer_id, c.seller_id)
        or c.product.campus_id != request.state.user.campus_id
    ):
        abort(404)
    return c


@router.api_route("", methods=["GET"], dependencies=[Depends(require_member)], response_model=None)
def index(request: Request, db: Session = Depends(get_db)):
    page = (
        db.query(Conversation)
        .filter(
            or_(
                Conversation.buyer_id == request.state.user.id,
                Conversation.seller_id == request.state.user.id,
            )
        )
        .order_by(Conversation.updated_at.desc())
        .paginate(per_page=20, error_out=False, page=max(1, integer(request.query_params.get("page"), 1)))
    )
    return render(request, "messaging/index.html", page=page)


@router.api_route(
    "/start/{pid:int}",
    methods=["POST"],
    dependencies=[Depends(require_member), Depends(limit("15 per hour"))],
    response_model=None,
)
def start(request: Request, pid: int, db: Session = Depends(get_db)):
    p = product_access(request, db, pid)
    if p.seller_id == request.state.user.id:
        abort(400, "You cannot message yourself.")
    if p.status not in ("available", "reserved"):
        abort(400, "This listing is no longer available for contact.")
    c = (
        db.query(Conversation)
        .filter_by(product_id=pid, buyer_id=request.state.user.id, seller_id=p.seller_id)
        .first()
    )
    if not c:
        c = Conversation(product_id=pid, buyer_id=request.state.user.id, seller_id=p.seller_id)
        db.add(c)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            c = (
                db.query(Conversation)
                .filter_by(product_id=pid, buyer_id=request.state.user.id, seller_id=p.seller_id)
                .one()
            )
    return redirect("/messages/" + str(c.id))


@router.api_route(
    "/{cid:int}",
    methods=["GET"],
    dependencies=[Depends(require_member), Depends(limit("20 per minute", methods=["POST"]))],
    response_model=None,
    operation_id="messaging_conversation_get",
)
@router.api_route(
    "/{cid:int}",
    methods=["POST"],
    dependencies=[Depends(require_member), Depends(limit("20 per minute", methods=["POST"]))],
    response_model=None,
    operation_id="messaging_conversation_post",
)
def conversation(request: Request, cid: int, db: Session = Depends(get_db)):
    c = access(request, db, cid)
    if request.method == "POST":
        if not c.buyer.active or not c.seller.active or c.product.status in ("removed", "hidden", "draft"):
            abort(403, "Messaging is unavailable for this listing.")
        message = Message(
            conversation_id=cid, sender_id=request.state.user.id, body=field(request, "body", 1, 3000)
        )
        db.add(message)
        c.updated_at = now()
        recipient = c.seller_id if request.state.user.id == c.buyer_id else c.buyer_id
        db.add(
            Notification(
                user_id=recipient,
                kind="message",
                title="New message from " + request.state.user.display_name,
                body=c.product.title,
                link="/messages/" + str(cid),
            )
        )
        db.commit()
        return redirect("/messages/" + str(cid))
    query = db.query(Message).filter_by(conversation_id=cid)
    before = integer(request.query_params.get("before"))
    if before:
        query = query.filter(Message.id < before)
    messages = list(reversed(query.order_by(Message.id.desc()).limit(40).all()))
    return render(
        request,
        "messaging/conversation.html",
        conversation=c,
        messages=messages,
        older=bool(messages and query.filter(Message.id < messages[0].id).first()),
        historical=bool(before),
    )


@router.api_route(
    "/{cid:int}/poll",
    methods=["GET"],
    dependencies=[Depends(require_member), Depends(limit("30 per minute"))],
    response_model=MessagePoll,
)
def poll(request: Request, cid: int, db: Session = Depends(get_db)):
    access(request, db, cid)
    after = max(0, integer(request.query_params.get("after")))
    rows = (
        db.query(Message)
        .filter(Message.conversation_id == cid, Message.id > after)
        .order_by(Message.id)
        .limit(100)
        .all()
    )
    return {
        "messages": [
            {
                "id": m.id,
                "body": m.body,
                "mine": m.sender_id == request.state.user.id,
                "sender": m.sender.display_name,
                "created_at": m.created_at.isoformat() + "Z",
                "read": bool(m.read_at),
            }
            for m in rows
        ]
    }


@router.api_route(
    "/{cid:int}/read", methods=["POST"], dependencies=[Depends(require_member)], response_model=None
)
def read(request: Request, cid: int, db: Session = Depends(get_db)):
    access(request, db, cid)
    through = integer(request.state.form.get("through"))
    query = db.query(Message).filter(
        Message.conversation_id == cid, Message.sender_id != request.state.user.id, Message.read_at.is_(None)
    )
    if through:
        query = query.filter(Message.id <= through)
    query.update({"read_at": now()})
    db.commit()
    return {"ok": True}
