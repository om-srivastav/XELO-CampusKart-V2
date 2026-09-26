from conftest import listing, login
from support import Client


def test_view_does_not_change_listing_edit_timestamp(client, people, app, db):
    from app.models import Product

    login(client)
    listing(client)
    before = db.query(Product).one().updated_at
    buyer = Client(app)
    login(buyer, "buyer")
    buyer.get("/market/1")
    assert db.query(Product).one().views == 1
    assert db.query(Product).one().updated_at == before
