def test_production_uses_shared_rate_limit_storage():
    from limits.storage import RedisStorage

    from app import create_app
    from app.extensions import limiter

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
            "RATELIMIT_ENABLED": True,
        }
    )
    with app.app_context():
        assert isinstance(limiter.storage, RedisStorage)
