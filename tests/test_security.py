import re
from datetime import timedelta
from io import BytesIO
from pathlib import Path

import pytest
from conftest import image_file, listing, login
from support import Client

from app.database import Base


def test_reset_link_single_use_and_session_revocation(app, client, people, db):
    from app.models import UserSession

    login(client)
    requester = Client(app)
    assert requester.post("/auth/forgot", data={"email": "seller@north.edu"}).status_code == 302
    mail = list(Path(app.state.settings.MAIL_FOLDER).glob("*.eml"))[0].read_text()
    path = re.search("http://127.0.0.1:8000(/auth/reset/[^\\s]+)", mail).group(1)
    assert requester.get(path).status_code == 200
    assert (
        requester.post(
            path, data={"password": "Replacement-secret-123", "confirm": "Replacement-secret-123"}
        ).status_code
        == 302
    )
    assert (
        requester.post(
            path, data={"password": "Replacement-secret-123", "confirm": "Replacement-secret-123"}
        ).status_code
        == 400
    )
    assert client.get("/profile/edit").status_code == 302
    assert db.query(UserSession).filter_by(revoked=False).count() == 0


def test_suspension_hides_all_listing_surfaces(client, people, app, db):
    from app.models import Product

    login(client)
    listing(client)
    key = db.query(Product).one().images[0].key
    admin = Client(app)
    login(admin, "admin")
    assert (
        admin.post(
            "/admin/action",
            data={"action": "suspend_user", "target": "1", "reason": "Confirmed policy violation"},
        ).status_code
        == 302
    )
    buyer = Client(app)
    login(buyer, "buyer")
    for url in ["/market/1", "/market/image/" + key, "/profile/1"]:
        assert buyer.get(url).status_code == 404
    assert buyer.post("/market/1/whatsapp").status_code == 404
    assert buyer.get("/market/suggest?q=Calculus").json() == []
    assert client.get("/profile/edit").status_code == 302


@pytest.mark.parametrize(
    "url",
    [
        "/market",
        "/wishlist",
        "/messages",
        "/notifications",
        "/dashboard",
        "/profile/1",
        "/reports",
        "/auth/sessions",
    ],
)
def test_member_pages_render(client, people, url):
    login(client)
    assert client.get(url).status_code == 200


@pytest.mark.parametrize(
    "section", ["users", "products", "categories", "campuses", "reports", "reviews", "conversations", "audit"]
)
def test_admin_sections_render(client, people, section):
    login(client, "admin")
    assert client.get("/admin?section=" + section).status_code == 200


def test_upload_failure_keeps_existing_images(client, people, db):
    from app.models import Product

    login(client)
    listing(client)
    assert (
        client.post(
            "/market/1/edit",
            data={
                "title": "New name",
                "description": "Updated description is long enough",
                "category_id": "1",
                "price": "12",
                "condition": "good",
                "city": "Kanpur",
                "images": [(BytesIO(b"bad"), "bad.png"), image_file()],
            },
            content_type="multipart/form-data",
        ).status_code
        == 400
    )
    assert db.query(Product).one().title == "Calculus textbook"
    assert len(db.query(Product).one().images) == 1


def test_filter_sort_pagination(client, people, db):
    from app.models import Product

    login(client)
    for i in range(15):
        db.add(
            Product(
                seller_id=1,
                campus_id=1,
                category_id=1,
                title=f"Item {i:02}",
                description="Sample item description",
                price=i,
                status="available",
                city="Kanpur",
            )
        )
    db.commit()
    response = client.get("/market?sort=price_low")
    assert response.content.index(b"Item 00") < response.content.index(b"Item 11")
    assert b"Item 12" not in response.content
    response = client.get("/market?sort=price_low&page=2")
    assert b"Item 12" in response.content and b"Item 00" not in response.content
    assert b"sort=price_low" in response.content


def test_csrf_valid_then_missing(client, people, app):
    app.state.settings.CSRF_ENABLED = True
    page = client.get("/auth/login")
    token = re.search(b'name="csrf_token" value="([^"]+)', page.content).group(1).decode()
    assert (
        client.post(
            "/auth/login",
            data={"csrf_token": token, "email": "seller@north.edu", "password": "Correct-horse-123"},
        ).status_code
        == 302
    )
    assert client.post("/auth/logout").status_code == 400


def test_expired_session_rejected(client, people, db):
    from app.models import UserSession
    from app.models.identity import now

    login(client)
    db.query(UserSession).one().expires_at = now() - timedelta(seconds=1)
    db.commit()
    assert client.get("/dashboard").status_code == 302


def test_phone_normalization_and_rejection(app):
    from fastapi import HTTPException as BadRequest

    from app.services.validation import phone

    assert phone("+91 (98765) 43210") == "919876543210"
    assert phone("9876543210") == "919876543210"
    with pytest.raises(BadRequest):
        phone("abc9876543210")


def test_private_profile_rejects_direct_url(client, people, db):
    people["seller"].profile_visible = False
    db.commit()
    login(client, "buyer")
    assert client.get("/profile/1").status_code == 404


def test_untrusted_host_denied(client):
    assert client.get("/", headers={"Host": "evil.example"}).status_code == 400


def test_postgres_schema_compiles(app):
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable

    for table in Base.metadata.sorted_tables:
        assert str(CreateTable(table).compile(dialect=postgresql.dialect()))
