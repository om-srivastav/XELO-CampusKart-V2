import secrets
import smtplib
from datetime import timedelta
from email.message import EmailMessage
from pathlib import Path

from flask import current_app

from ..extensions import db
from ..models import AccountToken
from ..models.identity import now
from .security import digest


def send_token(user, purpose):
    if purpose != "reset":
        raise ValueError("Only password reset emails are supported.")
    raw = secrets.token_urlsafe(32)
    record = AccountToken(
        user_id=user.id, token_hash=digest(raw), purpose=purpose, expires_at=now() + timedelta(minutes=30)
    )
    db.session.add(record)
    db.session.flush()
    message = EmailMessage()
    message["Subject"] = "Xelo: reset your password"
    message["From"] = current_app.config["SMTP_FROM"] or "development@localhost"
    message["To"] = user.email
    link = current_app.config["BASE_URL"].rstrip("/") + "/auth/" + purpose + "/" + raw
    message.set_content(
        "Open this link within 30 minutes. If you did not request it, ignore this email.\n\n" + link
    )
    if current_app.config["MAIL_MODE"] == "file" and current_app.config["APP_ENV"] != "production":
        folder = Path(current_app.config.get("MAIL_FOLDER", Path(current_app.instance_path) / "mail"))
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (secrets.token_hex(12) + ".eml")).write_text(message.as_string(), encoding="utf-8")
    else:
        with smtplib.SMTP(
            current_app.config["SMTP_HOST"], current_app.config["SMTP_PORT"], timeout=10
        ) as server:
            if current_app.config["SMTP_TLS"]:
                server.starttls()
            if current_app.config["SMTP_USER"]:
                server.login(current_app.config["SMTP_USER"], current_app.config["SMTP_PASSWORD"])
            server.send_message(message)
    db.session.commit()
