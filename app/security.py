"""Password compatibility, signed form tokens and session primitives."""

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .web import abort

_hasher = PasswordHasher()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def hash_password(value):
    return _hasher.hash(value)


def verify_password(encoded, value):
    if encoded.startswith("$argon2"):
        try:
            return _hasher.verify(encoded, value)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
    # Preserve passwords created by the original application without Werkzeug.
    try:
        method, salt, expected = encoded.split("$", 2)
        parts = method.split(":")
        if parts[0] == "scrypt":
            n, r, p = map(int, parts[1:])
            actual = hashlib.scrypt(
                value.encode(),
                salt=salt.encode(),
                n=n,
                r=r,
                p=p,
                maxmem=max(64 * 1024 * 1024, 132 * n * r * p),
            ).hex()
        elif parts[0] == "pbkdf2":
            actual = hashlib.pbkdf2_hmac(parts[1], value.encode(), salt.encode(), int(parts[2])).hex()
        else:
            return False
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def generate_csrf(request):
    nonce = request.session.setdefault("csrf", secrets.token_urlsafe(32))
    return URLSafeTimedSerializer(request.app.state.settings.SECRET_KEY, salt="xelo-csrf").dumps(nonce)


def check_csrf(request):
    if not request.app.state.settings.CSRF_ENABLED:
        return
    token = (
        request.headers.get("x-csrftoken")
        or request.headers.get("x-csrf-token")
        or request.state.form.get("csrf_token", "")
    )
    try:
        value = URLSafeTimedSerializer(request.app.state.settings.SECRET_KEY, salt="xelo-csrf").loads(
            token, max_age=3600
        )
        nonce = request.session.get("csrf")
        if not nonce or not hmac.compare_digest(str(value), str(nonce)):
            raise BadSignature("mismatch")
    except (BadSignature, TypeError):
        abort(400, "Please reopen the form and try again. Your session has changed.")
