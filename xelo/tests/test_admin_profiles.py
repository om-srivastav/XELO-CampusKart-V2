from pathlib import Path

from conftest import image_file, login


def test_profile_images_edit_remove_and_privacy(client, people, app):
    from app.models import User

    login(client)
    data = {
        "display_name": "Updated Seller",
        "department": "Engineering",
        "year": "3",
        "city": "Kanpur",
        "bio": "Campus member",
        "phone": "+91 98765 43210",
        "whatsapp": "+91 98765 43210",
        "show_whatsapp": "on",
        "profile_visible": "on",
        "contact_visible": "on",
        "avatar": image_file(),
        "cover": image_file(),
    }
    assert client.post("/profile/edit", data=data, content_type="multipart/form-data").status_code == 302
    user = User.query.filter_by(username="seller").one()
    assert user.phone == "919876543210" and user.avatar and user.cover
    avatar = user.avatar
    assert client.get("/profile/1/image/avatar").mimetype == "image/webp"
    assert client.get("/profile/1/image/cover").status_code == 200
    assert (
        client.post(
            "/profile/edit",
            data={
                "display_name": "Updated Seller",
                "remove_avatar": "on",
                "remove_cover": "on",
                "profile_visible": "on",
                "contact_visible": "on",
            },
        ).status_code
        == 302
    )
    assert client.get("/profile/1/image/avatar").status_code == 404
    assert not (Path(app.config["UPLOAD_FOLDER"]) / avatar).exists()


def test_admin_category_and_campus_management(client, people):
    from app.models import AdminAction, Campus, Category

    login(client, "admin")
    assert (
        client.post(
            "/admin/category",
            data={
                "name": "Electronics",
                "description": "Devices",
                "icon": "E",
                "position": "1",
                "active": "on",
                "reason": "Add supported category",
            },
        ).status_code
        == 302
    )
    c = Category.query.filter_by(name="Electronics").one()
    assert c.active
    assert (
        client.post(
            "/admin/category", data={"id": str(c.id), "name": "Electronics", "reason": "Deactivate category"}
        ).status_code
        == 302
    )
    assert not Category.query.filter_by(id=c.id).one().active
    assert (
        client.post(
            "/admin/campus",
            data={
                "name": "New College",
                "city": "Mumbai",
                "domains": "college.edu",
                "active": "on",
                "reason": "Onboard college",
            },
        ).status_code
        == 302
    )
    assert Campus.query.filter_by(name="New College").one().domains == "college.edu"
    assert AdminAction.query.count() == 3


def test_admin_report_resolution_review_moderation(client, people):
    from app.extensions import db
    from app.models import Notification, Product, Report, Review

    login(client, "admin")
    people["buyer"].verified = False
    p = Product(
        seller_id=1,
        campus_id=1,
        category_id=1,
        title="Confirmed book",
        description="Book description",
        price=10,
        status="sold",
    )
    db.session.add(p)
    db.session.flush()
    db.session.add(Review(product_id=p.id, reviewer_id=2, seller_id=1, rating=4, body="Good exchange"))
    db.session.add(
        Report(reporter_id=2, kind="product", target_id=p.id, reason="other", description="Please review")
    )
    db.session.commit()
    for action in ["resolve_report", "hide_review"]:
        target = "1"
        assert (
            client.post(
                "/admin/action",
                data={"action": action, "target": target, "reason": "Reviewed by campus moderator"},
            ).status_code
            == 302
        )
    assert Report.query.one().status == "resolved"
    assert Review.query.one().hidden
    assert Notification.query.count() == 2


def test_cli_admin_and_maintenance(app, people):
    from datetime import timedelta

    from app.extensions import db
    from app.models import SearchHistory, User
    from app.models.identity import now

    runner = app.test_cli_runner()
    result = runner.invoke(
        args=[
            "create-admin",
            "--email",
            "second@north.edu",
            "--username",
            "secondadmin",
            "--campus-id",
            "1",
            "--password",
            "Extra-admin-password-123",
        ]
    )
    assert result.exit_code == 0, result.output
    assert User.query.filter_by(username="secondadmin").one().is_admin
    db.session.add(SearchHistory(user_id=1, term="old query", created_at=now() - timedelta(days=40)))
    db.session.commit()
    result = runner.invoke(args=["maintenance"])
    assert result.exit_code == 0, result.output
    assert SearchHistory.query.count() == 0


def test_notifications_counts_mark_read_and_search_history(client, people):
    from app.extensions import db
    from app.models import Notification, SearchHistory

    login(client)
    db.session.add(Notification(user_id=1, kind="system", title="Account update", link="/profile/edit"))
    db.session.add(SearchHistory(user_id=1, term="book"))
    db.session.commit()
    assert client.get("/notifications/counts").json == {"notifications": 1, "messages": 0}
    assert client.post("/notifications/read-all").status_code == 302
    assert client.get("/notifications/counts").json["notifications"] == 0
    assert b"book" in client.get("/history").data
    assert client.post("/history/clear").status_code == 302
    assert SearchHistory.query.count() == 0
