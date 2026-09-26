# XELO — CampusKart V2 · FastAPI

Campus marketplace with server-rendered Jinja pages, responsive themes, WebGL enhancement, listings/images, WhatsApp contact, private messaging, notifications, saved items, buyer-confirmed reviews, reports, moderation and seller analytics.

This is the migrated application. It runs natively on FastAPI/Starlette and Uvicorn, with **no Flask or Flask extensions**. The working original is preserved separately in the workspace; this package contains only the FastAPI project.

## Local setup

Python 3.12 recommended. Run commands from this folder.

```sh
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

python -m pip install -r requirements-dev.txt
```

Copy `.env.example` to `.env`. The defaults use SQLite, development file email and in-memory rate limiting. A private development signing key is persisted in `instance/.development-secret`; do not share that file.

```sh
python -m alembic upgrade head
python -m app.cli seed-categories
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000**. Students type their college name at signup and can use the marketplace immediately after signing in. Campus membership verification remains removed as requested.

To create an administrator:

```sh
python -m app.cli campus-add "Pranveer Singh Institute Of Technology" Kanpur
python -m app.cli create-admin
```

Use the campus ID printed by campus-add. If the college already exists, use its existing ID instead. The admin command prompts for credentials; it does not print the password.

## Existing data

The SQL schema, table names, foreign keys and original migration revision are preserved. Existing PostgreSQL databases can continue using their current DATABASE_URL. Run `python -m alembic upgrade head` and `python -m alembic check` before switching traffic.

For SQLite, back up and copy the database to `instance/xelo.db`, or set DATABASE_URL to its absolute path. Copy the original uploads directory to UPLOAD_FOLDER. Database and uploads must be transferred together; CLI migrations do not transfer records between SQLite and PostgreSQL.

Old scrypt/PBKDF2 password hashes still work; new/reset passwords use Argon2. Existing accounts are retained, but browsers must sign in again because the cookie format/name changed. Never copy credentials or user data into a public repository.

## Settings

| Setting | Purpose |
| --- | --- |
| APP_ENV | development, testing or production |
| SECRET_KEY | Persistent secret; production requires at least 32 characters with sufficient diversity |
| DATABASE_URL | SQLAlchemy URL; production requires PostgreSQL/psycopg |
| BASE_URL | Canonical URL for password reset links; HTTPS in production |
| TRUSTED_HOSTS | Comma-separated hostnames, without schemes or paths |
| REDIS_URL | redis:// or rediss:// for shared limits; memory:// for local development |
| UPLOAD_FOLDER | Durable directory for original sanitized images and thumbnails |
| INSTANCE_PATH | Local application state |
| MAIL_PROVIDER | file (development), resend or brevo |
| MAIL_API_KEY | Transactional HTTP email provider key |
| MAIL_FROM | Sender address authorized by the provider |
| MAIL_FOLDER | Development .eml directory |
| SESSION_HOURS | Absolute session lifetime, default 168 hours |
| SESSION_IDLE_HOURS | Inactivity expiry, default 24 hours |
| SESSION_COOKIE_SAMESITE | lax by default; production cookies are Secure and all are HttpOnly |
| PORT | Port used by python -m app; default 8000 |
| FORWARDED_ALLOW_IPS | Trusted proxy IPs/networks for the portable launcher; unset means forwarded headers are ignored |

Production configuration fails clearly without PostgreSQL, a strong secret, Redis, HTTPS, explicit trusted hosts and API email credentials. Keep secrets in provider environment settings or a private .env.

## Email

Password reset uses an email service abstraction. Development writes real MIME messages to MAIL_FOLDER; open the latest .eml and use its expiring single-use link.

Resend and Brevo use HTTPS APIs; no SMTP port is required. Configure MAIL_PROVIDER, MAIL_API_KEY and MAIL_FROM. Provider HTTP behavior is tested with mocked responses, but no live provider account was used during migration.

## Uploads and hosting

JPEG/PNG/WebP uploads are decoded, size/dimension checked, metadata stripped and stored as generated WebP filenames plus thumbnails. Access to profile/listing images checks campus, ownership and privacy before serving. Total requests are bounded to 32 MB and each image to 5 MB; listings allow six images.

The storage protocol is in `app/services/storage.py`. The included implementation is local disk and works on any provider with durable storage. **S3/R2/Supabase/B2 adapters are not included.** A serverless host with an ephemeral filesystem, such as a function-only deployment, requires an object-storage adapter first.

## Generic production deployment

Use any host supporting Python ASGI or Docker, PostgreSQL, Redis and durable uploads. No Render configuration is required.

```sh
python -m pip install -r requirements.txt
python -m alembic upgrade head
python -m app.cli seed-categories
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --no-proxy-headers
```

Or run `python -m app` to honor PORT. That launcher trusts forwarded headers only when FORWARDED_ALLOW_IPS is explicitly configured. Set the exact trusted proxy addresses provided by your host; do not expose an app that trusts every sender's forwarded headers. TLS should terminate at your trusted proxy. BASE_URL/TRUSTED_HOSTS must match your public domain.

### Docker

```sh
docker build -t xelo-fastapi .
docker run --rm --env-file .env -v xelo-data:/data xelo-fastapi python -m alembic upgrade head
docker run -d --name xelo --env-file .env -p 8000:8000 -v xelo-data:/data xelo-fastapi
```

Supply production PostgreSQL/Redis/API-mail settings in .env before public deployment. The container runs as an unprivileged user. /data must be durable. Migrations are an explicit release step; they do not run concurrently in each worker.

For a local PostgreSQL + Redis stack:

```sh
docker compose up --build -d
docker compose exec web python -m app.cli seed-categories
```

Compose is a development example, binds only localhost, and uses a development database password. Configure production secrets, HTTPS and trusted proxy routing before hosting it. Docker was unavailable on the development machine, so container build/launch has not been executed here.

## Management

```sh
python -m app.cli --help
python -m app.cli seed-categories
python -m app.cli campus-add "College Name" "City"
python -m app.cli create-admin
python -m app.cli maintenance
python -m app.cli seed-demo
```

Demo accounts are explicitly labeled and prohibited in production. Maintenance applies retention to history, expired tokens/sessions, development email and orphaned local images. Schedule it with your host's scheduler. Back up PostgreSQL and uploads together and verify restoration separately.

## Testing

```sh
python -m ruff check app tests
python -m pytest
python -m alembic check
python -m pip_audit -r requirements.txt
```

For PostgreSQL tests set TEST_DATABASE_URL to an **isolated database named xelo_test**. The suite creates/drops tables and must never target real data. GitHub Actions runs SQLite/PostgreSQL matrices, migrations, lint and dependency auditing.

Optional browser tests:

```sh
npm ci
npx playwright install chromium
python tests/qa_server.py
# In another terminal:
npm run test:browser
npm run test:layout
```

QA uses a separate loopback-only database and fixture accounts. Set BROWSER_CHANNEL=msedge to use installed Edge. No WhatsApp message is sent by these tests.

## Operational boundaries

- Health: /health/live checks the process; /health/ready checks database and production rate-limit storage.
- Authentication uses signed HttpOnly browser cookies referencing hashed, revocable database sessions. Every state-changing form has CSRF protection.
- User-entered college names are not institutionally verified. Campus isolation and administrator suspension remain enforced.
- WhatsApp is opt-in; enabling it during listing updates the seller's contact settings across listings. Owners can test their own link without inflating analytics.
- Status-change watcher notifications currently process up to 1,000 watchers; a background queue is appropriate beyond this scale.
- No payment processing or escrow is provided.
- Local single-process rate limiting is for development; production uses Redis.
- Live hosting, real mail delivery, backup restoration, load testing and external penetration testing are not claimed as completed.

See `docs/MIGRATION-MAP.md`, `docs/route-map.json` and `docs/MIGRATION-REPORT.md` for the migration and verification details.
