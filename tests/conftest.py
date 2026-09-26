import os

import pytest


@pytest.fixture
def app(tmp_path):
    from app import create_app
    from app.extensions import db

    test_url = os.getenv("TEST_DATABASE_URL")
    if test_url:
        from sqlalchemy.engine import make_url

        if make_url(test_url).database != "xelo_test":
            raise RuntimeError("TEST_DATABASE_URL must point to the disposable xelo_test database.")
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "tests-only-secret",
            "SQLALCHEMY_DATABASE_URI": os.getenv("TEST_DATABASE_URL", "sqlite://"),
            "WTF_CSRF_ENABLED": False,
            "RATELIMIT_ENABLED": False,
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "MAIL_FOLDER": str(tmp_path / "mail"),
            "MAIL_MODE": "file",
        }
    )
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def people(app):
    from werkzeug.security import generate_password_hash

    from app.extensions import db
    from app.models import Campus, Category, User

    campus = Campus(name="North Campus", city="Kanpur", domains="north.edu")
    other = Campus(name="South Campus", city="Delhi", domains="south.edu")
    category = Category(name="Books", slug="books")
    db.session.add_all([campus, other, category])
    db.session.flush()
    result = {}
    for name, college, admin in [
        ("seller", campus, False),
        ("buyer", campus, False),
        ("outsider", other, False),
        ("admin", campus, True),
    ]:
        user = User(
            username=name,
            email=name + "@" + college.domains,
            display_name=name.title(),
            campus_id=college.id,
            verified=True,
            is_admin=admin,
            password_hash=generate_password_hash("Correct-horse-123"),
        )
        db.session.add(user)
        result[name] = user
    db.session.commit()
    result["category"] = category
    result["campus"] = campus
    return result


def login(client, name="seller"):
    domain = "south.edu" if name == "outsider" else "north.edu"
    return client.post("/auth/login", data={"email": name + "@" + domain, "password": "Correct-horse-123"})


def image_file():
    from io import BytesIO

    from PIL import Image

    stream = BytesIO()
    Image.new("RGB", (64, 64), "#aacc99").save(stream, "PNG")
    stream.seek(0)
    return stream, "book.png"


def listing(client, **changes):
    data = dict(
        title="Calculus textbook",
        description="Clean textbook with useful worked examples.",
        category_id="1",
        price="450.00",
        condition="good",
        brand="Pearson",
        city="Kanpur",
        status="available",
        images=image_file(),
    )
    data.update(changes)
    return client.post("/market/new", data=data, content_type="multipart/form-data")
