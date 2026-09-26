# XELO implementation plan

Spec: architecture.md (approved in the task).
Execution: native, continuous; user explicitly requested no intermediate approval stops.

## Constraints and interfaces

Python 3.11+, Flask app factory `create_app(config=None)`, SQLAlchemy `db`, Jinja, vanilla JS; no V1 code. Domain routes use `/auth`, `/profile`, `/market`, `/messages`, `/notifications`, `/dashboard`, `/admin`. Services enforce campus and ownership constraints. Models use portable SQL and named constraints. All mutations require CSRF. Production services are configured, never simulated.

## Tasks

- [x] 0: Write smoke tests for homepage, health, headers and fail-closed production configuration. Observe missing app failure. Implement app factory, configuration, shared templates, theme and isolated depth renderer. Run pytest.
- [x] 1: Write persistence/constraint tests, implement identity, catalog and interaction models, generate initial Alembic migration and test empty upgrade. Run pytest.
- [x] 2: Test signup/login/verification/session revocation/privacy; implement auth, SMTP/development mail, profile and secure image services. Run pytest.
- [x] 3: Test owner CRUD, uploads, campus visibility, filters/sort/pagination; implement marketplace and listing forms/gallery. Run pytest.
- [x] 4: Test view deduplication, wishlist uniqueness, WhatsApp privacy, conversation authorization and notifications; implement transactional workflows and polling. Run pytest.
- [x] 5: Test buyer-confirmed reviews, report privacy and real dashboard aggregates; implement dashboards, review and report workflows. Run pytest.
- [x] 6: Test admin boundaries, suspension and removal effects; implement audited moderation, categories and campus controls. Run pytest.
- [x] 7: Verify full page templates, responsive layouts, themes, reduced-motion, controls and real empty states in browser. Fix observed UI issues.
- [x] 8: Run full regression, security/authorization tests, migration upgrade/downgrade, dependency audit and available PostgreSQL checks; independent code review and fixes.
- [x] 9: Add Render configuration, pinned requirements, environment examples, operational commands and README; package source and final verification report.

## Review focus

1. Direct URL requests must enforce campus/privacy rules as strongly as navigation.
2. Suspended owners and removed listings must disappear from contacts, images and suggestions.
3. Failed image decoding/database writes must not corrupt existing images.
4. CSRF, invalid form values, empty databases and unavailable external services must fail clearly.
5. Polling pagination, hidden tabs, reduced motion and mobile widths must preserve usability.

Each feature starts with executable behavior tests and is checked with `python -m pytest -q`. Test expected HTTP statuses, persisted values, authorization failures and escaped output rather than implementation structure. Phase reports and rulings go in progress.md. The project itself is a fresh isolated directory, not an existing repository needing a worktree.
