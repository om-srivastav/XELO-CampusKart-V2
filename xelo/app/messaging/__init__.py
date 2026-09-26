from flask import Blueprint, abort, g, redirect, render_template, request
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from ..extensions import db, limiter
from ..models import Conversation, Message, Notification
from ..models.identity import now
from ..services.security import member_required, product_access
from ..services.validation import field, integer

bp = Blueprint("messages", __name__, url_prefix="/messages")


def access(cid):
    c = db.get_or_404(Conversation, cid)
    if g.user.id not in (c.buyer_id, c.seller_id) or c.product.campus_id != g.user.campus_id:
        abort(404)
    return c


@bp.get("")
@member_required
def index():
    page = (
        Conversation.query.filter(
            or_(Conversation.buyer_id == g.user.id, Conversation.seller_id == g.user.id)
        )
        .order_by(Conversation.updated_at.desc())
        .paginate(per_page=20, error_out=False)
    )
    return render_template("messaging/index.html", page=page)


@bp.post("/start/<int:pid>")
@member_required
@limiter.limit("15 per hour")
def start(pid):
    p = product_access(pid)
    if p.seller_id == g.user.id:
        abort(400, "You cannot message yourself.")
    if p.status not in ("available", "reserved"):
        abort(400, "This listing is no longer available for contact.")
    c = Conversation.query.filter_by(product_id=pid, buyer_id=g.user.id, seller_id=p.seller_id).first()
    if not c:
        c = Conversation(product_id=pid, buyer_id=g.user.id, seller_id=p.seller_id)
        db.session.add(c)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            c = Conversation.query.filter_by(product_id=pid, buyer_id=g.user.id, seller_id=p.seller_id).one()
    return redirect("/messages/" + str(c.id))


@bp.route("/<int:cid>", methods=["GET", "POST"])
@member_required
@limiter.limit("20 per minute", methods=["POST"])
def conversation(cid):
    c = access(cid)
    if request.method == "POST":
        if not c.buyer.active or not c.seller.active or c.product.status in ("removed", "hidden", "draft"):
            abort(403, "Messaging is unavailable for this listing.")
        message = Message(conversation_id=cid, sender_id=g.user.id, body=field("body", 1, 3000))
        db.session.add(message)
        c.updated_at = now()
        recipient = c.seller_id if g.user.id == c.buyer_id else c.buyer_id
        db.session.add(
            Notification(
                user_id=recipient,
                kind="message",
                title="New message from " + g.user.display_name,
                body=c.product.title,
                link="/messages/" + str(cid),
            )
        )
        db.session.commit()
        return redirect("/messages/" + str(cid))
    query = Message.query.filter_by(conversation_id=cid)
    before = integer(request.args.get("before"))
    if before:
        query = query.filter(Message.id < before)
    messages = list(reversed(query.order_by(Message.id.desc()).limit(40).all()))
    return render_template(
        "messaging/conversation.html",
        conversation=c,
        messages=messages,
        older=bool(messages and query.filter(Message.id < messages[0].id).first()),
        historical=bool(before),
    )


@bp.get("/<int:cid>/poll")
@member_required
@limiter.limit("30 per minute")
def poll(cid):
    access(cid)
    after = max(0, integer(request.args.get("after")))
    rows = (
        Message.query.filter(Message.conversation_id == cid, Message.id > after)
        .order_by(Message.id)
        .limit(100)
        .all()
    )
    return {
        "messages": [
            {
                "id": m.id,
                "body": m.body,
                "mine": m.sender_id == g.user.id,
                "sender": m.sender.display_name,
                "created_at": m.created_at.isoformat() + "Z",
                "read": bool(m.read_at),
            }
            for m in rows
        ]
    }


@bp.post("/<int:cid>/read")
@member_required
def read(cid):
    access(cid)
    through = integer(request.form.get("through"))
    query = Message.query.filter(
        Message.conversation_id == cid, Message.sender_id != g.user.id, Message.read_at.is_(None)
    )
    if through:
        query = query.filter(Message.id <= through)
    query.update({"read_at": now()})
    db.session.commit()
    return {"ok": True}
