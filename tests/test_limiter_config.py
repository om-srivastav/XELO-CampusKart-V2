from limits.storage import RedisStorage
from test_deployment import production_settings

from app.main import build_app


def test_production_uses_shared_rate_limit_storage():
    app = build_app(production_settings(RATELIMIT_ENABLED=True))
    assert isinstance(app.state.rate_storage, RedisStorage)
