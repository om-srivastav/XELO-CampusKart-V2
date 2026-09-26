# FastAPI migration report
Verified 26 September 2026.

## Result
XELO runs natively through uvicorn app.main:app, without Flask or Werkzeug installed. The original application is preserved in ../xelo; no Git repository existed in the workspace. Existing local data was copied using SQLite backup and image-file copying: 2 users, 4 listings, 2 campuses, 8 WebP files. Private data is excluded from the distribution archive. Users should sign in again after switching servers.

## Created
- app/main.py, __main__.py, database.py, dependencies.py, security.py, web.py.
- app/routers/: auth, marketplace, profiles, messaging, notifications, wishlist, reviews, reports, analytics, admin.
- app/middleware/: HTTP security/body limits and rate limiting.
- app/schemas/: login form and typed health/notification/message/search responses.
- Standalone alembic.ini, Dockerfile, .dockerignore, compose.yaml.
- tests/test_migration_contract.py and native mail/storage/migration coverage.
- docs/MIGRATION-MAP.md, route-map.json, this report.

## Modified
- Models use plain SQLAlchemy; all 18 table definitions and relationships retained.
- Configuration uses pydantic-settings, environment validation, stable development secret and strict production settings.
- Services accept explicit request/session/settings; storage uses an adapter; email supports Resend/Brevo HTTP APIs and development files.
- Templates use native request/query/URL integration; existing styling, JavaScript, images, themes and WebGL retained.
- Management commands, requirements, test fixtures, browser tests, GitHub Actions, .env.example and README migrated.

## Dependencies
Removed Flask, Flask-SQLAlchemy, Flask-Migrate, Flask-WTF, Flask-Limiter and Werkzeug dependencies. No Flask-Login dependency is required. Removed WSGI launchers and Render configuration from the migrated project.
Added FastAPI, Starlette, Uvicorn, pydantic-settings, python-multipart, Argon2 and httpx; retained plain SQLAlchemy, Alembic, psycopg, Redis/limits, Jinja2, Pillow and Click. Exact pinned closure is in requirements.txt.

## Routes and features
All 46 original feature handlers have their original URL/method contracts verified against docs/route-map.json. Public homepage/safety and live/ready health routes remain available.
Authentication/reset/change/session revoke/deactivation, campus isolation/administration, profiles/privacy/images, listing lifecycle/images/search/filters/pagination, WhatsApp, wishlist, views, messaging/read state, notifications, reviews, reports, moderation and analytics are migrated. The free-text campus entry and absence of membership-verification steps are preserved.
Browser authentication remains cookie based. CSRF, login throttling, secure password hashing with legacy password verification, ownership checks, upload validation and production fail-closed configuration remain enforced.

## Verification
- Clean Python 3.12 environment: Flask and Werkzeug absent.
- SQLite: 95 tests passed.
- PostgreSQL 18: 95 tests passed; 88% backend statement coverage.
- Standalone Alembic upgrade and schema check: SQLite and PostgreSQL passed; no schema drift. SQLite migration round-trip is covered by tests.
- Ruff: all checks passed. Runtime dependency audit: no known vulnerabilities at verification.
- Browser workflow: profile, image listing, search, wishlist, buyer/seller messages, reservation/sale/confirmation, reviews, reports and moderation passed; no browser/server errors.
- Browser layouts: 320/390/768/1440 widths across five pages passed; mobile dialog keyboard/focus, dark theme, reduced motion, WebGL fallback and login without JavaScript passed.
- New CI configuration is supplied; remote GitHub Actions has not been run.
- Starlette emits one non-failing deprecation warning for its httpx TestClient integration.

## Known limitations
- Docker configuration is provided but could not be built here because Docker is unavailable.
- Redis production integration is configured; no live Redis service was exercised locally.
- Email HTTP contracts were tested with mocks; live provider delivery requires credentials and sender-domain setup.
- Local storage adapter is implemented and verified. An S3/R2 adapter is not shipped; use durable storage on the host until one is added. Stateless/serverless hosting needs external upload storage.
- No public deployment, custom domain, payment/escrow, load test or external security audit was performed.
- Status-change notifications currently cap at 1,000 watchers; use background jobs for larger scale.
- College names are self-declared, not institutional verification.

## Deployment
Use a generic Docker/ASGI host or VPS with PostgreSQL, Redis, HTTPS, an email API and durable uploads. Railway, Fly.io, Koyeb or cloud/VPS infrastructure are examples, subject to their current plans and storage support. No free tier or provider pricing is assumed. Run migrations as a release step, then python -m app (PORT supported) or uvicorn app.main:app. See README for commands and proxy trust settings. Render is not required.
