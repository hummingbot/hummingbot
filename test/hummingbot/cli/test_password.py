import io
import sys
import unittest
from unittest.mock import patch

import typer

from hummingbot.cli.password import resolve_password


class PasswordResolveTest(unittest.TestCase):
    def test_env_var(self):
        with patch.dict("os.environ", {"HBOT_PASSWORD": "secret"}, clear=True):
            self.assertEqual(resolve_password(password_stdin=False, json_output=False), "secret")

    def test_config_password_fallback(self):
        with patch.dict("os.environ", {"CONFIG_PASSWORD": "legacy"}, clear=True):
            self.assertEqual(resolve_password(password_stdin=False, json_output=False), "legacy")

    def test_stdin(self):
        with patch.dict("os.environ", {}, clear=True), \
                patch.object(sys, "stdin", io.StringIO("frompipe\n")):
            self.assertEqual(resolve_password(password_stdin=True, json_output=False), "frompipe")

    def test_stdin_empty_fails(self):
        with patch.dict("os.environ", {}, clear=True), \
                patch.object(sys, "stdin", io.StringIO("\n")):
            with self.assertRaises(typer.Exit):
                resolve_password(password_stdin=True, json_output=False)

    def test_no_source_non_tty_fails(self):
        # StringIO.isatty() is False, so with no stdin flag and no env we must fail (not hang).
        with patch.dict("os.environ", {}, clear=True), \
                patch.object(sys, "stdin", io.StringIO("")):
            with self.assertRaises(typer.Exit):
                resolve_password(password_stdin=False, json_output=False)

    def test_hidden_prompt_used_for_tty(self):
        with patch.dict("os.environ", {}, clear=True), \
                patch.object(sys.stdin, "isatty", return_value=True), \
                patch("hummingbot.cli.password.getpass.getpass", return_value="typed"):
            self.assertEqual(resolve_password(password_stdin=False, json_output=False), "typed")


if __name__ == "__main__":
    unittest.main()
