"""Password reset delivery through HTTP providers or development mail files."""

import secrets
from datetime import timedelta
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from ..models import AccountToken
from ..models.identity import now
from ..security import digest


class MailDeliveryError(RuntimeError):
    """A deliberately redacted error safe for application logs."""


def _deliver(recipient: str, subject: str, body: str, settings) -> None:
    provider = settings.MAIL_PROVIDER.lower()
    if provider == "file":
        if settings.APP_ENV not in {"development", "test", "testing"}:
            raise MailDeliveryError("File mail delivery is only available in development.")
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings.MAIL_FROM or "development@localhost"
        message["To"] = recipient
        message.set_content(body)
        folder = Path(settings.MAIL_FOLDER)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (secrets.token_hex(12) + ".eml")).write_text(message.as_string(), encoding="utf-8")
        return
    if provider not in {"resend", "brevo"}:
        raise MailDeliveryError("Unsupported mail provider.")
    if not settings.MAIL_API_KEY or not settings.MAIL_FROM:
        raise MailDeliveryError("Mail delivery is not configured.")
    if provider == "resend":
        url = "https://api.resend.com/emails"
        headers = {"Authorization": "Bearer " + settings.MAIL_API_KEY}
        payload = {"from": settings.MAIL_FROM, "to": [recipient], "subject": subject, "text": body}
    else:
        url = "https://api.brevo.com/v3/smtp/email"
        headers = {"api-key": settings.MAIL_API_KEY}
        name, address = parseaddr(settings.MAIL_FROM)
        sender = {"email": address}
        if name:
            sender["name"] = name
        payload = {"sender": sender, "to": [{"email": recipient}], "subject": subject, "textContent": body}
    try:
        with httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0), follow_redirects=False) as client:
            response = client.post(url, headers=headers, json=payload)
            if not 200 <= response.status_code < 300:
                raise MailDeliveryError("Mail provider rejected delivery.")
    except httpx.HTTPError:
        raise MailDeliveryError("Mail provider is unavailable.") from None


def send_token(user, purpose: str, db: Session, settings) -> None:
    if purpose != "reset":
        raise ValueError("Only password reset emails are supported.")
    raw = secrets.token_urlsafe(32)
    record = AccountToken(
        user_id=user.id, token_hash=digest(raw), purpose=purpose, expires_at=now() + timedelta(minutes=30)
    )
    link = settings.BASE_URL.rstrip("/") + "/auth/reset/" + raw
    body = "Open this link within 30 minutes. If you did not request it, ignore this email.\n\n" + link
    try:
        db.add(record)
        db.flush()
        _deliver(user.email, "Xelo: reset your password", body, settings)
        db.commit()
    except Exception:
        db.rollback()
        raise
