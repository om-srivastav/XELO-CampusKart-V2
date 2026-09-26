from conftest import listing, login
from support import Client


def setup_pair(client, people, app):
    login(client)
    listing(client)
    buyer = Client(app)
    login(buyer, "buyer")
    return buyer


def test_wishlist_and_deduplicated_views(client, people, app, db):
    from app.models import Product, Wishlist

    buyer = setup_pair(client, people, app)
    buyer.get("/market/1")
    buyer.get("/market/1")
    assert db.query(Product).one().views == 1
    assert buyer.post("/wishlist/1").status_code == 302
    assert db.query(Wishlist).count() == 1
    assert b"Calculus textbook" in buyer.get("/wishlist").content
    buyer.post("/wishlist/1")
    assert db.query(Wishlist).count() == 0


def test_whatsapp_privacy_and_tracking(client, people, app, db):
    from app.models import AnalyticsEvent

    buyer = setup_pair(client, people, app)
    people["seller"].whatsapp = "919876543210"
    db.commit()
    assert buyer.post("/market/1/whatsapp").status_code == 404
    assert b"9876543210" not in buyer.get("/market/1").content
    people["seller"].show_whatsapp = True
    db.commit()
    response = buyer.post("/market/1/whatsapp")
    assert response.status_code == 302
    assert response.headers["location"].startswith("https://wa.me/919876543210?text=")
    assert db.query(AnalyticsEvent).filter_by(kind="whatsapp").count() == 1


def test_private_conversation_and_notifications(client, people, app, db):
    from app.models import Message, Notification

    buyer = setup_pair(client, people, app)
    assert buyer.post("/messages/start/1").status_code == 302
    assert buyer.post("/messages/1", data={"body": "Is this available?"}).status_code == 302
    assert db.query(Message).one().sender_id == people["buyer"].id
    note = db.query(Notification).filter_by(user_id=1, kind="message").first()
    assert note is not None
    outsider = Client(app)
    login(outsider, "outsider")
    assert outsider.get("/messages/1").status_code == 404
    assert outsider.get("/messages/1/poll").status_code == 404
    assert outsider.post("/notifications/" + str(note.id) + "/read").status_code == 404
    assert client.get("/messages/1").status_code == 200
    assert client.post("/messages/1/read").status_code == 200
    assert db.query(Message).one().read_at is not None


def test_sale_review_rules_and_report_privacy(client, people, app, db):
    from app.models import Report, Review

    buyer = setup_pair(client, people, app)
    assert buyer.post("/reviews/1", data={"rating": 5, "body": "Great"}).status_code == 403
    buyer.post("/messages/start/1")
    buyer.post("/messages/1", data={"body": "I would like to buy it."})
    assert client.post("/market/1/status", data={"status": "sold", "buyer_id": "2"}).status_code == 302
    assert buyer.post("/reviews/1/confirm").status_code == 302
    assert buyer.post("/reviews/1", data={"rating": "5", "body": "Exactly as described."}).status_code == 302
    assert db.query(Review).one().seller_id == 1
    assert buyer.post("/reviews/1", data={"rating": "5", "body": "Again"}).status_code == 409
    assert (
        buyer.post(
            "/reports/new?kind=product&target=1", data={"reason": "scam", "description": "Please investigate"}
        ).status_code
        == 302
    )
    assert db.query(Report).one().reporter_id == 2
    assert b"Please investigate" not in client.get("/reports").content


def test_dashboard_real_metrics_and_admin_guards(client, people, app, db):
    from app.models import AdminAction, Product

    setup_pair(client, people, app)
    assert client.get("/dashboard").status_code == 200
    assert client.get("/admin").status_code == 403
    admin = Client(app)
    login(admin, "admin")
    assert admin.get("/admin").status_code == 200
    assert (
        admin.post(
            "/admin/action", data={"action": "remove_product", "target": "1", "reason": "Prohibited item"}
        ).status_code
        == 302
    )
    assert db.query(Product).one().status == "removed"
    assert db.query(AdminAction).count() == 1
    assert client.get("/market/1").status_code == 404
