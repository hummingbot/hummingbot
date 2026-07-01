import io
import sys
import unittest
from unittest.mock import MagicMock, patch

import typer

import hummingbot.cli.password as pw
from hummingbot.cli.password import resolve_password


class PasswordResolveTest(unittest.TestCase):
    def test_env_var(self):
        with patch.dict("os.environ", {"HBOT_PASSWORD": "secret"}, clear=True):
            self.assertEqual(resolve_password(password_stdin=False), "secret")

    def test_config_password_fallback(self):
        with patch.dict("os.environ", {"CONFIG_PASSWORD": "legacy"}, clear=True):
            self.assertEqual(resolve_password(password_stdin=False), "legacy")

    def test_stdin(self):
        with patch.dict("os.environ", {}, clear=True), \
                patch.object(sys, "stdin", io.StringIO("frompipe\n")):
            self.assertEqual(resolve_password(password_stdin=True), "frompipe")

    def test_stdin_empty_fails(self):
        with patch.dict("os.environ", {}, clear=True), \
                patch.object(sys, "stdin", io.StringIO("\n")):
            with self.assertRaises(typer.Exit):
                resolve_password(password_stdin=True)

    def test_no_source_non_tty_fails(self):
        # StringIO.isatty() is False, so with no stdin flag and no env we must fail (not hang).
        with patch.dict("os.environ", {}, clear=True), \
                patch.object(sys, "stdin", io.StringIO("")):
            with self.assertRaises(typer.Exit):
                resolve_password(password_stdin=False)

    def test_hidden_prompt_used_for_tty(self):
        with patch.dict("os.environ", {}, clear=True), \
                patch.object(sys.stdin, "isatty", return_value=True), \
                patch("hummingbot.cli.password.getpass.getpass", return_value="typed"):
            self.assertEqual(resolve_password(password_stdin=False), "typed")


class LoginFirstRunTest(unittest.TestCase):
    """`login` must initialize the keystore on a brand-new install (the first password provided becomes
    the keystore password) instead of tripping over the missing .password_verification file."""

    def _run_login(self, new_password_required: bool):
        with patch.object(pw, "resolve_password", return_value="pw"), \
                patch("hummingbot.client.config.config_helpers.load_client_config_map_from_file", return_value={}), \
                patch("hummingbot.client.config.config_crypt.ETHKeyFileSecretManger", return_value=MagicMock()), \
                patch("hummingbot.client.config.config_crypt.store_password_verification") as store, \
                patch("hummingbot.client.config.security.Security") as security:
            security.new_password_required.return_value = new_password_required
            security.login.return_value = True
            pw.login()
            return store, security

    def test_first_run_initializes_keystore(self):
        store, security = self._run_login(new_password_required=True)
        store.assert_called_once()       # the keystore is created from the first password
        security.login.assert_called_once()

    def test_existing_keystore_not_reinitialized(self):
        store, security = self._run_login(new_password_required=False)
        store.assert_not_called()        # an existing keystore is never overwritten
        security.login.assert_called_once()

    def test_unlock_keystore_first_run(self):
        # unlock_keystore() is the first-run-safe path login() delegates to; verify it inits the keystore.
        with patch("hummingbot.client.config.config_crypt.ETHKeyFileSecretManger", return_value=MagicMock()), \
                patch("hummingbot.client.config.config_crypt.store_password_verification") as store, \
                patch("hummingbot.client.config.security.Security") as security:
            security.new_password_required.return_value = True
            security.login.return_value = True
            pw.unlock_keystore("pw")
            store.assert_called_once()
            security.login.assert_called_once()


if __name__ == "__main__":
    unittest.main()
