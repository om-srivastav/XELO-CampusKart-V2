from conftest import listing, login


def test_view_does_not_change_listing_edit_timestamp(client, people, app):
    from app.models import Product

    login(client)
    listing(client)
    before = Product.query.one().updated_at
    buyer = app.test_client()
    login(buyer, "buyer")
    buyer.get("/market/1")
    assert Product.query.one().views == 1
    assert Product.query.one().updated_at == before
