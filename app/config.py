"""Environment-driven settings shared by ASGI, CLI and Alembic."""

import secrets
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=True)

    APP_ENV: Literal["development", "testing", "production"] = "development"
    INSTANCE_PATH: str = str(ROOT / "instance")
    SECRET_KEY: str = ""
    DATABASE_URL: str = ""
    REDIS_URL: str = "memory://"
    BASE_URL: str = "http://127.0.0.1:8000"
    TRUSTED_HOSTS: Annotated[list[str], NoDecode] = ["localhost", "127.0.0.1", "testserver"]
    TRUST_PROXY: bool = False
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    SESSION_COOKIE_SECURE: bool = False
    SESSION_HOURS: int = 168
    SESSION_IDLE_HOURS: int = 24
    MAX_CONTENT_LENGTH: int = 32 * 1024 * 1024
    MAX_FORM_MEMORY_SIZE: int = 256 * 1024
    UPLOAD_FOLDER: str = str(ROOT / "uploads")
    MAIL_FOLDER: str = ""
    MAIL_PROVIDER: Literal["file", "resend", "brevo"] = "file"
    MAIL_API_KEY: str = ""
    MAIL_FROM: str = ""
    DEBUG: bool = False
    TESTING: bool = False
    CSRF_ENABLED: bool = True
    RATELIMIT_ENABLED: bool = True

    @field_validator("TRUSTED_HOSTS", mode="before")
    @classmethod
    def parse_hosts(cls, value):
        if isinstance(value, str):
            return [host.strip() for host in value.split(",") if host.strip()]
        return value

    @model_validator(mode="after")
    def configure(self):
        if not self.DATABASE_URL:
            self.DATABASE_URL = "sqlite:///" + str(Path(self.INSTANCE_PATH) / "xelo.db")
        if self.DATABASE_URL.startswith(("postgres://", "postgresql://")):
            self.DATABASE_URL = "postgresql+psycopg://" + self.DATABASE_URL.split("://", 1)[1]
        if not self.MAIL_FOLDER:
            self.MAIL_FOLDER = str(Path(self.INSTANCE_PATH) / "mail")
        if self.APP_ENV == "production":
            if len(self.SECRET_KEY) < 32 or len(set(self.SECRET_KEY)) < 12:
                raise ValueError("Production requires a strong SECRET_KEY of at least 32 characters.")
            if not self.DATABASE_URL.startswith("postgresql+psycopg://"):
                raise ValueError("Production requires PostgreSQL with psycopg.")
            if not self.REDIS_URL.startswith(("redis://", "rediss://")):
                raise ValueError("Production requires shared Redis rate limiting.")
            base = urlsplit(self.BASE_URL)
            if (
                base.scheme != "https"
                or not base.hostname
                or not self.TRUSTED_HOSTS
                or "*" in self.TRUSTED_HOSTS
            ):
                raise ValueError("Production requires HTTPS and explicit trusted hosts.")
            if (
                self.MAIL_PROVIDER not in ("resend", "brevo")
                or not self.MAIL_API_KEY
                or "@" not in self.MAIL_FROM
            ):
                raise ValueError(
                    "Production requires Resend or Brevo API delivery and MAIL_API_KEY/MAIL_FROM."
                )
            self.SESSION_COOKIE_SECURE = True
            self.DEBUG = False
        elif not self.SECRET_KEY:
            self.SECRET_KEY = development_secret(self.INSTANCE_PATH)
        return self
