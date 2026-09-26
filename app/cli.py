import re
from datetime import timedelta
from functools import wraps
from pathlib import Path

import click

from .config import Settings
from .database import make_engine, make_session_factory
from .models import (
    AccountToken,
    Campus,
    Category,
    LoginHistory,
    ProductImage,
    SearchHistory,
    User,
    UserSession,
)
from .models.identity import now
from .security import hash_password


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "item"


def build_cli(settings, factory):
    @click.group()
    def cli():
        """Xelo account, catalog and retention management."""

    def with_session(callback):
        @wraps(callback)
        def wrapped(*args, **kwargs):
            with factory() as session:
                try:
                    return callback(session, *args, **kwargs)
                except Exception:
                    session.rollback()
                    raise

        return wrapped

    @cli.command("seed-categories")
    @with_session
    def categories(session):
        names = [
            "Electronics",
            "Books",
            "Notes",
            "Furniture",
            "Hostel Essentials",
            "Clothing",
            "Sports",
            "Bikes",
            "Accessories",
            "Gaming",
            "Study Materials",
            "Services",
            "Other",
        ]
        for i, name in enumerate(names):
            if not session.query(Category).filter_by(slug=slug(name)).first():
                session.add(Category(name=name, slug=slug(name), position=i))
        session.commit()
        click.echo("Categories initialized; no users or listings created.")

    @cli.command("campus-add")
    @click.argument("name")
    @click.argument("city")
    @click.option("--domains", default="")
    @with_session
    def campus_add(session, name, city, domains):
        if session.query(Campus).filter_by(name=name).first():
            raise click.ClickException("Campus already exists.")
        values = [v.strip().lower() for v in domains.split(",") if v.strip()]
        if any(not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,63}", v) for v in values):
            raise click.ClickException("Invalid email domain.")
        c = Campus(name=name, city=city, domains=",".join(values))
        session.add(c)
        session.commit()
        click.echo(f"Campus {c.id}: {c.name}")

    @cli.command("create-admin")
    @click.option("--email", prompt=True)
    @click.option("--username", prompt=True)
    @click.option("--campus-id", type=int, prompt=True)
    @click.password_option()
    @with_session
    def admin(session, email, username, campus_id, password):
        if len(password) < 12 or len(password) > 128:
            raise click.ClickException("Use a password of 12-128 characters.")
        if not session.get(Campus, campus_id):
            raise click.ClickException("Unknown campus.")
        from email_validator import EmailNotValidError, validate_email

        try:
            email = validate_email(email, check_deliverability=False).normalized.lower()
        except EmailNotValidError:
            raise click.ClickException("Invalid email.")
        if not re.fullmatch(r"[a-z0-9_]{3,40}", username.lower()):
            raise click.ClickException("Invalid username.")
        if session.query(User).filter((User.email == email) | (User.username == username.lower())).first():
            raise click.ClickException("Account already exists.")
        session.add(
            User(
                email=email,
                username=username.lower(),
                display_name=username,
                campus_id=campus_id,
                password_hash=hash_password(password),
                is_admin=True,
                verified=True,
            )
        )
        session.commit()
        click.echo("Administrator created.")

    @cli.command("maintenance")
    @with_session
    def maintenance(session):
        cutoff = now() - timedelta(days=30)
        session.query(SearchHistory).filter(SearchHistory.created_at < cutoff).delete()
        session.query(LoginHistory).filter(LoginHistory.created_at < now() - timedelta(days=90)).delete()
        session.query(AccountToken).filter(AccountToken.expires_at < cutoff).delete()
        session.query(UserSession).filter(UserSession.expires_at < cutoff).delete()
        session.commit()
        referenced = {key for (key,) in session.query(ProductImage.key)}
        for avatar, cover in session.query(User.avatar, User.cover):
            referenced.update(k for k in (avatar, cover) if k)
        folder = Path(settings.UPLOAD_FOLDER)
        count = 0
        if folder.exists():
            for path in folder.glob("*.webp"):
                if (
                    path.name.removeprefix("thumb-") not in referenced
                    and path.stat().st_mtime < (now() - timedelta(days=1)).timestamp()
                ):
                    path.unlink()
                    count += 1
        mail = Path(settings.MAIL_FOLDER)
        if mail.exists():
            for path in mail.glob("*.eml"):
                if path.stat().st_mtime < cutoff.timestamp():
                    path.unlink()
        click.echo(f"Retention applied; {count} orphan images removed.")

    @cli.command("seed-demo")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    @with_session
    def demo(session, password):
        if settings.APP_ENV == "production":
            raise click.ClickException("Demo data is disabled in production.")
        if len(password) < 12:
            raise click.ClickException("Use at least 12 characters.")
        if session.query(User).filter_by(username="demo_student").first():
            raise click.ClickException("Demo account already exists.")
        c = session.query(Campus).filter_by(name="DEMO Campus").first()
        if not c:
            c = Campus(name="DEMO Campus", city="Demo City", domains="demo.invalid")
            session.add(c)
            session.flush()
        session.add(
            User(
                username="demo_student",
                email="student@demo.invalid",
                display_name="DEMO Student",
                campus_id=c.id,
                verified=True,
                password_hash=hash_password(password),
            )
        )
        session.commit()
        click.echo("Created student@demo.invalid in DEMO Campus. No fabricated listings or statistics.")

    return cli


def main():
    settings = Settings()
    Path(settings.INSTANCE_PATH).mkdir(parents=True, exist_ok=True)
    engine = make_engine(settings)
    try:
        build_cli(settings, make_session_factory(engine))()
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
