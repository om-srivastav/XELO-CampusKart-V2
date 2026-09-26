# XELO — CampusKart

**Buy. Sell. Connect. Within Campus.**

A fresh Flask campus marketplace with Jinja pages, SQLAlchemy persistence, private messaging and a lightweight WebGL homepage. No V1 code or runtime JavaScript framework is required. Node is optional and used only for browser tests.

## What works

- Signup with a typed college name and immediate marketplace access, login/logout, password recovery/change, session expiry, individual/all-other session revocation and account deactivation.
- Campus profiles with avatar/cover uploads, department/year/city/bio and separate profile/contact/phone/WhatsApp privacy controls.
- Database categories, listing creation/editing, drafts, publish/reserve/sell/hide/remove, six-image galleries, preview/reorder/removal, search suggestions, combined filters, sorting and pagination.
- Saved listings, deduplicated views, direct WhatsApp links with click tracking, private listing conversations with short polling, read state and notifications.
- Seller statistics, per-listing performance, 14-day trends, buyer-confirmed reviews, private reports, audited admin moderation, category/campus administration and account suspension.
- Responsive design, light/dark/system themes, mobile filter dialog, reduced-motion behavior, keyboard controls and static fallback when WebGL is unavailable.

Production starts empty. Initial categories are configuration, not fabricated listings. Statistics come from application records.

## Quick start — Windows PowerShell

Use Python 3.11 or newer; this build was tested on Python 3.12.10. Open a terminal in this project's root.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

Paste the generated secret into `.env` as `SECRET_KEY`. Keep it private. If activation is restricted, call `.venv\Scripts\python` directly instead.

```powershell
python -m flask --app run db upgrade
python -m flask --app run seed-categories
python -m flask --app run campus-add "Your College" "Your City" --domains "your-college.edu"
python -m flask --app run create-admin
python run.py
```

