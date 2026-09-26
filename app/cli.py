import re
from datetime import timedelta
from pathlib import Path

import click
from flask import current_app
from werkzeug.security import generate_password_hash

from .extensions import db
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
from .services.validation import slug


def register(app):
    @app.cli.command("seed-categories")
    def categories():
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
            if not Category.query.filter_by(slug=slug(name)).first():
                db.session.add(Category(name=name, slug=slug(name), position=i))
        db.session.commit()
        click.echo("Categories initialized; no users or listings created.")

    @app.cli.command("campus-add")
    @click.argument("name")
    @click.argument("city")
    @click.option("--domains", default="")
    def campus_add(name, city, domains):
        if Campus.query.filter_by(name=name).first():
            raise click.ClickException("Campus already exists.")
        values = [v.strip().lower() for v in domains.split(",") if v.strip()]
        if any(not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,63}", v) for v in values):
            raise click.ClickException("Invalid email domain.")
        c = Campus(name=name, city=city, domains=",".join(values))
        db.session.add(c)
        db.session.commit()
        click.echo(f"Campus {c.id}: {c.name}")

    @app.cli.command("create-admin")
    @click.option("--email", prompt=True)
    @click.option("--username", prompt=True)
    @click.option("--campus-id", type=int, prompt=True)
    @click.password_option()
    def admin(email, username, campus_id, password):
        if len(password) < 12 or len(password) > 128:
            raise click.ClickException("Use a password of 12–128 characters.")
        if not db.session.get(Campus, campus_id):
            raise click.ClickException("Unknown campus.")
        from email_validator import EmailNotValidError, validate_email

        try:
            email = validate_email(email, check_deliverability=False).normalized.lower()
        except EmailNotValidError:
            raise click.ClickException("Invalid email.")
        if not re.fullmatch(r"[a-z0-9_]{3,40}", username.lower()):
            raise click.ClickException("Invalid username.")
        if User.query.filter((User.email == email) | (User.username == username.lower())).first():
            raise click.ClickException("Account already exists.")
        db.session.add(
            User(
                email=email,
                username=username.lower(),
                display_name=username,
                campus_id=campus_id,
                password_hash=generate_password_hash(password),
                is_admin=True,
                verified=True,
            )
        )
        db.session.commit()
        click.echo("Administrator created.")

    @app.cli.command("maintenance")
    def maintenance():
        cutoff = now() - timedelta(days=30)
        SearchHistory.query.filter(SearchHistory.created_at < cutoff).delete()
        LoginHistory.query.filter(LoginHistory.created_at < now() - timedelta(days=90)).delete()
        AccountToken.query.filter(AccountToken.expires_at < cutoff).delete()
        UserSession.query.filter(UserSession.expires_at < cutoff).delete()
        db.session.commit()
        referenced = {key for (key,) in db.session.query(ProductImage.key)}
        for avatar, cover in db.session.query(User.avatar, User.cover):
            referenced.update(k for k in (avatar, cover) if k)
        folder = Path(current_app.config["UPLOAD_FOLDER"])
        count = 0
        if folder.exists():
            for path in folder.glob("*.webp"):
                if (
                    path.name.removeprefix("thumb-") not in referenced
                    and path.stat().st_mtime < (now() - timedelta(days=1)).timestamp()
                ):
                    path.unlink()
                    count += 1
        mail = Path(current_app.config.get("MAIL_FOLDER", Path(current_app.instance_path) / "mail"))
        if mail.exists():
            for path in mail.glob("*.eml"):
                if path.stat().st_mtime < cutoff.timestamp():
                    path.unlink()
        click.echo(f"Retention applied; {count} orphan images removed.")

    @app.cli.command("seed-demo")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def demo(password):
        if current_app.config["APP_ENV"] == "production":
            raise click.ClickException("Demo data is disabled in production.")
        if len(password) < 12:
            raise click.ClickException("Use at least 12 characters.")
        if User.query.filter_by(username="demo_student").first():
            raise click.ClickException("Demo account already exists.")
        c = Campus.query.filter_by(name="DEMO Campus").first()
        if not c:
            c = Campus(name="DEMO Campus", city="Demo City", domains="demo.invalid")
            db.session.add(c)
            db.session.flush()
        db.session.add(
            User(
                username="demo_student",
                email="student@demo.invalid",
                display_name="DEMO Student",
                campus_id=c.id,
                verified=True,
                password_hash=generate_password_hash(password),
            )
        )
        db.session.commit()
        click.echo("Created student@demo.invalid in DEMO Campus. No fabricated listings or statistics.")
