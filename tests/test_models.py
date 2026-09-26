def test_models_available():
    import importlib.util

    assert importlib.util.find_spec("app.models") is not None, "Persistence layer missing"


def test_identity_and_price_constraints(app, people, db):
    import pytest
    from sqlalchemy.exc import IntegrityError

    from app.models import Product, User

    db.add(
        User(
            username="seller",
            email="duplicate@north.edu",
            display_name="Duplicate",
            password_hash="x",
            campus_id=1,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(Product(title="Bad", description="Bad", price=-1, seller_id=1, campus_id=1, category_id=1))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
