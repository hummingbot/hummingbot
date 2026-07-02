import unittest
from unittest.mock import patch

from typer.testing import CliRunner

import hummingbot.cli.main as main_mod
from hummingbot.cli.main import _version, app


class MainAppTest(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_help_lists_all_commands(self):
        result = self.runner.invoke(app, ["--help"])
        self.assertEqual(result.exit_code, 0)
        for command in ("balance", "config", "connect", "create", "deploy", "history",
                        "import", "logs", "start", "status", "stop"):
            self.assertIn(command, result.output)

    def test_no_args_shows_help(self):
        result = self.runner.invoke(app, [])
        self.assertIn("Usage", result.output)

    def test_version_flag(self):
        result = self.runner.invoke(app, ["--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.output.startswith("hbot "))
        self.assertNotIn("unknown", result.output)  # the real VERSION file is readable

    def test_version_helper_reads_version_file(self):
        version = _version()
        self.assertTrue(version)
        self.assertNotEqual(version, "unknown")

    def test_version_helper_tolerates_unreadable_file(self):
        with patch("pathlib.Path.read_text", side_effect=OSError("denied")):
            self.assertEqual(_version(), "unknown")

    def test_root_callback_without_version_is_a_no_op(self):
        self.assertIsNone(main_mod._root(version=None))

    def test_main_entrypoint_invokes_the_app(self):
        with patch.object(main_mod, "app") as mock_app:
            main_mod.main()
        mock_app.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
