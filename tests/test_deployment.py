from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.config import Settings
from app.database import Base
from app.main import build_app


def production_settings(**overrides):
    values = dict(
        APP_ENV="production",
        SECRET_KEY="0123456789abcdef" * 4,
        DATABASE_URL="postgresql+psycopg://test:test@localhost/xelo_test",
        BASE_URL="https://localhost",
        TRUSTED_HOSTS=["localhost"],
        MAIL_PROVIDER="resend",
        MAIL_API_KEY="test-only-key",
        MAIL_FROM="xelo@example.test",
        REDIS_URL="redis://localhost:6379/0",
        RATELIMIT_ENABLED=False,
        DEBUG=True,
    )
    values.update(overrides)
    return Settings(**values)


def test_migration_upgrade_downgrade(tmp_path):
    app = build_app(
        Settings(
            APP_ENV="testing",
            SECRET_KEY="migration-test",
            DATABASE_URL="sqlite:///" + str(tmp_path / "migrated.db"),
            RATELIMIT_ENABLED=False,
        )
    )
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.attributes["settings"] = app.state.settings
    command.upgrade(cfg, "head")
    assert "product" in inspect(app.state.engine).get_table_names()
    command.check(cfg)
    command.downgrade(cfg, "base")
    assert "product" not in inspect(app.state.engine).get_table_names()
    command.upgrade(cfg, "head")
    assert "user_session" in inspect(app.state.engine).get_table_names()
    app.state.engine.dispose()


def test_production_cookie_and_headers():
    app = build_app(production_settings())
    assert app.state.settings.DEBUG is False
    assert app.state.settings.SESSION_COOKIE_SECURE is True
    with TestClient(app, base_url="https://localhost") as client:
        response = client.get("/auth/login")
    assert "secure" in response.headers["set-cookie"].lower()
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "samesite=lax" in response.headers["set-cookie"].lower()
    assert "max-age=" in response.headers["strict-transport-security"]


def test_login_rate_limit_is_enforced(tmp_path):
    app = build_app(
        Settings(
            APP_ENV="testing",
            SECRET_KEY="rate-test",
            DATABASE_URL="sqlite://",
            CSRF_ENABLED=False,
            RATELIMIT_ENABLED=True,
            REDIS_URL="memory://",
        )
    )
    Base.metadata.create_all(app.state.engine)
    with TestClient(app) as client:
        statuses = [
            client.post(
                "/auth/login", data={"email": "unknown@example.edu", "password": "wrong-password"}
            ).status_code
            for _ in range(11)
        ]
    assert statuses[-1] == 429
    assert 401 in statuses
    Base.metadata.drop_all(app.state.engine)
    app.state.engine.dispose()
