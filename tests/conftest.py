import os

import pytest
from support import Client

from app.config import Settings
from app.database import Base
from app.main import build_app


@pytest.fixture
def app(tmp_path):
    test_url = os.getenv("TEST_DATABASE_URL")
    if test_url:
        from sqlalchemy.engine import make_url

        if make_url(test_url).database != "xelo_test":
            raise RuntimeError("TEST_DATABASE_URL must point to the disposable xelo_test database.")
    application = build_app(
        Settings(
            APP_ENV="testing",
            TESTING=True,
            SECRET_KEY="tests-only-secret",
            DATABASE_URL=test_url or "sqlite://",
            TRUSTED_HOSTS=["localhost", "127.0.0.1", "testserver"],
            CSRF_ENABLED=False,
            RATELIMIT_ENABLED=False,
            UPLOAD_FOLDER=str(tmp_path / "uploads"),
            MAIL_FOLDER=str(tmp_path / "mail"),
            MAIL_PROVIDER="file",
            INSTANCE_PATH=str(tmp_path),
            BASE_URL="http://127.0.0.1:8000",
        )
    )
    Base.metadata.create_all(application.state.engine)
    try:
        yield application
    finally:
        Base.metadata.drop_all(application.state.engine)
        application.state.engine.dispose()


@pytest.fixture
def db(app):
    with app.state.session_factory() as session:
        app.state.test_session = session
        yield session
        session.rollback()
        del app.state.test_session


@pytest.fixture
def client(app, db):
    with Client(app) as client:
        yield client


@pytest.fixture
def people(app, db):
    from app.models import Campus, Category, User
    from app.security import hash_password

    campus = Campus(name="North Campus", city="Kanpur", domains="north.edu")
    other = Campus(name="South Campus", city="Delhi", domains="south.edu")
    category = Category(name="Books", slug="books")
    db.add_all([campus, other, category])
    db.flush()
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
            password_hash=hash_password("Correct-horse-123"),
        )
        db.add(user)
        result[name] = user
    db.commit()
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
