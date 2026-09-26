from conftest import listing, login
from support import Client


def test_search_matches_campus_and_rejects_other_college(client, people):
    login(client)
    listing(client)
    assert b"Calculus textbook" in client.get("/market?q=North%20Campus").content
    assert b"Calculus textbook" not in client.get("/market?college=999").content


def test_profile_stats_are_real(client, people, db):
    from app.models import Product

    login(client)
    listing(client)
    db.query(Product).one().status = "sold"
    db.commit()
    response = client.get("/profile/1")
    assert b"1 sold" in response.content


def test_current_session_rotates_after_password_change(client, people, db):
    from app.models import UserSession

    login(client)
    before = db.query(UserSession).one().token_hash
    client.post(
        "/auth/password",
        data={
            "current": "Correct-horse-123",
            "password": "Different-password-123",
            "confirm": "Different-password-123",
        },
    )
    db.expire_all()
    assert db.query(UserSession).filter_by(revoked=False).one().token_hash != before


def test_all_other_sessions_can_be_revoked(client, people, app):
    other = Client(app)
    login(client)
    login(other)
    assert client.post("/auth/sessions/revoke-others").status_code == 302
    assert client.get("/profile/edit").status_code == 200
    assert other.get("/profile/edit").status_code == 302
