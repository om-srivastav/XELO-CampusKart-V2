# Native FastAPI architecture
FastAPI APIRouters call explicit services with request-scoped synchronous SQLAlchemy sessions from Depends(get_db). Jinja2Templates render the preserved UI. SQLAlchemy DeclarativeBase preserves the original 18-table schema; direct Alembic owns schema changes.

Starlette signed cookies hold browser state and reference hashed database sessions supporting expiry/revocation. Unsafe requests require session-bound expiring CSRF tokens. Redis backs production limits, with memory only for development. Middleware bounds request bodies, validates hosts and applies security headers.

Storage is accessed through get_storage and an adapter protocol; the included local implementation sanitizes images and thumbnails. Mail uses HTTP provider adapters or development files. Settings are environment based and reject incomplete production security configuration.

See MIGRATION-MAP.md for component mapping, route-map.json for original route contracts, MIGRATION-REPORT.md for evidence and limitations, and ../README.md for operation.
