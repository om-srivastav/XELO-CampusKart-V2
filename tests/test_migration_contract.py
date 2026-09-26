import hashlib
import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.security import hash_password, verify_password


def test_no_flask_runtime_dependency():
    text = (Path(__file__).parents[1] / "requirements.txt").read_text()
    assert "flask" not in text.lower()
    assert "werkzeug" not in text.lower()


def test_all_original_routes_preserved(app):
    mapping = json.loads((Path(__file__).parents[1] / "docs/route-map.json").read_text())
    actual = app.openapi()["paths"]
    for route in mapping:
        path = re.sub(r"\{(\w+):int\}", r"{\1}", route["path"])
        for method in route["methods"]:
            assert method.lower() in actual[path], (path, method)


def test_legacy_scrypt_passwords_and_new_argon2():
    password = "Existing-account-password-123"
    salt = "known-test-salt"
    derived = hashlib.scrypt(
        password.encode(), salt=salt.encode(), n=32768, r=8, p=1, maxmem=64 * 1024 * 1024
    ).hex()
    original = "scrypt:32768:8:1$" + salt + "$" + derived
    assert verify_password(original, password)
    assert not verify_password(original, "incorrect")
    assert hash_password(password).startswith("$argon2")


def test_csrf_token_cannot_cross_browser_sessions(app):
    app.state.settings.CSRF_ENABLED = True
    with TestClient(app) as first, TestClient(app) as second:
        token = first.get("/auth/form-token").json()["token"]
        second.get("/auth/form-token")
        response = second.post(
            "/auth/login", data={"email": "a@example.com", "password": "wrong", "csrf_token": token}
        )
        assert response.status_code == 400
        assert "Please reopen the form" in response.text


def test_oversized_request_rejected_before_form_parsing(app):
    app.state.settings.MAX_CONTENT_LENGTH = 1024
    with TestClient(app) as client:
        assert client.post("/auth/login", content=b"x" * 1025).status_code == 413
