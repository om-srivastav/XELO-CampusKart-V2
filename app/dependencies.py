"""Request parsing and authorization dependencies shared by native APIRouters."""

from datetime import timedelta

from fastapi import Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import FormData, UploadFile

from .database import Session, get_db
from .models import UserSession
from .models.identity import now
from .security import check_csrf, digest
from .web import abort


def load_identity(request, db):
    request.state.user = None
    request.state.login_session = None
    raw = request.session.get("sid")
    if not raw:
        return
    record = db.query(UserSession).filter_by(token_hash=digest(raw), revoked=False).first()
    settings = request.app.state.settings
    if (
        not record
        or record.expires_at <= now()
        or record.last_seen < now() - timedelta(hours=settings.SESSION_IDLE_HOURS)
        or not record.user.active
    ):
        request.session.clear()
        return
    request.state.user, request.state.login_session = record.user, record
    if record.last_seen < now() - timedelta(minutes=5):
        record.last_seen = now()
        db.commit()


async def prepare_request(request: Request, db: Session = Depends(get_db)):
    request.state.user = None
    request.state.login_session = None
    request.state.form = FormData()
    request.state.files = FormData()
    parsed = None
    try:
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            parsed = await request.form(max_files=8, max_fields=100, max_part_size=256 * 1024)
            request.state.form = FormData(
                [(k, v) for k, v in parsed.multi_items() if not isinstance(v, UploadFile)]
            )
            request.state.files = FormData(
                [(k, v) for k, v in parsed.multi_items() if isinstance(v, UploadFile)]
            )
            check_csrf(request)
        from .middleware.rate_limit import enforce

        await run_in_threadpool(
            enforce, request, "300 per minute", request.client.host if request.client else "unknown", "global"
        )
        await run_in_threadpool(load_identity, request, db)
        yield
    finally:
        if parsed is not None:
            await parsed.close()


def require_login(request: Request, prepared=Depends(prepare_request)):
    if not request.state.user:
        raise HTTPException(302, headers={"Location": "/auth/login?next=" + request.url.path})
    return request.state.user


def require_member(request: Request, user=Depends(require_login)):
    if not user.campus.active:
        abort(403, "This campus is currently unavailable.")
    return user


def require_admin(request: Request, user=Depends(require_login)):
    if not user.is_admin:
        abort(403)
    return user
