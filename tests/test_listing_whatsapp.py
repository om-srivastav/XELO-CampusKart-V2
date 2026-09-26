from conftest import listing, login

from app.models import AnalyticsEvent, Product


def test_listing_collects_whatsapp_and_buyer_can_contact(client, people, app):
    login(client)
    assert b'name="whatsapp"' in client.get("/market/new").data
    assert listing(client, whatsapp="+91 98765 43210", whatsapp_contact="on").status_code == 302
    assert people["seller"].whatsapp == "919876543210"
    buyer = app.test_client()
    login(buyer, "buyer")
    pid = Product.query.one().id
    assert b"Message on WhatsApp" in buyer.get(f"/market/{pid}").data
    result = buyer.post(f"/market/{pid}/whatsapp")
    assert result.status_code in (302, 303)
    assert "wa.me/919876543210" in result.location
    assert "text=" in result.location
    assert AnalyticsEvent.query.filter_by(kind="whatsapp").count() == 1


def test_listing_whatsapp_validation_and_opt_out(client, people, app):
    login(client)
    assert listing(client, whatsapp="bad-number", whatsapp_contact="on").status_code == 400
    assert Product.query.count() == 0
    assert listing(client, whatsapp="9876543210").status_code == 302
    assert not people["seller"].show_whatsapp
    buyer = app.test_client()
    login(buyer, "buyer")
    assert buyer.post("/market/1/whatsapp").status_code == 404
