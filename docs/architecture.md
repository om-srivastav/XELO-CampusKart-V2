# XELO V2.0 — architecture proposal

Status: approved design baseline. The application is implemented; consult verification.md and progress.md for delivery evidence and implementation decisions. The original Phase 0 report at the end is retained as design history.

## Product contract

Build XELO — CampusKart from an empty project, independently of any V1 implementation. Tagline: “Buy. Sell. Connect. Within Campus.” Students join a verified campus, complete a profile, publish items with images, discover listings, and contact sellers through internal messages or optional WhatsApp.

Use Python 3.11+, Flask, SQLAlchemy, Alembic via Flask-Migrate, Jinja, HTML, CSS, and vanilla JavaScript. SQLite serves local development and tests; PostgreSQL serves production. Deploy on Render. No React, Next.js, Node application backend, payment processing, WhatsApp Business API, or runtime dependency on the coding environment.

No fake listings, counts, controls, APIs, notifications, or analytics. Production starts empty except for explicitly installed category and campus configuration. Development fixtures are opt-in and visibly identified.

## Architecture choice

Recommended: a modular Flask monolith. Domain blueprints own routes and presentation; services own reusable business operations; SQLAlchemy models enforce persistence constraints. One deployment handles server-rendered pages and small authenticated JSON endpoints. This keeps access rules consistent and deployment manageable.

Alternatives considered:

| Approach | Benefit | Cost / decision |
|---|---|---|
| Modular Flask monolith | Simple deployment, transactions, shared authorization | Selected; modules need explicit boundaries |
| Separate Flask API and JavaScript client | Independent client development | Duplicates validation and state handling; unnecessary for the requested Jinja stack |
| Separate domain services | Independent scaling | Adds distributed authentication, deployment, and consistency costs before demand exists |

## Proposed project structure

Create a fresh `outputs/xelo/` project after architecture review:

```text
xelo/
  app/
    __init__.py              # create_app; register extensions and blueprints
    config.py                # environment parsing and production validation
    extensions.py            # database, migrations, CSRF, limiter
    models/                  # domain models grouped by responsibility
    auth/                    # signup, verification, login, recovery, sessions
    profiles/                # profile editing and visibility-aware presentation
    marketplace/             # discovery, listing lifecycle, images, contact
    wishlist/
    messaging/
    notifications/
    reviews/
    reports/
    analytics/
    admin/
    services/
      authorization.py       # membership, ownership, participation, admin checks
      storage.py             # image storage interface and local implementation
      images.py              # validation, decoding, re-encoding, variants
      mail.py                # SMTP delivery and explicit development delivery
      tokens.py              # single-use verification and reset tokens
      events.py              # analytics and notification transaction helpers
    templates/               # base, reusable cards/forms, domain pages, errors
    static/
      css/                   # tokens, layout, components, themes
      js/                    # progressive enhancement and isolated 3D module
  migrations/
  tests/
  docs/                      # architecture, phase reports, operations guide
  instance/                  # ignored local database
  uploads/                   # ignored local image storage
  requirements.txt
  requirements-dev.txt
  .env.example
  .gitignore
  run.py
  wsgi.py
  render.yaml
  README.md
```

Only implement modules in their assigned phase. Do not manufacture placeholder route handlers for future features.

## Campus-only access: proposed rule

“Campus-only” needs an enforceable membership rule, not just a college text field. Proposed default: each account has one active campus membership. An administrator registers a campus and its allowed email domains. Students verify a matching email address before browsing member listings, publishing, messaging, or revealing contact information.

For campuses without institutional email, support explicit administrator approval of membership. Selecting a college alone does not confer access. No identity document collection is required by this design.

The public homepage presents XELO and the join/login flow. Verified members see actual campus categories, newest listings, and trending listings. Listing queries, suggestions, images, profiles, wishlists, conversations, reports, and contact redirects all enforce campus membership. Cross-campus resources return a consistent not-found response.

Campus changes require a new membership verification and handling of existing listings; they are not a freely editable profile field. Admins can manage the platform across campuses through separate authorized routes.

This membership model is a proposed product decision, not a requirement explicitly specified in the supplied prompt.

## Persistence design

