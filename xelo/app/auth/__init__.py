import re
import secrets
from datetime import timedelta

from email_validator import EmailNotValidError, validate_email
from flask import Blueprint, abort, flash, g, redirect, render_template, request, session
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db, limiter
from ..models import AccountToken, Campus, LoginHistory, User, UserSession
from ..models.identity import now
from ..services.mail import send_token
from ..services.security import digest, login_required, safe_next
from ..services.validation import field, integer, password

bp = Blueprint("auth", __name__, url_prefix="/auth")
DUMMY_HASH = generate_password_hash(secrets.token_urlsafe(20))


@bp.route("/signup", methods=["GET", "POST"])
@limiter.limit("8 per hour", methods=["POST"])
def signup():
    if request.method == "POST":
        username = field("username", 3, 40).lower()
        if not re.fullmatch(r"[a-z0-9_]+", username):
            abort(400, "Username may contain letters, numbers and underscores.")
        try:
            email = validate_email(field("email", 3, 254), check_deliverability=False).normalized.lower()
        except EmailNotValidError:
            abort(400, "Enter a valid email address.")
        display_name = field("display_name", 2, 80)
        password_hash = generate_password_hash(password())
        if "college_name" in request.form:
            college_name = " ".join(field("college_name", 2, 120).split())
            if len(college_name) < 2:
                abort(400, "Enter your college's full name.")
            # Reuse established membership boundaries for equivalent typed names.
            college = next(
                (
                    c
                    for c in Campus.query.all()
                    if " ".join(c.name.split()).casefold() == college_name.casefold()
                ),
                None,
            )
            if college is None:
                college = Campus(name=college_name, city="", domains="")
                db.session.add(college)
                try:
                    db.session.flush()
                except IntegrityError:
                    db.session.rollback()
                    abort(409, "This college was just registered. Please submit again.")
        else:
            # Accept older clients that still submit the registered campus ID.
            college = db.session.get(Campus, integer(request.form.get("campus_id")))
        if not college or not college.active:
            abort(400, "This campus is unavailable. Contact the administrator.")
        user = User(
            username=username,
            email=email,
            display_name=display_name,
            password_hash=password_hash,
            campus_id=college.id,
        )
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            abort(400, "This email or username is already registered.")
        flash("Account created. Sign in to start using your campus marketplace.", "success")
        return redirect("/auth/login")
    return render_template("auth/signup.html")


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
@limiter.limit(
    "30 per hour", key_func=lambda: digest(request.form.get("email", "").strip().lower()), methods=["POST"]
)
def login():
    if request.method == "POST":
        user = User.query.filter_by(email=field("email", 3, 254).lower()).first()
        value = request.form.get("password", "")[:129]
        valid = check_password_hash(user.password_hash if user else DUMMY_HASH, value)
        db.session.add(
            LoginHistory(user_id=user.id if user else None, success=bool(valid and user and user.active))
        )
        db.session.commit()
        if not valid or not user or not user.active:
            flash("Email or password is incorrect, or the account is inactive.", "error")
            return render_template("auth/login.html"), 401
        session.clear()
        raw = secrets.token_urlsafe(32)
        record = UserSession(user_id=user.id, token_hash=digest(raw), expires_at=now() + timedelta(days=7))
        db.session.add(record)
        db.session.commit()
        session["sid"] = raw
        return redirect(safe_next(request.args.get("next"), "/profile/edit"))
    return render_template("auth/login.html")


@bp.post("/logout")
@login_required
def logout():
    g.login_session.revoked = True
    db.session.commit()
    session.clear()
    return redirect("/")


@bp.route("/password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        if not check_password_hash(g.user.password_hash, request.form.get("current", "")):
            abort(400, "Current password is incorrect.")
        g.user.password_hash = generate_password_hash(password())
        AccountToken.query.filter_by(user_id=g.user.id, purpose="reset", used=False).update({"used": True})
        UserSession.query.filter(
            UserSession.user_id == g.user.id, UserSession.id != g.login_session.id
        ).update({"revoked": True})
        db.session.commit()
        raw = secrets.token_urlsafe(32)
        g.login_session.token_hash = digest(raw)
        db.session.commit()
        session.clear()
        session["sid"] = raw
        flash("Password changed. Other sessions have been revoked.", "success")
        return redirect("/auth/sessions")
    return render_template("auth/password.html")


@bp.route("/forgot", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def forgot():
    if request.method == "POST":
        user = User.query.filter_by(email=field("email", 3, 254).lower(), active=True).first()
        if user:
            try:
                send_token(user, "reset")
            except Exception:
                db.session.rollback()
                from flask import current_app

                current_app.logger.warning("Password reset delivery failed")
        flash("If an active account matches, a reset link has been sent.", "success")
        return redirect("/auth/login")
    return render_template("auth/forgot.html")


@bp.route("/<purpose>/<token>", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def token_action(purpose, token):
    if purpose != "reset":
        abort(404)
    record = AccountToken.query.filter_by(token_hash=digest(token), purpose=purpose, used=False).first()
    if not record or record.expires_at <= now():
        abort(400, "This link has expired or was already used.")
    user = db.session.get(User, record.user_id)
    if not user.active:
        abort(400, "This account is inactive.")
    if request.method == "POST":
        if purpose == "reset":
            user.password_hash = generate_password_hash(password())
            UserSession.query.filter_by(user_id=user.id).update({"revoked": True})
        # Conditional consume prevents concurrent reuse.
        changed = AccountToken.query.filter_by(id=record.id, used=False).update({"used": True})
        if not changed:
            db.session.rollback()
            abort(400, "This link was already used.")
        if purpose == "reset":
            AccountToken.query.filter_by(user_id=user.id, purpose="reset", used=False).update({"used": True})
        db.session.commit()
        flash("Password reset. Sign in again.", "success")
        return redirect("/auth/login")
    return render_template("auth/token.html", purpose=purpose)


@bp.route("/sessions")
@login_required
def sessions():
    return render_template(
        "auth/sessions.html",
        sessions=UserSession.query.filter_by(user_id=g.user.id, revoked=False)
        .order_by(UserSession.created_at.desc())
        .limit(50)
        .all(),
        history=LoginHistory.query.filter_by(user_id=g.user.id)
        .order_by(LoginHistory.created_at.desc())
        .limit(20)
        .all(),
    )


@bp.post("/sessions/<int:sid>/revoke")
@login_required
def revoke(sid):
    record = db.get_or_404(UserSession, sid)
    if record.user_id != g.user.id:
        abort(404)
    record.revoked = True
    db.session.commit()
    if record.id == g.login_session.id:
        session.clear()
    return redirect("/auth/sessions")


@bp.post("/sessions/revoke-others")
@login_required
def revoke_others():
    UserSession.query.filter(UserSession.user_id == g.user.id, UserSession.id != g.login_session.id).update(
        {"revoked": True}
    )
    db.session.commit()
    flash("Other sessions revoked.", "success")
    return redirect("/auth/sessions")


@bp.post("/deactivate")
@login_required
def deactivate():
    if g.user.is_admin:
        abort(400, "An administrator must transfer their role before deactivation.")
    if not check_password_hash(g.user.password_hash, request.form.get("current", "")):
        abort(400, "Current password is incorrect.")
    g.user.active = False
    UserSession.query.filter_by(user_id=g.user.id).update({"revoked": True})
    db.session.commit()
    session.clear()
    return redirect("/")


@bp.get("/form-token")
def form_token():
    from flask_wtf.csrf import generate_csrf

    return {"token": generate_csrf()}, 200, {"Cache-Control": "no-store"}
