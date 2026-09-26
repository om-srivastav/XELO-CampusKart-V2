from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_native_fastapi_application(app):
    assert isinstance(app, FastAPI)
    with TestClient(app) as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/openapi.json").status_code == 200
