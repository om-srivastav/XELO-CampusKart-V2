import importlib.util

import pytest

from app.config import Settings


def test_application_exists():
    assert importlib.util.find_spec("app") is not None, "FastAPI application has not been created"


def test_home_health_headers(client):
    assert client.get("/health/live").json() == {"status": "ok"}
    response = client.get("/")
    assert response.status_code == 200
    assert b"XELO" in response.content
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert client.get("/missing").status_code == 404


def test_production_requires_services(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValueError):
        Settings(APP_ENV="production", SECRET_KEY="")
