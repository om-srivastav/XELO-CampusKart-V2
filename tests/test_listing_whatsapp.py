from conftest import listing, login
from support import Client

from app.models import AnalyticsEvent, Product


def test_listing_collects_whatsapp_and_buyer_can_contact(client, people, app, db):
    login(client)
    assert b'name="whatsapp"' in client.get("/market/new").content
    assert listing(client, whatsapp="+91 98765 43210", whatsapp_contact="on").status_code == 302
    assert people["seller"].whatsapp == "919876543210"
    buyer = Client(app)
    login(buyer, "buyer")
    pid = db.query(Product).one().id
    assert b"Message on WhatsApp" in buyer.get(f"/market/{pid}").content
    result = buyer.post(f"/market/{pid}/whatsapp")
    assert result.status_code in (302, 303)
    assert "wa.me/919876543210" in result.headers["location"]
    assert "text=" in result.headers["location"]
    assert db.query(AnalyticsEvent).filter_by(kind="whatsapp").count() == 1


def test_listing_whatsapp_validation_and_opt_out(client, people, app, db):
    login(client)
    assert listing(client, whatsapp="bad-number", whatsapp_contact="on").status_code == 400
    assert db.query(Product).count() == 0
    assert listing(client, whatsapp="9876543210").status_code == 302
    assert not people["seller"].show_whatsapp
    buyer = Client(app)
    login(buyer, "buyer")
    assert buyer.post("/market/1/whatsapp").status_code == 404
