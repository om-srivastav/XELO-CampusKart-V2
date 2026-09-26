# Operational boundaries

## Not deployed by this build
The project is Render-ready, not published to a live Render account. No cloud resources, domain, email provider, payments or third-party messaging services were provisioned. Set your real campus policy, SMTP identity and production secrets before launch.

## Schema and services
SQLite is the development default. PostgreSQL is mandatory in production. Redis provides shared limits across Gunicorn workers. Persistent local upload storage supports one web service. Do not increase service replicas until storage is shared.

## Release checks
1. Back up database and upload disk.
2. Verify deployment environment and dependencies.
3. Apply the reviewed migration once in pre-deploy.
4. Start application workers and inspect readiness.
5. Test signup delivery, login, upload, privacy and one buyer/seller exchange.
6. Confirm maintenance scheduling and restore procedures.

## Security behavior
Session identifiers and email tokens are hashed at rest. Password changes rotate the current session and revoke others; password recovery revokes all sessions. Changing/resetting a password consumes all outstanding reset links. Confirmed sale assignments are protected by conditional database updates. Hidden profiles suppress listing contacts. Thumbnail failure cleans both variants.

Admin role assignment is a trusted CLI operation. Admin routes can verify membership, suspend/reactivate accounts, moderate listings/reviews/reports, and manage categories/campuses. Every such action writes an audit record. Ordinary users cannot change their own campus or role.

## Data model decisions
User, profile, campus membership and contact preferences are combined into the User row. Product contains sale confirmation fields instead of a separate SaleConfirmation table. This is intentional and keeps the current single-campus account model small. Add a membership-history table before introducing campus transfers.

## Accessibility and rendering
Semantic forms and links support core workflows without JavaScript. Upload previews, client-side reordering, gallery selection, native sharing, the mobile filter dialog and message polling enhance those pages. Native file inputs and server-side validation remain authoritative. Reduced motion prevents loading the animated WebGL renderer. Main content never lives inside a canvas.

## Resource ceilings
Listings: 12 per page; messages: 40 initial/older and up to 100 per polling cursor; notifications: 20 per page; admin records: 25 per page. Admin statistics and seller trends use SQL aggregates. The current seller status notification loop is capped at 1,000 watchers per action; add an outbox worker before scaling beyond that threshold.

## Testing provenance
Automated tests use isolated SQLite or explicitly named disposable PostgreSQL databases. Browser fixtures use QA-prefixed records in a separate local database. Source archives exclude databases, secrets, uploads, virtual environments, caches and QA screenshots.