Use UTC timestamps, explicit foreign keys, named constraints, and migrations. Monetary values use fixed-precision decimal storage and server-side decimal validation. Never use floating point for price arithmetic. Store status values as strings constrained by the database for SQLite/PostgreSQL compatibility.

| Entity | Key data and invariants |
|---|---|
| Campus / CampusDomain | Name, city, active status; unique normalized allowed domain |
| Membership | User, campus, verification state/method; unique user-campus pair; one active membership per account enforced transactionally |
| User / Profile | Unique normalized email and username; password hash, account status, role; one profile per user |
| ContactPreference | One per user; show phone, enable WhatsApp, profile visibility, contact visibility |
| UserSession | Hashed random session identifier, user, expiry, last activity, revocation |
| LoginHistory | User where known, outcome, time, limited security metadata |
| AccountToken | Purpose, hashed token, user, expiry, consumed time |
| Category | Unique slug, name, description, icon key, active flag, display order |
| Product | Seller, campus, category, title, slug, description, price, condition, brand, city, negotiable, lifecycle status, timestamps |
| ProductImage | Product, generated storage key, dimensions, display order; unique product/order |
| Wishlist | Unique user/product; timestamp |
| ProductView | Product, viewer-derived pseudonymous key, UTC day; unique deduplication key |
| AnalyticsEvent | Product, event kind, time; no raw phone, message body, or arbitrary client payload |
| Conversation | Product, buyer, seller; unique product/buyer/seller tuple |
| Message | Conversation, sender, body, timestamp, recipient-read timestamp |
| Notification | Recipient, kind, title, message, internal destination, read timestamp |
| SaleConfirmation | Product, selected buyer, seller declaration, buyer confirmation; one sale per product |
| Review | Confirmed sale, reviewer, seller, rating 1–5, text, moderation state; unique sale/reviewer |
| Report | Reporter, target kind and id, reason, description, private resolution status |
| AdminAction | Admin, action, target, reason, timestamp; append-only through application interfaces |
| SearchHistory | Optional opt-in user query history with deletion and retention policy |

Index actual query paths: campus/status/date, seller/status, category, price, view counts where materialized, normalized identity fields, conversation/message time, recipient/unread, and report/status. Use eager loading for cards and seller summaries, bounded pagination, and aggregate queries for statistics. Enable foreign key enforcement on SQLite.

Migrations are the schema authority. Never run `create_all` at production startup. Test schema upgrades on both databases; SQLite success does not establish PostgreSQL support.

## Authentication and security

Use Werkzeug password hashing, password confirmation, bounded validated input, generic recovery responses, and expiring single-use tokens stored only as hashes. Verification and reset mail use configurable SMTP; development delivery must be explicitly enabled and must never silently operate in production.

The browser receives an opaque session cookie; persist only its hash server-side. Rotate on login and privilege changes. Check account status, expiry, and revocation on each protected request. Password reset/change revokes other sessions. Provide session listing and individual/all-other-session revocation. Deactivated accounts cannot authenticate; reactivation requires the documented recovery/admin process.

Cookies are HttpOnly, SameSite=Lax, and Secure in production. Configure absolute and idle session expiry. Apply CSRF to every mutation, including JSON requests and contact-click tracking. GET requests do not change business state, except documented deduplicated view telemetry.

Rate limits protect login, signup, reset requests, messaging, reporting, contact clicks, and uploads. Use shared Redis-backed rate-limit state for production processes; development may use memory with an explicit limitation. Avoid attacker-triggered permanent account locks.

Central authorization helpers enforce membership, ownership, conversation participation, review eligibility, and admin status. Never trust client-submitted seller, sender, reviewer, or user identifiers. Whitelist sort keys and filter names. Validate redirect destinations as local paths.

Jinja escapes user text; messages, reviews, descriptions, and bios remain plain text. Apply CSP restricted to local scripts/styles/assets, frame protection, nosniff, a conservative referrer policy, and HSTS in HTTPS production. Do not use inline executable scripts or third-party font/CDN dependencies. Configure proxy trust only for the known deployment topology.

Custom 400, 403, 404, 413, 429, and 500 pages show useful recovery actions without internals. Roll back failed transactions and log server-side errors without secrets, tokens, phone numbers, or message bodies.

## Marketplace and uploads

