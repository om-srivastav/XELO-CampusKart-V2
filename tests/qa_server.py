import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from waitress import serve
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import Campus, Category, User

(root / "instance").mkdir(exist_ok=True)
app = create_app(
    {
        "APP_ENV": "testing",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(root / "instance/browser-qa.db"),
        "SECRET_KEY": "browser-qa-only-not-a-production-secret",
        "UPLOAD_FOLDER": str(root / "instance/qa-uploads"),
        "MAIL_FOLDER": str(root / "instance/qa-mail"),
        "RATELIMIT_ENABLED": False,
    }
)
with app.app_context():
    db.create_all()
    if not Campus.query.first():
        c = Campus(name="QA Test Campus", city="Kanpur", domains="qa.test")
        db.session.add(c)
        db.session.flush()
        db.session.add(Category(name="Books", slug="books"))
        for name, admin in [("seller", False), ("buyer", False), ("moderator", True)]:
            db.session.add(
                User(
                    username=name,
                    email=name + "@qa.test",
                    display_name="QA " + name.title(),
                    campus_id=c.id,
                    verified=True,
                    is_admin=admin,
                    password_hash=generate_password_hash("QA-browser-password-123"),
                )
            )
        db.session.commit()
serve(app, host="127.0.0.1", port=5001)
