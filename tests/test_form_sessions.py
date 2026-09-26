from app.config import Settings


def test_development_secret_survives_restart(tmp_path, monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    assert (
        Settings(INSTANCE_PATH=str(tmp_path), _env_file=None).SECRET_KEY
        == Settings(INSTANCE_PATH=str(tmp_path), _env_file=None).SECRET_KEY
    )


def test_csrf_refresh_and_friendly_failure(app, client):
    app.state.settings.CSRF_ENABLED = True
    response = client.get("/auth/form-token")
    assert response.status_code == 200
    assert response.json()["token"]
    assert response.headers["Cache-Control"] == "no-store"
    failed = client.post("/auth/login", data={"csrf_token": "old"})
    assert failed.status_code == 400
    assert b"CSRF" not in failed.content
    assert b"Please reopen the form" in failed.content
    valid = client.post(
        "/auth/login",
        data={"csrf_token": response.json()["token"], "email": "missing@example.com", "password": "anything"},
    )
    assert b"Please reopen the form" not in valid.content
