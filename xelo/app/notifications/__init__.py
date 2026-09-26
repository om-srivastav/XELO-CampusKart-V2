from flask import Blueprint, abort, g, redirect, render_template
from sqlalchemy import or_

from ..extensions import db
from ..models import Conversation, Message, Notification
from ..models.identity import now
from ..services.security import login_required

bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@bp.get("")
@login_required
def index():
    page = (
        Notification.query.filter_by(user_id=g.user.id)
        .order_by(Notification.created_at.desc())
        .paginate(per_page=20, error_out=False)
    )
    return render_template("notifications.html", page=page)


@bp.get("/counts")
@login_required
def counts():
    unread = (
        Message.query.join(Conversation)
        .filter(
            or_(Conversation.buyer_id == g.user.id, Conversation.seller_id == g.user.id),
            Message.sender_id != g.user.id,
            Message.read_at.is_(None),
        )
        .count()
    )
    return {
        "notifications": Notification.query.filter_by(user_id=g.user.id, read_at=None).count(),
        "messages": unread,
    }


@bp.post("/<int:nid>/read")
@login_required
def read(nid):
    note = db.get_or_404(Notification, nid)
    if note.user_id != g.user.id:
        abort(404)
    note.read_at = now()
    db.session.commit()
    return redirect(note.link)


@bp.post("/read-all")
@login_required
def read_all():
    Notification.query.filter_by(user_id=g.user.id, read_at=None).update({"read_at": now()})
    db.session.commit()
    return redirect("/notifications")
