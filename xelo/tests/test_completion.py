from conftest import listing, login


def test_search_matches_campus_and_rejects_other_college(client, people):
    login(client)
    listing(client)
    assert b"Calculus textbook" in client.get("/market?q=North%20Campus").data
    assert b"Calculus textbook" not in client.get("/market?college=999").data


def test_profile_stats_are_real(client, people):
    from app.extensions import db
    from app.models import Product

    login(client)
    listing(client)
    Product.query.one().status = "sold"
    db.session.commit()
    response = client.get("/profile/1")
    assert b"1 sold" in response.data


def test_current_session_rotates_after_password_change(client, people):
    from app.models import UserSession

    login(client)
    before = UserSession.query.one().token_hash
    client.post(
        "/auth/password",
        data={
            "current": "Correct-horse-123",
            "password": "Different-password-123",
            "confirm": "Different-password-123",
        },
    )
    from app.extensions import db

    db.session.expire_all()
    assert UserSession.query.filter_by(revoked=False).one().token_hash != before


def test_all_other_sessions_can_be_revoked(client, people, app):
    other = app.test_client()
    login(client)
    login(other)
    assert client.post("/auth/sessions/revoke-others").status_code == 302
    assert client.get("/profile/edit").status_code == 200
    assert other.get("/profile/edit").status_code == 302
