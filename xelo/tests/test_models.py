def test_models_available():
    import importlib.util

    assert importlib.util.find_spec("app.models") is not None, "Persistence layer missing"


def test_identity_and_price_constraints(app, people):
    import pytest
    from sqlalchemy.exc import IntegrityError

    from app.extensions import db
    from app.models import Product, User

    db.session.add(
        User(
            username="seller",
            email="duplicate@north.edu",
            display_name="Duplicate",
            password_hash="x",
            campus_id=1,
        )
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    db.session.add(Product(title="Bad", description="Bad", price=-1, seller_id=1, campus_id=1, category_id=1))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
