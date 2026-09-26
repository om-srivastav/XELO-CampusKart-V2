from conftest import image_file, listing, login
from support import Client


def test_confirmed_sale_cannot_change_buyer(client, people, app, db):
    from app.models import Conversation, Product

    login(client)
    listing(client)
    p = db.query(Product).one()
    p.status = "sold"
    p.buyer_id = 2
    p.sale_confirmed = True
    db.add(Conversation(product_id=1, buyer_id=4, seller_id=1))
    db.commit()
    response = client.post("/market/1/status", data={"status": "sold", "buyer_id": "4"})
    assert response.status_code in (400, 409)
    db.expire_all()
    assert db.query(Product).one().buyer_id == 2


def test_private_profile_hides_listing_contacts(client, people, app, db):
    from app.models import AnalyticsEvent

    login(client)
    listing(client)
    u = people["seller"]
    u.profile_visible = False
    u.show_phone = True
    u.show_whatsapp = True
    u.phone = "919876543210"
    u.whatsapp = u.phone
    db.commit()
    buyer = Client(app)
    login(buyer, "buyer")
    response = buyer.get("/market/1")
    assert b"9876543210" not in response.content
    assert b"Chat on WhatsApp" not in response.content
    assert buyer.post("/market/1/whatsapp").status_code == 404
    assert db.query(AnalyticsEvent).filter_by(kind="whatsapp").count() == 0


def test_password_change_invalidates_reset_links(client, people, db):
    from datetime import timedelta

    from app.models import AccountToken
    from app.models.identity import now
    from app.security import digest

    db.add(
        AccountToken(
            user_id=1,
            token_hash=digest("old-link"),
            purpose="reset",
            expires_at=now() + timedelta(minutes=20),
        )
    )
    db.commit()
    login(client)
    client.post(
        "/auth/password",
        data={
            "current": "Correct-horse-123",
            "password": "New-owner-password-123",
            "confirm": "New-owner-password-123",
        },
    )
    assert client.get("/auth/reset/old-link").status_code == 400


def test_reset_invalidates_other_reset_links(client, people, db):
    from datetime import timedelta

    from app.models import AccountToken
    from app.models.identity import now
    from app.security import digest

    for raw in ("link-one", "link-two"):
        db.add(
            AccountToken(
                user_id=1, token_hash=digest(raw), purpose="reset", expires_at=now() + timedelta(minutes=20)
            )
        )
    db.commit()
    assert (
        client.post(
            "/auth/reset/link-one",
            data={"password": "New-owner-password-123", "confirm": "New-owner-password-123"},
        ).status_code
        == 302
    )
    assert client.get("/auth/reset/link-two").status_code == 400


def test_partial_image_write_is_cleaned(client, people, app, monkeypatch, db):
    from pathlib import Path

    from app.models import Product
    from app.services.storage import LocalImageStorage

    login(client)
    listing(client)
    root = Path(app.state.settings.UPLOAD_FOLDER)
    before = {p.name for p in root.iterdir()}
    original = LocalImageStorage.put

    def disk_failure(self, key, data):
        if key.startswith("thumb-"):
            raise OSError("simulated disk write failure")
        return original(self, key, data)

    monkeypatch.setattr(LocalImageStorage, "put", disk_failure)
    response = client.post(
        "/market/1/edit",
        data={
            "title": "Edited book",
            "description": "Long enough valid description",
            "category_id": "1",
            "price": "450",
            "condition": "good",
            "city": "Kanpur",
            "images": image_file(),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code in (400, 503)
    assert {p.name for p in root.iterdir()} == before
    assert len(db.query(Product).one().images) == 1
