from conftest import listing, login

from app.models import AnalyticsEvent


def test_owner_can_test_whatsapp_without_inflating_analytics(client, people):
    login(client)
    listing(client, whatsapp="9876543210", whatsapp_contact="on")
    assert b"Message on WhatsApp" in client.get("/market/1").data
    result = client.post("/market/1/whatsapp")
    assert result.status_code == 302
    assert "wa.me/919876543210" in result.location
    assert AnalyticsEvent.query.filter_by(kind="whatsapp").count() == 0


def test_owner_gets_setup_link_when_contact_is_disabled(client, people):
    login(client)
    listing(client)
    page = client.get("/market/1")
    assert b"Set up WhatsApp" in page.data
    assert b'/market/1/edit' in page.data
