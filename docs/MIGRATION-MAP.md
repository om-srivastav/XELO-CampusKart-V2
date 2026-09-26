# Migration map

The working original remains in ../xelo. This sibling project is native ASGI; it does not mount the original WSGI application. No Git repository was present, so no branch or history could be created/preserved.

| Original component | Replacement |
| --- | --- |
| Flask app factory | app/main.py native FastAPI app and test builder |
| 10 Blueprint modules, 46 route handlers | 10 native APIRouters under app/routers; original paths/methods in route-map.json |
| Flask-SQLAlchemy db.Model and db.session | plain SQLAlchemy DeclarativeBase, request-scoped Session via Depends(get_db) |
| Flask-Migrate | direct Alembic env, original revision and schema |
| Flask browser sessions | Starlette signed cookie + existing hashed revocable UserSession database records |
| Werkzeug password hashing | Argon2 for new passwords; hashlib verification of existing scrypt/PBKDF2 passwords |
| Flask-WTF CSRF | signed session-bound expiring CSRF tokens checked for unsafe form requests |
| Flask-Limiter | limits library with Redis production storage and development memory fallback |
| Flask template globals | Jinja2Templates and explicit Request/response utilities; template context preserves UI |
| request form/files globals | parsed Starlette FormData/UploadFile scoped to Request |
| Flask CLI | standalone Click commands through python -m app.cli |
| raw SMTP | HTTP API email provider interface (Resend, Brevo), local mail files for development |
| Render upload disk assumption | configurable local Storage adapter on any durable volume |
| Gunicorn/Waitress WSGI | Uvicorn ASGI and portable Docker launcher |

Compatibility risks and decisions:
- Existing SQL table/column/constraint names are preserved; no schema migration is required solely for this framework change.
- Old signed browser cookies use a different format. Users sign in once again; password hashes and stored account records are retained.
- Routes are ordered with static paths before parameterized token paths to preserve route matching.
- Sync database, image and provider operations run in FastAPI worker threads. No async database driver is introduced.
- Uploads are bounded before multipart parsing; decoded size/type checks and cleanup are retained.
- New storage providers can implement the Storage protocol. The included adapter still needs a persistent filesystem; ephemeral/serverless deployment requires an object-storage adapter.
- Proxy headers are disabled by the portable launcher unless FORWARDED_ALLOW_IPS explicitly lists trusted upstreams.
- Free hosting and domain availability are separate from framework compatibility. No host has been deployed.
