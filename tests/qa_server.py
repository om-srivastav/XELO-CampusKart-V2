"""Loopback-only browser QA with an isolated fixture database."""

import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
import uvicorn

from app.config import Settings
from app.database import Base
from app.main import build_app
from app.models import Campus, Category, User
from app.security import hash_password

app = build_app(
    Settings(
        APP_ENV="testing",
        DATABASE_URL="sqlite:///" + str(root / "instance/browser-qa.db"),
        SECRET_KEY="browser-qa-only-not-a-production-secret",
        UPLOAD_FOLDER=str(root / "instance/qa-uploads"),
        MAIL_FOLDER=str(root / "instance/qa-mail"),
        RATELIMIT_ENABLED=False,
        BASE_URL="http://127.0.0.1:5001",
    )
)
Base.metadata.create_all(app.state.engine)
with app.state.session_factory() as db:
    if not db.query(Campus).first():
        campus = Campus(name="QA Test Campus", city="Kanpur", domains="qa.test")
        db.add(campus)
        db.flush()
        db.add(Category(name="Books", slug="books"))
        for name, admin in [("seller", False), ("buyer", False), ("moderator", True)]:
            db.add(
                User(
                    username=name,
                    email=name + "@qa.test",
                    display_name="QA " + name.title(),
                    campus_id=campus.id,
                    is_admin=admin,
                    password_hash=hash_password("QA-browser-password-123"),
                )
            )
        db.commit()
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5001, proxy_headers=False)
