from io import BytesIO

from conftest import image_file, listing, login
from support import Client


def test_publish_browse_edit_and_ownership(client, people, app, db):
    from app.models import Product

    login(client)
    response = listing(client)
    assert response.status_code == 302
    product = db.query(Product).one()
    assert product.price == 450 and len(product.images) == 1
    assert client.get("/market").status_code == 200
    assert client.get("/market/1").status_code == 200
    assert client.get("/market/1/edit").status_code == 200
    other = Client(app)
    login(other, "buyer")
    assert other.post("/market/1/status", data={"status": "sold"}).status_code == 403
    assert client.post("/market/1/status", data={"status": "reserved"}).status_code == 302
    assert db.query(Product).one().status == "reserved"
    assert client.post("/market/1/delete").status_code == 302
    assert other.get("/market/1").status_code == 404


def test_campus_isolation_including_images(client, people, app, db):
    from app.models import Product

    login(client)
    listing(client)
    key = db.query(Product).one().images[0].key
    outsider = Client(app)
    login(outsider, "outsider")
    assert outsider.get("/market/1").status_code == 404
    assert outsider.get("/market/image/" + key).status_code == 404
    assert b"Calculus textbook" not in outsider.get("/market").content
    assert outsider.get("/market/suggest?q=Calculus").json() == []


def test_search_filters_and_xss(client, people):
    login(client)
    listing(client)
    listing(client, title="Desk lamp", price="900")
    assert (
        b"Calculus textbook"
        in client.get("/market?q=Calculus&max_price=500&condition=good&category=1").content
    )
    assert b"Desk lamp" not in client.get("/market?max_price=500").content
    assert client.get("/market?min_price=NaN").status_code == 400
    assert client.get("/market?q=%27%20OR%201=1--").status_code == 200
    listing(client, title="<script>alert(1)</script>")
    assert b"<script>alert(1)</script>" not in client.get("/market/3").content
    assert b"&lt;script&gt;" in client.get("/market/3").content


def test_invalid_upload_and_price(client, people, db):
    from app.models import Product

    login(client)
    assert listing(client, images=(BytesIO(b"executable"), "bad.png")).status_code == 400
    assert listing(client, price="-1").status_code == 400
    assert db.query(Product).count() == 0


def test_multiple_image_reorder_and_remove(client, people, db):
    from app.models import Product

    login(client)
    assert listing(client, images=[image_file(), image_file()]).status_code == 302
    p = db.query(Product).one()
    ids = [i.id for i in p.images]
    response = client.post("/market/1/images", data={"order": ",".join(map(str, reversed(ids)))})
    assert response.status_code == 302
    db.expire_all()
    assert db.query(Product).one().images[0].id == ids[1]
    assert client.post("/market/1/images", data={"order": str(ids[0])}).status_code == 302
    db.expire_all()
    assert len(db.query(Product).one().images) == 1