Open [local XELO](http://127.0.0.1:5000). Replace the example college, city and email domain with your real configuration. The admin command prompts for email, username, campus ID and a private password; no default admin account exists.

Students type their college name at signup. Matching names reuse an existing campus; new names create one. No membership verification or approval is required. Campus assignment is not editable by ordinary members.

## macOS / Linux

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
# Set a private SECRET_KEY, then run the same flask commands above.
python run.py
```

## Email during development

With `MAIL_MODE=file`, password reset emails are real generated MIME messages saved to `instance/mail/*.eml`. Open the latest file and follow its link. They expire after 30 minutes and are single-use. This mode is explicitly blocked in production.

Use `MAIL_MODE=smtp` and configure SMTP to deliver real email. SMTP delivery has not been tested against your provider. Password reset responses intentionally do not reveal whether an account exists.

## Typical workflow

1. Register with your college name, then sign in. Marketplace access is immediate.
2. Complete your profile and optionally enable phone or WhatsApp contact.
3. Select **Sell an item**, enter details, upload photos and publish.
4. A second member of the same campus can search, save, message or contact you.
5. Reserve the item if needed. When sold, select a buyer from its conversations.
6. The buyer confirms receiving the item and can leave one review.
7. Reports go to the admin panel; moderation actions are logged.

XELO does not process payments, verify bank transfers or guarantee merchandise. Reviews represent peer-confirmed exchanges. WhatsApp uses ordinary click-to-chat links; no Meta API or WhatsApp Business account is required.

## Configuration

| Variable | Purpose |
|---|---|
| `APP_ENV` | `development` or `production` |
| `SECRET_KEY` | Stable private secret; at least 32 characters in production |
| `DATABASE_URL` | SQLite locally; PostgreSQL in production; plain postgres/postgresql URLs normalize to psycopg |
| `BASE_URL` | Canonical URL for password reset links; HTTPS in production |
| `TRUSTED_HOSTS` | Comma-separated allowed hostnames, without scheme or path |
| `UPLOAD_FOLDER` | Image storage path; persistent disk path in production |
| `RATELIMIT_STORAGE_URI` | `memory://` locally; shared `redis://` or `rediss://` in production |
| `MAIL_MODE` | `file` for development; `smtp` for production |
| `SMTP_HOST`, `SMTP_PORT` | SMTP server and port; default port 587 |
| `SMTP_TLS` | STARTTLS; default true |
| `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Provider credentials and verified sender |
| `TRUST_PROXY` | Trust one upstream proxy for client IP/protocol; true only behind the configured reverse proxy |

Without a development secret, the application generates a process-local secret; restart invalidates cookies. Always set a stable secret for normal use and multi-process hosting.

Upload limits: six images per listing, 5 MB per image, 32 MB per request, 20 million decoded pixels, JPEG/PNG/WebP only. Images are re-encoded without source metadata, with full and thumbnail variants. Session lifetime is seven days maximum and 24 hours idle.

## Architecture

```text
app/
  __init__.py        app factory, headers, errors, home and health
  config.py          environment configuration and production validation
  extensions.py      SQLAlchemy, migrations, CSRF and rate limiting
  models/            identity, catalog and community persistence
  auth/ profiles/ marketplace/ wishlist/
  messaging/ notifications/ reviews/ reports/
  analytics/ admin/  domain blueprints
  services/          security, validation, storage, mail and view events
  templates/         server-rendered pages and reusable components
  static/            CSS, theme scripts, interactions, isolated WebGL
migrations/          reviewed Alembic schema history
tests/               pytest integration/security tests and browser QA
docs/                architecture, delivery record and operations
render.yaml          production services and persistent disk
```

An active campus is stored on each user, without a membership verification requirement. Profile/contact settings share the user row to keep authorization state transactional. Listing sale fields hold the selected buyer and confirmation; confirmed sales cannot be reassigned.

Routes use shared authorization helpers. Contact values are only rendered when all privacy conditions allow them. Admins cannot browse arbitrary private message bodies; the admin conversation view shows metadata.

## Tests

```sh
python -m pytest -q
python -m pytest --cov=app --cov-report=term-missing
python -m ruff check app tests run.py wsgi.py
python -m pip_audit -r requirements.txt
```

For PostgreSQL, create a **disposable database named exactly `xelo_test`**, then set:

```powershell
$env:TEST_DATABASE_URL="postgresql+psycopg://test_user:password@127.0.0.1:5432/xelo_test"
python -m pytest -q
Remove-Item Env:TEST_DATABASE_URL
```

**The test fixture creates and drops application tables. Never point it at production.** Its database-name guard rejects other names. PostgreSQL server credentials are not committed.

GitHub Actions runs SQLite and PostgreSQL tests, schema checks, lint and the dependency audit. The workflow is provided; a hosted CI run is not claimed.

Browser QA is optional:

```sh
npm install
npx playwright install chromium
python tests/qa_server.py
# In a second terminal:
npm run test:browser
```

The QA server uses an isolated `instance/browser-qa.db`, clearly named QA accounts and generated fixture images. It never populates the normal application database. See [browser verification](tests/BROWSER.md). The runtime app does not use Node.

## Database migrations

```sh
flask --app wsgi db upgrade
flask --app wsgi db check
# After a deliberate model change:
flask --app wsgi db migrate -m "describe change"
# Review generated migration before applying it.
flask --app wsgi db upgrade
```

Do not use `create_all` for production. The supplied initial migration was exercised through upgrade, downgrade and re-upgrade on SQLite and PostgreSQL. Downgrades may destroy data; back up and inspect the migration first.

## Render deployment

The supplied `render.yaml` defines a Python web service, PostgreSQL, Redis-compatible Key Value storage and an upload disk. These are paid resources; it does not create or charge for anything until you deploy.

1. Push this **xelo directory as the repository root** to your chosen Git repository.
2. Create a Render Blueprint from that repository.
3. Enter `BASE_URL=https://your-service.onrender.com`, its matching `TRUSTED_HOSTS`, and SMTP values when prompted. Use your eventual custom domain when applicable.
4. Render installs requirements, runs migrations in pre-deploy, then starts Gunicorn.
5. In the Render shell run `flask --app wsgi seed-categories`, `campus-add`, and `create-admin`.
6. Verify signup mail, a same-campus transaction flow, readiness, disk persistence and backups on the deployed service.

The pre-deploy step only touches the database. Render disks are unavailable during build/pre-deploy, so image directories are created on first runtime upload. One service with a disk is the supported initial topology; horizontal scaling requires replacing the storage adapter with shared object storage.

Production rejects missing secrets, non-PostgreSQL databases, HTTP base URLs, development mail and memory-only rate limiting. Cookies become Secure/HttpOnly/SameSite; debug is forced off. Gunicorn writes operational errors to standard logs; no application request logging of passwords, phone numbers or message bodies is added.

[Render Flask deployment](https://render.com/docs/deploy-flask), [persistent disk constraints](https://render.com/docs/disks), [Blueprint configuration](https://render.com/docs/blueprint-spec), and [Flask security guidance](https://flask.palletsprojects.com/en/stable/web-security/) informed these settings.

## Privacy, security and limits

- Members see only their chosen campus. Suspended users and removed listings are denied through direct listing, image and contact URLs.
- Profile visibility and contact visibility both gate phone/WhatsApp disclosure. Numbers are private by default. Enabling WhatsApp reveals the number to the member who opens that link.
- CSRF covers all POST actions, including polling read receipts. GET views record only deduplicated view telemetry.
- The CSP permits local assets; form navigation allows only self plus WhatsApp's click-to-chat destinations. This narrow exception is necessary for the real redirect.
- Messages poll every five seconds while visible, with retry backoff; this is not WebSocket realtime.
- Listing views count once per member/listing/UTC day and exclude the owner. They are not a count of unique humans.
- Search history is opt-in. Run maintenance daily to enforce 30-day search/token retention and 90-day login-history retention. Reports/audit and historical conversations are retained; define a campus retention policy before public launch.
- No deployment-specific penetration test, sustained load test, formal accessibility certification, or guarantee against all vulnerabilities is claimed.

## Maintenance and backup

Run daily from the service environment:

```sh
flask --app wsgi maintenance
```

It deletes expired history/tokens/sessions and orphan image variants older than one day. Back up PostgreSQL and the upload disk together; use a maintenance window or consistent snapshot strategy. Test restoring both into a separate environment, then run migrations and verify protected image URLs. Changing `SECRET_KEY` invalidates existing browser cookies.

Health: `/health/live` checks process availability; `/health/ready` checks a database query and returns generic 503 on failure. Monitor both and external email delivery.

## Troubleshooting

- **No campuses at signup:** register a campus using CLI or the admin panel.
- **Campus access:** no membership approval is required. Administratively disabled campuses remain unavailable.
- **No password reset email locally:** inspect `instance/mail`; production requires SMTP.
- **403 on forms:** reload for a fresh CSRF token; confirm HTTPS/proxy/cookie configuration.
- **Images disappear after deploy:** use the configured persistent disk, never ephemeral application storage.
- **429:** wait for the rate window; ensure `TRUST_PROXY` matches your actual reverse-proxy topology.
- **Database tables missing:** run migrations with the same DATABASE_URL as the server.
- **Windows test temp permissions:** use `pytest --basetemp=./instance/pytest-temp` in a disposable test directory.
- **WebGL unavailable:** the static composition remains visible and all marketplace functions work.

## Deliberate future extensions

Shared object storage for multi-instance hosting, transactional email queues, institution SSO, moderation appeals and stronger exchange attestation can be added through the existing boundaries. They are not presented as implemented features.
