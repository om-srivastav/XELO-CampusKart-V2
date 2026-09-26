from conftest import login


def test_signup_allows_immediate_access(client, people, app):
    from pathlib import Path

    from app.models import User

    response = client.post(
        "/auth/signup",
        data={
            "username": "newstudent",
            "display_name": "New Student",
            "email": "new@north.edu",
            "password": "Strong-password-123",
            "confirm": "Strong-password-123",
            "campus_id": "1",
        },
    )
    assert response.status_code == 302
    user = User.query.filter_by(username="newstudent").one()
    assert not user.verified and user.password_hash != "Strong-password-123"
    assert not list(Path(app.config["MAIL_FOLDER"]).glob("*.eml"))
    client.post("/auth/login", data={"email": "new@north.edu", "password": "Strong-password-123"})
    assert client.get("/profile/1").status_code == 200


def test_login_logout_and_safe_redirect(client, people):
    assert login(client).status_code == 302
    assert client.get("/profile/edit").status_code == 200
    assert client.post("/auth/logout").status_code == 302
    assert client.get("/profile/edit").status_code == 302
    response = client.post(
        "/auth/login?next=https://evil.example",
        data={"email": "seller@north.edu", "password": "Correct-horse-123"},
    )
    assert response.location.startswith("/")


def test_password_change_revokes_other_sessions(client, app, people):
    other = app.test_client()
    login(client)
    login(other)
    response = client.post(
        "/auth/password",
        data={
            "current": "Correct-horse-123",
            "password": "New-correct-horse-123",
            "confirm": "New-correct-horse-123",
        },
    )
    assert response.status_code == 302
    assert other.get("/profile/edit").status_code == 302


def test_hidden_contact_never_rendered(client, people):
    from app.extensions import db

    user = people["seller"]
    user.phone = "919876543210"
    user.whatsapp = "919876543210"
    db.session.commit()
    login(client, "buyer")
    response = client.get("/profile/1")
    assert response.status_code == 200
    assert b"9876543210" not in response.data


def test_csrf_rejects_mutations(app, people):
    app.config["WTF_CSRF_ENABLED"] = True
    assert (
        app.test_client()
        .post("/auth/login", data={"email": "seller@north.edu", "password": "Correct-horse-123"})
        .status_code
        == 400
    )
