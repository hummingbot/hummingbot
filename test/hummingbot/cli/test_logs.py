import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import typer

from hummingbot.cli import bot
from hummingbot.cli.commands.logs import _resolve_log_file, logs
from hummingbot.cli.output import ExitCode


class ResolveLogFileTest(unittest.TestCase):
    def test_named_bot_found(self):
        with patch.object(bot, "structured_log_for", return_value=Path("/logs/logs_past.log")):
            self.assertEqual(_resolve_log_file("past"), Path("/logs/logs_past.log"))

    def test_named_bot_missing_exits_not_found(self):
        with patch.object(bot, "structured_log_for", return_value=None), \
                patch.object(bot, "list_bots", return_value=["a", "b"]):
            with self.assertRaises(typer.Exit) as ctx:
                _resolve_log_file("nope")
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.NOT_FOUND))

    def test_no_bot_exits_not_found(self):
        with patch.object(bot, "exists", return_value=False):
            with self.assertRaises(typer.Exit) as ctx:
                _resolve_log_file(None)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.NOT_FOUND))

    def test_prefers_structured_log(self):
        with TemporaryDirectory() as d:
            structured = Path(d) / "logs_mybot.log"
            structured.write_text("x\n")
            with patch.object(bot, "exists", return_value=True), \
                    patch.object(bot, "structured_log_file", return_value=structured):
                self.assertEqual(_resolve_log_file(None), structured)

    def test_falls_back_to_child_log(self):
        with TemporaryDirectory() as d:
            child = Path(d) / "bot.log"
            child.write_text("x\n")
            with patch.object(bot, "exists", return_value=True), \
                    patch.object(bot, "structured_log_file", return_value=Path(d) / "gone.log"), \
                    patch.object(bot, "log_file", return_value=child):
                self.assertEqual(_resolve_log_file(None), child)

    def test_no_log_files_returns_none(self):
        with TemporaryDirectory() as d:
            with patch.object(bot, "exists", return_value=True), \
                    patch.object(bot, "structured_log_file", return_value=Path(d) / "a.log"), \
                    patch.object(bot, "log_file", return_value=Path(d) / "b.log"):
                self.assertIsNone(_resolve_log_file(None))


class LogsCommandTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.log = Path(self._tmp.name) / "logs_mybot.log"
        self.log.write_text("one\ntwo\nthree\n")

    def test_json_with_follow_exits_config_error(self):
        with self.assertRaises(typer.Exit) as ctx:
            logs(name=None, lines=10, follow=True, as_json=True)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))

    def test_no_log_file_yet_exits_error(self):
        with patch("hummingbot.cli.commands.logs._resolve_log_file", return_value=None):
            with self.assertRaises(typer.Exit) as ctx:
                logs(name=None, lines=10, follow=False, as_json=False)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.ERROR))

    def test_snapshot_markdown(self):
        with patch("hummingbot.cli.commands.logs._resolve_log_file", return_value=self.log), \
                patch("hummingbot.cli.commands.logs.echo") as echo_mock:
            logs(name=None, lines=2, follow=False, as_json=False)
        printed = [c.args[0] for c in echo_mock.call_args_list]
        self.assertEqual(printed, ["two", "three"])

    def test_snapshot_json(self):
        with patch("hummingbot.cli.commands.logs._resolve_log_file", return_value=self.log), \
                patch("hummingbot.cli.commands.logs.emit") as emit_mock:
            logs(name=None, lines=200, follow=False, as_json=True)
        payload = emit_mock.call_args.args[0]
        self.assertEqual(payload["file"], str(self.log))
        self.assertEqual(payload["lines"], ["one", "two", "three"])
        self.assertTrue(emit_mock.call_args.args[2])

    def test_follow_streams_new_lines_until_interrupted(self):
        # First idle poll appends a new line to the file; second raises KeyboardInterrupt.
        def sleep_side_effect(_):
            if not getattr(sleep_side_effect, "appended", False):
                sleep_side_effect.appended = True
                with open(self.log, "a") as f:
                    f.write("four\n")
            else:
                raise KeyboardInterrupt

        with patch("hummingbot.cli.commands.logs._resolve_log_file", return_value=self.log), \
                patch("hummingbot.cli.commands.logs.time") as time_mock, \
                patch("hummingbot.cli.commands.logs.echo") as echo_mock:
            time_mock.sleep.side_effect = sleep_side_effect
            logs(name=None, lines=2, follow=True, as_json=False)
        printed = [c.args[0] for c in echo_mock.call_args_list]
        # tail of 2 lines, then the line appended while following
        self.assertEqual(printed, ["two", "three", "four"])
        self.assertEqual(time_mock.sleep.call_count, 2)


if __name__ == "__main__":
    unittest.main()
