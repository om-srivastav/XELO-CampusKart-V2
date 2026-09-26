import os
import secrets
from pathlib import Path


def development_secret(instance):
    folder = Path(instance)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ".development-secret"
    try:
        with path.open("x", encoding="ascii") as handle:
            handle.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    return path.read_text(encoding="ascii").strip()


def configuration(instance):
    url = os.getenv("DATABASE_URL", "sqlite:///" + str(Path(instance) / "xelo.db"))
    if url.startswith(("postgres://", "postgresql://")):
        url = "postgresql+psycopg://" + url.split("://", 1)[1]
    prod = os.getenv("APP_ENV") == "production"
    return dict(
        APP_ENV=os.getenv("APP_ENV", "development"),
        SECRET_KEY=os.getenv("SECRET_KEY") or ("" if prod else development_secret(instance)),
        SQLALCHEMY_DATABASE_URI=url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=prod,
        MAX_CONTENT_LENGTH=32 * 1024 * 1024,
        MAX_FORM_MEMORY_SIZE=256 * 1024,
        UPLOAD_FOLDER=os.getenv("UPLOAD_FOLDER", str(Path(instance).parent / "uploads")),
        RATELIMIT_STORAGE_URI=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
        BASE_URL=os.getenv("BASE_URL", "http://127.0.0.1:5000"),
        TRUSTED_HOSTS=os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1").split(","),
        MAIL_MODE=os.getenv("MAIL_MODE", "file" if not prod else "smtp"),
        SMTP_HOST=os.getenv("SMTP_HOST", ""),
        SMTP_PORT=int(os.getenv("SMTP_PORT", "587")),
        SMTP_USER=os.getenv("SMTP_USER", ""),
        SMTP_PASSWORD=os.getenv("SMTP_PASSWORD", ""),
        SMTP_FROM=os.getenv("SMTP_FROM", ""),
        SMTP_TLS=os.getenv("SMTP_TLS", "true") == "true",
        TRUST_PROXY=os.getenv("TRUST_PROXY", "false") == "true",
        SESSION_HOURS=168,
        SESSION_IDLE_HOURS=24,
    )


def validate_production(config):
    if config["APP_ENV"] != "production":
        return
    required = ["SECRET_KEY", "SMTP_HOST", "SMTP_FROM", "TRUSTED_HOSTS"]
    if any(not config.get(k) for k in required) or len(config["SECRET_KEY"]) < 32:
        raise ValueError("Production requires a strong secret, trusted hosts and SMTP settings.")
    if not config["SQLALCHEMY_DATABASE_URI"].startswith("postgresql"):
        raise ValueError("Production requires PostgreSQL.")
    if not config["BASE_URL"].startswith("https://") or config["MAIL_MODE"] != "smtp":
        raise ValueError("Production requires HTTPS and SMTP delivery.")
    if not config["RATELIMIT_STORAGE_URI"].startswith(("redis://", "rediss://")):
        raise ValueError("Production requires shared Redis rate limiting.")
    config["SESSION_COOKIE_SECURE"] = True
    config["DEBUG"] = False
