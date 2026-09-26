# Browser QA

Start from the project root. Install Python development requirements and optional Node devDependencies. Run `npx playwright install chromium`, then `python tests/qa_server.py`. In a second terminal, run `npm run test:browser`.

The server listens on localhost:5001 and uses only `instance/browser-qa.db` and `instance/qa-uploads`. It creates clearly identified QA accounts with a public test-only password. These accounts never exist in the normal database. Do not run the QA server on a public interface.

The script runs seller, buyer and moderator sessions, publishes a QA listing with an image, searches/saves/messages, verifies a polled reply, records a sale, confirms/reviews it, reports it and removes it through moderation. It also checks theme persistence, mobile width, reduced-motion script loading and login without JavaScript.

Screenshots are saved to `tests/artifacts`. The normal test intercepts WhatsApp's destination and validates the server redirect without sending a WhatsApp message. A browser may follow WhatsApp's redirect chain before interception; no message is ever submitted. Do not use a real person's number in fixtures.

Set `BROWSER_CHANNEL=msedge` to use an installed Microsoft Edge instead of bundled Chromium. The Node dependency is not part of XELO's runtime.
