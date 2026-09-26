import logging
import re
import secrets
from datetime import timedelta
from typing import Annotated

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.exc import IntegrityError

from ..database import Session, get_db
from ..dependencies import prepare_request, require_login
from ..middleware.rate_limit import limit
from ..models import AccountToken, Campus, LoginHistory, User, UserSession
from ..models.identity import now
from ..schemas.auth import LoginForm
from ..security import digest, generate_csrf
from ..security import hash_password as generate_password_hash
from ..security import verify_password as check_password_hash
from ..services.mail import send_token
from ..services.security import safe_next
from ..services.validation import field, integer, password
from ..web import abort, flash, redirect, render, respond

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(prepare_request)])
DUMMY_HASH = generate_password_hash(secrets.token_urlsafe(20))


@router.api_route(
    "/signup",
    methods=["GET"],
    dependencies=[Depends(limit("8 per hour", methods=["POST"]))],
    response_model=None,
    operation_id="auth_signup_get",
)
@router.api_route(
    "/signup",
    methods=["POST"],
    dependencies=[Depends(limit("8 per hour", methods=["POST"]))],
    response_model=None,
    operation_id="auth_signup_post",
)
def signup(request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        username = field(request, "username", 3, 40).lower()
        if not re.fullmatch("[a-z0-9_]+", username):
            abort(400, "Username may contain letters, numbers and underscores.")
        try:
            email = validate_email(
                field(request, "email", 3, 254), check_deliverability=False
            ).normalized.lower()
        except EmailNotValidError:
            abort(400, "Enter a valid email address.")
        display_name = field(request, "display_name", 2, 80)
        password_hash = generate_password_hash(password(request))
        if "college_name" in request.state.form:
            college_name = " ".join(field(request, "college_name", 2, 120).split())
            if len(college_name) < 2:
                abort(400, "Enter your college's full name.")
            college = next(
                (
                    c
                    for c in db.query(Campus).all()
                    if " ".join(c.name.split()).casefold() == college_name.casefold()
                ),
                None,
            )
            if college is None:
                college = Campus(name=college_name, city="", domains="")
                db.add(college)
                try:
                    db.flush()
                except IntegrityError:
                    db.rollback()
                    abort(409, "This college was just registered. Please submit again.")
        else:
            college = db.get(Campus, integer(request.state.form.get("campus_id")))
        if not college or not college.active:
            abort(400, "This campus is unavailable. Contact the administrator.")
        user = User(
            username=username,
            email=email,
            display_name=display_name,
            password_hash=password_hash,
            campus_id=college.id,
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            abort(400, "This email or username is already registered.")
        flash(request, "Account created. Sign in to start using your campus marketplace.", "success")
        return redirect("/auth/login")
    return render(request, "auth/signup.html")


@router.api_route(
    "/login",
    methods=["GET"],
    dependencies=[
        Depends(limit("10 per minute", methods=["POST"])),
        Depends(limit("30 per hour", by_email=True, methods=["POST"])),
    ],
    response_model=None,
    operation_id="auth_login_get",
)
def login_page(request: Request):
    return render(request, "auth/login.html")


@router.api_route(
    "/login",
    methods=["POST"],
    dependencies=[
        Depends(limit("10 per minute", methods=["POST"])),
        Depends(limit("30 per hour", by_email=True, methods=["POST"])),
    ],
    response_model=None,
    operation_id="auth_login_post",
)
def login(request: Request, db: Session = Depends(get_db), *, credentials: Annotated[LoginForm, Form()]):
    user = db.query(User).filter_by(email=credentials.email.strip().lower()).first()
    value = credentials.password
    valid = check_password_hash(user.password_hash if user else DUMMY_HASH, value)
    db.add(LoginHistory(user_id=user.id if user else None, success=bool(valid and user and user.active)))
    db.commit()
    if not valid or not user or (not user.active):
        flash(request, "Email or password is incorrect, or the account is inactive.", "error")
        return respond(render(request, "auth/login.html"), 401)
    request.session.clear()
    raw = secrets.token_urlsafe(32)
    record = UserSession(
        user_id=user.id,
        token_hash=digest(raw),
        expires_at=now() + timedelta(hours=request.app.state.settings.SESSION_HOURS),
    )
    db.add(record)
    db.commit()
    request.session["sid"] = raw
    return redirect(safe_next(request.query_params.get("next"), "/profile/edit"))


@router.api_route("/logout", methods=["POST"], dependencies=[Depends(require_login)], response_model=None)
def logout(request: Request, db: Session = Depends(get_db)):
    request.state.login_session.revoked = True
    db.commit()
    request.session.clear()
    return redirect("/")


@router.api_route(
    "/password",
    methods=["GET"],
    dependencies=[Depends(require_login)],
    response_model=None,
    operation_id="auth_change_password_get",
)
@router.api_route(
    "/password",
    methods=["POST"],
    dependencies=[Depends(require_login)],
    response_model=None,
    operation_id="auth_change_password_post",
)
def change_password(request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        if not check_password_hash(request.state.user.password_hash, request.state.form.get("current", "")):
            abort(400, "Current password is incorrect.")
        request.state.user.password_hash = generate_password_hash(password(request))
        db.query(AccountToken).filter_by(user_id=request.state.user.id, purpose="reset", used=False).update(
            {"used": True}
        )
        db.query(UserSession).filter(
            UserSession.user_id == request.state.user.id, UserSession.id != request.state.login_session.id
        ).update({"revoked": True})
        db.commit()
        raw = secrets.token_urlsafe(32)
        request.state.login_session.token_hash = digest(raw)
        db.commit()
        request.session.clear()
        request.session["sid"] = raw
        flash(request, "Password changed. Other sessions have been revoked.", "success")
        return redirect("/auth/sessions")
    return render(request, "auth/password.html")


@router.api_route(
    "/forgot",
    methods=["GET"],
    dependencies=[Depends(limit("5 per hour", methods=["POST"]))],
    response_model=None,
    operation_id="auth_forgot_get",
)
@router.api_route(
    "/forgot",
    methods=["POST"],
    dependencies=[Depends(limit("5 per hour", methods=["POST"]))],
    response_model=None,
    operation_id="auth_forgot_post",
)
def forgot(request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        user = db.query(User).filter_by(email=field(request, "email", 3, 254).lower(), active=True).first()
        if user:
            try:
                send_token(user, "reset", db, request.app.state.settings)
            except Exception:
                db.rollback()
                logger.warning("Password reset delivery failed")
        flash(request, "If an active account matches, a reset link has been sent.", "success")
        return redirect("/auth/login")
    return render(request, "auth/forgot.html")


@router.api_route(
    "/{purpose}/{token}",
    methods=["GET"],
    dependencies=[Depends(limit("20 per minute"))],
    response_model=None,
    operation_id="auth_token_action_get",
)
@router.api_route(
    "/{purpose}/{token}",
    methods=["POST"],
    dependencies=[Depends(limit("20 per minute"))],
    response_model=None,
    operation_id="auth_token_action_post",
)
def token_action(request: Request, purpose: str, token: str, db: Session = Depends(get_db)):
    if purpose != "reset":
        abort(404)
    record = db.query(AccountToken).filter_by(token_hash=digest(token), purpose=purpose, used=False).first()
    if not record or record.expires_at <= now():
        abort(400, "This link has expired or was already used.")
    user = db.get(User, record.user_id)
    if not user.active:
        abort(400, "This account is inactive.")
    if request.method == "POST":
        if purpose == "reset":
            user.password_hash = generate_password_hash(password(request))
            db.query(UserSession).filter_by(user_id=user.id).update({"revoked": True})
        changed = db.query(AccountToken).filter_by(id=record.id, used=False).update({"used": True})
        if not changed:
            db.rollback()
            abort(400, "This link was already used.")
        if purpose == "reset":
            db.query(AccountToken).filter_by(user_id=user.id, purpose="reset", used=False).update(
                {"used": True}
            )
        db.commit()
        flash(request, "Password reset. Sign in again.", "success")
        return redirect("/auth/login")
    return render(request, "auth/token.html", purpose=purpose)


@router.api_route("/sessions", methods=["GET"], dependencies=[Depends(require_login)], response_model=None)
def sessions(request: Request, db: Session = Depends(get_db)):
    return render(
        request,
        "auth/sessions.html",
        sessions=db.query(UserSession)
        .filter_by(user_id=request.state.user.id, revoked=False)
        .order_by(UserSession.created_at.desc())
        .limit(50)
        .all(),
        history=db.query(LoginHistory)
        .filter_by(user_id=request.state.user.id)
        .order_by(LoginHistory.created_at.desc())
        .limit(20)
        .all(),
    )


@router.api_route(
    "/sessions/{sid:int}/revoke", methods=["POST"], dependencies=[Depends(require_login)], response_model=None
)
def revoke(request: Request, sid: int, db: Session = Depends(get_db)):
    record = db.get_or_404(UserSession, sid)
    if record.user_id != request.state.user.id:
        abort(404)
    record.revoked = True
    db.commit()
    if record.id == request.state.login_session.id:
        request.session.clear()
    return redirect("/auth/sessions")


@router.api_route(
    "/sessions/revoke-others", methods=["POST"], dependencies=[Depends(require_login)], response_model=None
)
def revoke_others(request: Request, db: Session = Depends(get_db)):
    db.query(UserSession).filter(
        UserSession.user_id == request.state.user.id, UserSession.id != request.state.login_session.id
    ).update({"revoked": True})
    db.commit()
    flash(request, "Other sessions revoked.", "success")
    return redirect("/auth/sessions")


@router.api_route("/deactivate", methods=["POST"], dependencies=[Depends(require_login)], response_model=None)
def deactivate(request: Request, db: Session = Depends(get_db)):
    if request.state.user.is_admin:
        abort(400, "An administrator must transfer their role before deactivation.")
    if not check_password_hash(request.state.user.password_hash, request.state.form.get("current", "")):
        abort(400, "Current password is incorrect.")
    request.state.user.active = False
    db.query(UserSession).filter_by(user_id=request.state.user.id).update({"revoked": True})
    db.commit()
    request.session.clear()
    return redirect("/")


@router.api_route("/form-token", methods=["GET"], dependencies=[], response_model=None)
def form_token(request: Request, db: Session = Depends(get_db)):
    return respond({"token": generate_csrf(request)}, 200, {"Cache-Control": "no-store"})
