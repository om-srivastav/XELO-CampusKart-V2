from pathlib import Path


def test_migration_upgrade_downgrade(tmp_path):
    from flask_migrate import downgrade, upgrade
    from sqlalchemy import inspect

    from app import create_app
    from app.extensions import db

    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "migration-test",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(tmp_path / "migrated.db"),
            "RATELIMIT_ENABLED": False,
        }
    )
    with app.app_context():
        directory = str(Path(__file__).resolve().parents[1] / "migrations")
        upgrade(directory=directory)
        assert "product" in inspect(db.engine).get_table_names()
        downgrade(directory=directory, revision="base")
        assert "product" not in inspect(db.engine).get_table_names()
        upgrade(directory=directory)
        assert "user_session" in inspect(db.engine).get_table_names()


def test_production_cookie_and_headers():
    from app import create_app

    app = create_app(
        {
            "APP_ENV": "production",
            "SECRET_KEY": "a" * 40,
            "SQLALCHEMY_DATABASE_URI": "postgresql+psycopg://test:test@localhost/xelo_test",
            "SMTP_HOST": "smtp.example.test",
            "SMTP_FROM": "xelo@example.test",
            "BASE_URL": "https://localhost",
            "MAIL_MODE": "smtp",
            "RATELIMIT_STORAGE_URI": "redis://localhost:6379/0",
            "RATELIMIT_ENABLED": False,
            "DEBUG": True,
        }
    )
    assert app.config["DEBUG"] is False
    assert app.config["SESSION_COOKIE_SECURE"] is True
    response = app.test_client().get("/auth/login", base_url="https://localhost")
    assert "Secure" in response.headers["Set-Cookie"]
    assert "HttpOnly" in response.headers["Set-Cookie"]
    assert "SameSite=Lax" in response.headers["Set-Cookie"]
    assert "max-age=" in response.headers["Strict-Transport-Security"]


def test_login_rate_limit_is_enforced(tmp_path):
    from app import create_app
    from app.extensions import db

    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "rate-test",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "WTF_CSRF_ENABLED": False,
            "RATELIMIT_ENABLED": True,
            "RATELIMIT_STORAGE_URI": "memory://",
        }
    )
    with app.app_context():
        db.create_all()
        client = app.test_client()
        statuses = [
            client.post(
                "/auth/login", data={"email": "unknown@example.edu", "password": "wrong-password"}
            ).status_code
            for _ in range(11)
        ]
        assert statuses[-1] == 429
        assert 401 in statuses
        db.session.remove()
        db.drop_all()
