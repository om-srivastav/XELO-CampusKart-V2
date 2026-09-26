# Verification record

Date: 2026-09-26. Application built from scratch in this task.

## Completed verification

- Full pytest integration/security suite on SQLite.
- The same suite on a real local PostgreSQL 18.4 server; not merely SQL dialect compilation.
- Initial migration upgrade, downgrade, re-upgrade and no-drift check on SQLite/PostgreSQL.
- Real Microsoft Edge browser flows using isolated QA data: profile editing; listing/image publish; database search; wishlist; seller/buyer messaging and polled reply; reserve/sell; buyer confirmation; review; report; admin listing removal.
- WhatsApp button browser navigation through the real authenticated POST endpoint, including CSP handling; no message sent.
- Desktop/mobile screenshots inspected, light/dark preference persistence, reduced motion disabling the WebGL module, WebGL-unavailable static fallback, and no-JavaScript login.
- Five main pages checked for horizontal overflow at 320, 390, 768 and 1440 pixels.
- Mobile filter dialog opens, closes with Escape and restores focus.
- Ruff lint and runtime dependency vulnerability audit.

Final counts and artifact checksum are recorded in the delivery ledger after the last run.

## Independent review

A separate reviewer inspected auth, authorization, privacy, uploads and listing lifecycle. Reproducing tests confirmed and then verified fixes for:
1. Reassignment of a buyer after sale confirmation.
2. Contact disclosure from private profiles.
3. Outstanding password-reset links surviving password changes or resets.
4. Original-image leakage when thumbnail storage fails.

Further verification found and fixed invalid-host error rendering, WhatsApp navigation blocked by CSP, production rate-limit backend override, and a search-history ORM attribute collision. Current tests cover these regressions.

## What these results do not claim

- The application has not been deployed to Render.
- No live SMTP provider, custom domain, production Redis instance, or production backup restoration was exercised.
- The included GitHub Actions workflow has not run on a hosted repository.
- Accessibility checks are practical browser/keyboard checks, not a formal certification.
- No sustained production-load test or external penetration test was performed.
- Browser fixture accounts and listing images are QA data, isolated from the normal empty marketplace.