Listing lifecycle: draft → available ↔ reserved → sold; owner hiding and administrator removal are separate transitions. Moderated removal cannot be reversed by an owner. Sold listings remain identifiable but do not offer a misleading purchase contact action. Deletes are soft deletes where conversations/reports require history; storage cleanup uses an explicit retention policy.

Search uses SQLAlchemy queries across title, description, brand, category, campus, and city. Escape LIKE wildcards where literal search is intended. Combine category, city, condition, brand, price range, negotiable, and allowed status filters. Whitelist newest, oldest, price ascending/descending, most viewed, and relevance sorting with deterministic tie-breakers. Preserve query parameters across pages; cap page size. Debounced suggestions enforce the same visibility rules and result caps.

Image storage is accessed through a service interface. Accept a documented set of decoded raster formats, check extension/content agreement, bound total request size, image count, per-file size, dimensions, and pixel count. Re-encode images to strip metadata and reject malformed/decompression-bomb inputs. Generate opaque keys; never use user filenames as paths. Create bounded display and thumbnail variants.

Provide accessible file input plus drag/drop, previews, removal, reordering, and primary selection. Server validation remains authoritative. Stage new images, commit records, and clean abandoned staging files; do not delete currently referenced files before a successful commit. Image access checks membership and listing visibility rather than exposing the entire upload directory publicly.

Local development stores files on disk. The initial Render deployment uses a persistent disk for uploads on one application service; ephemeral filesystem storage is not acceptable. A later object-storage adapter can replace disk without changing marketplace routes. Document disk scaling and backup limitations explicitly.

## Contact privacy and messaging

Presentation uses an allowlisted profile view model. Hidden contact values never reach HTML, JSON, JavaScript, data attributes, logs, or analytics. Private profiles still provide the minimal seller identity needed by an authorized listing viewer, but do not expose the full profile or contact fields.

WhatsApp contact is available only for eligible viewers when the seller enables it. A CSRF-protected contact action rechecks privacy, normalizes the number, records a click, and redirects to `https://wa.me/<number>?text=<encoded message>`. Enabling WhatsApp necessarily reveals the number to a student who follows the link; explain this in the privacy setting. Turning it off removes the control and denies direct endpoint access.

Support Indian ten-digit mobile numbers by normalizing to country code 91; accept validated international E.164-style numbers. Reject ambiguous or malformed input instead of silently inventing a country code. WhatsApp clicks are clicks, not evidence of messages or completed purchases.

Internal messaging is text-only and associated with a listing. Only the buyer and seller may read or send. Enforce length bounds, rate limits, and account/campus eligibility. Use cursor-based short polling while the conversation is visible, back off on failure, and stop in background tabs. Document polling honestly. Notifications are written in the same transaction as the originating event; every read/mark-read operation is scoped to the recipient.

## Trust, reviews, moderation, analytics

To prevent arbitrary reviews, the seller selects a buyer from a legitimate listing conversation when recording a sale; the buyer confirms the exchange before submitting one seller review. This supports peer-confirmed reviews, not claims of payment verification. No self-review or duplicate review is allowed. Moderation can hide a review with an audit reason.

Reports support listing, user, and participant-visible message targets. Reporter-facing status excludes private moderator notes. Admin actions require server-side role checks and create an audit record. Suspension immediately prevents new sessions and invalidates active access; listing removal takes effect across discovery, suggestions, images, contact, and wishlist rendering.

Seller dashboards use actual counts of active/sold listings, deduplicated views, saves, conversation starts, and WhatsApp clicks, plus bounded date-series queries. Platform statistics use actual database aggregates and precise metric labels. View deduplication is once per eligible non-owner viewer/product/UTC day; document that it is not a perfect count of unique people.

## UI and 3D from the foundation

Visual direction: ink and warm-white surfaces, an electric mint accent, generous typography, fine borders, restrained glass panels, and consistent rounded cards. Use a local system font stack. Semantic HTML, visible focus, keyboard-operable galleries and dialogs, labeled fields, useful errors, minimum 44px primary touch targets, and WCAG AA contrast guide implementation.

The hero includes an isolated decorative depth layer from Phase 0. Use lightweight native WebGL geometry with no external assets or framework. An ES module loads only when the hero is visible, motion is allowed, and device conditions permit. CSS provides the static gradient/depth composition independently of JavaScript and WebGL.

