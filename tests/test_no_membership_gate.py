from conftest import login

from app.models import AccountToken


def test_existing_pending_member_can_use_marketplace(client, people, db):
    people["seller"].verified = False
    db.commit()
    login(client)
    for path in ["/market", "/market/new", "/dashboard", "/messages"]:
        assert client.get(path).status_code == 200
    page = client.get("/profile/edit")
    assert b"Membership pending" not in page.content
    assert b"Resend verification" not in page.content
    assert b"Verified member" not in page.content
    assert b"Fresh on campus" in client.get("/").content


def test_retired_verification_endpoints(client, people, db):
    login(client)
    assert client.get("/auth/verify/old-token").status_code == 404
    assert client.post("/auth/resend").status_code == 404
    assert db.query(AccountToken).filter_by(purpose="verify").count() == 0


def test_inactive_campus_still_blocked(client, people, db):
    people["campus"].active = False
    db.commit()
    login(client)
    assert client.get("/market").status_code == 403
