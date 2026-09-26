import logging

from fastapi import Request
from limits import parse
from limits.storage import storage_from_string
from limits.strategies import FixedWindowRateLimiter

from ..security import digest
from ..web import abort


def configure(settings):
    storage = storage_from_string(settings.REDIS_URL or "memory://")
    return storage, FixedWindowRateLimiter(storage)


def enforce(request, rule, key, scope):
    if not request.app.state.settings.RATELIMIT_ENABLED:
        return
    try:
        allowed = request.app.state.rate_limiter.hit(parse(rule), scope, key)
    except Exception:
        logging.getLogger(__name__).warning("Rate limiting storage unavailable")
        abort(503, "Please try again shortly.")
    if not allowed:
        abort(429)


def limit(rule, methods=None, by_email=False):
    def dependency(request: Request):
        if methods and request.method not in methods:
            return
        key = (
            digest(request.state.form.get("email", "").strip().lower())
            if by_email
            else (request.client.host if request.client else "unknown")
        )
        enforce(request, rule, key, request.url.path + (":email" if by_email else ":ip"))

    return dependency
