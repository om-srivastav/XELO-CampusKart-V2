import pytest

from app.extensions import db
from app.models import Campus, User


def signup(client, college):
    return client.post(
        "/auth/signup",
        data=dict(
            username="newstudent",
            display_name="New Student",
            email="new@example.com",
            password="Strong-password-123",
            confirm="Strong-password-123",
            college_name=college,
        ),
    )


def test_signup_accepts_typed_college_in_empty_database(client):
    page = client.get("/auth/signup")
    assert b'name="college_name"' in page.data
    assert b'<select name="campus_id"' not in page.data
    assert b"Create account" in page.data
    assert signup(client, "My Own College").status_code == 302
    user = User.query.one()
    assert user.campus.name == "My Own College"
    assert not user.verified
    assert user.campus.domains == ""


def test_signup_reuses_existing_college_case_and_whitespace(client):
    campus = Campus(name="Registered College", city="Kanpur")
    db.session.add(campus)
    db.session.commit()
    assert signup(client, "  REGISTERED   college  ").status_code == 302
    assert Campus.query.count() == 1
    assert User.query.one().campus_id == campus.id


@pytest.mark.parametrize("name", ["", " ", "A", "A" * 121])
def test_invalid_college_does_not_create_account(client, name):
    assert signup(client, name).status_code == 400
    assert User.query.count() == 0
    assert Campus.query.count() == 0


def test_typed_college_cannot_reactivate_disabled_campus(client):
    db.session.add(Campus(name="Closed College", city="Kanpur", active=False))
    db.session.commit()
    assert signup(client, "closed college").status_code == 400
    assert User.query.count() == 0
