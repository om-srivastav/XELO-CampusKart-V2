"""Provider contract tests: no network or real delivery is performed."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx

from app.services.mail import MailDeliveryError, _deliver, send_token


class MailProviderTests(unittest.TestCase):
    def settings(self, provider="resend", **overrides):
        values = dict(
            MAIL_PROVIDER=provider,
            MAIL_API_KEY="test-secret",
            MAIL_FROM="Xelo <sender@example.test>",
            BASE_URL="https://xelo.example.test",
            APP_ENV="development",
            MAIL_FOLDER="unused",
        )
        values.update(overrides)
        return SimpleNamespace(**values)

    @patch("app.services.mail.httpx.Client")
    def test_resend_contract(self, client):
        transport = client.return_value.__enter__.return_value
        transport.post.return_value.status_code = 202
        _deliver("reader@example.test", "Reset", "Safe body", self.settings())
        args, kwargs = transport.post.call_args
        self.assertEqual(args, ("https://api.resend.com/emails",))
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer test-secret"})
        self.assertEqual(kwargs["json"]["to"], ["reader@example.test"])
        self.assertEqual(kwargs["json"]["text"], "Safe body")
        self.assertFalse(client.call_args.kwargs["follow_redirects"])
        self.assertEqual(client.call_args.kwargs["timeout"].connect, 5.0)

    @patch("app.services.mail.httpx.Client")
    def test_brevo_contract(self, client):
        transport = client.return_value.__enter__.return_value
        transport.post.return_value.status_code = 201
        _deliver("reader@example.test", "Reset", "Safe body", self.settings("brevo"))
        args, kwargs = transport.post.call_args
        self.assertEqual(args, ("https://api.brevo.com/v3/smtp/email",))
        self.assertEqual(kwargs["headers"], {"api-key": "test-secret"})
        self.assertEqual(kwargs["json"]["sender"], {"name": "Xelo", "email": "sender@example.test"})
        self.assertEqual(kwargs["json"]["textContent"], "Safe body")

    @patch("app.services.mail.httpx.Client")
    def test_rejections_and_network_failures_are_redacted(self, client):
        transport = client.return_value.__enter__.return_value
        for status in (302, 400, 429, 500):
            transport.post.return_value.status_code = status
            with self.assertRaisesRegex(MailDeliveryError, "rejected delivery"):
                _deliver("reader@example.test", "Reset", "token-secret", self.settings())
        transport.post.side_effect = httpx.ConnectError("private-token-or-key")
        with self.assertRaises(MailDeliveryError) as error:
            _deliver("reader@example.test", "Reset", "token-secret", self.settings())
        self.assertNotIn("private-token-or-key", str(error.exception))

    def test_file_mail_is_development_only(self):
        with tempfile.TemporaryDirectory() as folder:
            _deliver(
                "reader@example.test", "Reset", "A reset link", self.settings("file", MAIL_FOLDER=folder)
            )
            files = list(Path(folder).glob("*.eml"))
            self.assertEqual(len(files), 1)
            self.assertIn("A reset link", files[0].read_text())
            with self.assertRaises(MailDeliveryError):
                _deliver(
                    "reader@example.test",
                    "Reset",
                    "Secret",
                    self.settings("file", APP_ENV="production", MAIL_FOLDER=folder),
                )
            self.assertEqual(len(list(Path(folder).glob("*.eml"))), 1)

    @patch("app.services.mail._deliver")
    def test_token_digest_and_delivery_transaction(self, deliver):
        db = MagicMock()
        user = SimpleNamespace(id=42, email="reader@example.test")
        with patch("app.services.mail.secrets.token_urlsafe", return_value="raw-token"):
            send_token(user, "reset", db, self.settings())
        token = db.add.call_args.args[0]
        self.assertEqual(token.user_id, 42)
        self.assertNotEqual(token.token_hash, "raw-token")
        self.assertEqual(len(token.token_hash), 64)
        self.assertIn("https://xelo.example.test/auth/reset/raw-token", deliver.call_args.args[2])
        db.commit.assert_called_once()
        db.rollback.assert_not_called()
        db.reset_mock()
        deliver.side_effect = MailDeliveryError("Mail provider is unavailable.")
        with self.assertRaises(MailDeliveryError):
            send_token(user, "reset", db, self.settings())
        db.rollback.assert_called_once()
        db.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
