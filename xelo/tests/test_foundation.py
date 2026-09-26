import importlib.util

import pytest


def test_application_exists():
    assert importlib.util.find_spec("app") is not None, "Flask application has not been created"


def test_home_health_headers(tmp_path):
    from app import create_app

    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SECRET_KEY": "test-key",
            "UPLOAD_FOLDER": str(tmp_path),
        }
    )
    client = app.test_client()
    assert client.get("/health/live").json == {"status": "ok"}
    response = client.get("/")
    assert response.status_code == 200
    assert b"XELO" in response.data
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert client.get("/missing").status_code == 404


def test_production_requires_services(monkeypatch):
    from app import create_app

    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValueError):
        create_app({"APP_ENV": "production", "SECRET_KEY": ""})