The canvas is aria-hidden and has pointer-events disabled; content remains normal HTML above it. Cap pixel ratio and geometry complexity, target at most 30 frames/second, pause off-screen/background rendering, handle context loss, and release resources. Reduced-motion preference disables continuous animation and pointer parallax. Low-performance and mobile devices use the static fallback when needed. No marketplace route or form depends on the renderer.

Light/dark/system preference persists locally. An early local script applies the stored preference before painting where practical; CSS defaults honor system preferences if storage or JavaScript is unavailable. Renderer colors follow the selected theme. Filters become a keyboard-accessible drawer on small screens. Progressive enhancement preserves standard form submission for core workflows.

Performance targets to verify, not promises: no render-blocking 3D code; no external visual dependency; bounded thumbnail sizes; acceptable mobile interaction and layout stability; no continuous rendering when hidden. Measure under throttling before claiming performance acceptance.

## Deployment and operations

Render runs Gunicorn against `wsgi:app`, with PostgreSQL, shared rate-limit storage, persistent uploads, and SMTP configured through environment variables. Apply migrations once through a controlled release operation before starting compatible application code. Check Render's current disk/release constraints while implementing the manifest; do not assume a disk is mounted in build or pre-deploy processes.

Configuration includes SECRET_KEY, DATABASE_URL, APP_ENV, allowed hosts/base URL, SMTP settings, upload root/limits, and rate-limit storage URL. Fail production startup on missing secrets, insecure database mode, or incomplete required services. `.env.example` contains no usable credentials. Pin tested dependencies when creating the project.

Expose separate liveness and database readiness endpoints. Readiness failures return a generic 503 without connection details. Document database and file backup/restore together, migration rollback strategy, log retention, first-admin CLI provisioning, campus registration, and SMTP verification. Do not ship default admin credentials.

## Delivery and verification gates

Follow the supplied ten phases. At each phase, inspect the current project, implement only its scope, run relevant tests, resolve regressions, update documentation, and record what was actually verified.

| Phase | Deliverable and acceptance gate |
|---|---|
| 0 | Reviewed architecture; fresh runnable app factory, configuration shell, base UI/themes and isolated 3D/fallback, health endpoints, smoke tests, setup documentation. No fake marketplace actions |
| 1 | Models, Alembic migrations, database setup, authorization/security utilities, storage contracts; upgrade and constraint tests |
| 2 | Auth, verification/membership, recovery, sessions, profile/media/privacy; account and access-control tests |
| 3 | Categories, listing lifecycle, multiple images, discovery/search/filter/sort/pagination/details; CRUD, upload, campus isolation tests |
| 4 | Wishlist, views, contact redirects, conversations/polling, notifications; privacy and participation regression tests |
| 5 | Seller dashboard, trends, peer-confirmed sales/reviews, reports; metric correctness and eligibility tests |
| 6 | Admin tools, category/campus management, suspension, moderation, audit log; role and enforcement tests |
| 7 | Complete responsive visual system across all real screens; keyboard, contrast, reduced-motion, WebGL-off and mobile checks |
| 8 | Full pytest regression/security suite, PostgreSQL integration, migration upgrades, query/performance audit, browser flows A–F |
| 9 | Validated production configuration and Render files; deployment, storage, backup and troubleshooting documentation |

Tests cover successful behavior and denied behavior: CSRF, session revocation, cross-campus access, ownership, hidden phone/WhatsApp leakage, malicious filenames and image content, SQL-like inputs, escaped HTML, duplicate races, notification ownership, message access, review eligibility, inactive categories, and moderation enforcement.

Run the requested flows A–F with separate users and a real test database. Test from an empty database as well as after migrations. Keep all test fixtures isolated from production. Record SQLite and PostgreSQL results separately, and state when live deployment or external mail delivery has not been verified.

## Phase 0 design report

- Created this architecture proposal only; no previous XELO files were used.
- Database changes: none; entity relationships and invariants are proposed above.
- Security changes: none deployed; security boundaries are specified above.
- Tests added/run: none; application scaffolding has not started.
- Run instructions: no runnable application exists at this design-review stage.
- Outstanding product assumptions: verified single-campus membership and buyer-confirmed review eligibility.
- Next step after design review: write the Phase 0 implementation plan, then create and verify the fresh project skeleton under the required skill workflow.
