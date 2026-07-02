import io
import json
import unittest
from contextlib import redirect_stdout
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import typer
from typer.testing import CliRunner

from hummingbot.cli import bot
from hummingbot.cli.output import SortedCommandsGroup, cell, echo, emit, render_kv, render_table


class EmitTest(unittest.TestCase):
    def test_markdown_is_the_default_surface(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            emit({"a": 1}, "- a: 1", as_json=False)
        self.assertEqual(buf.getvalue().strip(), "- a: 1")

    def test_json_carries_raw_values_and_serializes_decimals(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            emit({"n": 7, "d": Decimal("1.5"), "rows": [{"x": True}]}, "ignored", as_json=True)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["n"], 7)          # numbers stay numbers
        self.assertEqual(payload["d"], "1.5")      # Decimal -> str (exact, no float drift)
        self.assertEqual(payload["rows"], [{"x": True}])


class RenderHelpersTest(unittest.TestCase):
    def test_cell_none_is_empty_string(self):
        self.assertEqual(cell(None), "")

    def test_cell_formats_bools_floats_and_escapes(self):
        self.assertEqual(cell(True), "yes")
        self.assertEqual(cell(False), "no")
        self.assertEqual(cell(0.5), "0.5")
        self.assertEqual(cell("a|b\nc"), "a\\|b c")

    def test_render_table_empty_rows(self):
        self.assertEqual(render_table([], title="Trades"), "## Trades\n\n_(none)_")

    def test_render_table_rows_and_column_selection(self):
        rows = [{"pair": "BTC-USDT", "amount": 1.5, "extra": "hidden"},
                {"pair": "ETH-USDT", "amount": None}]
        out = render_table(rows, columns=["pair", "amount"], title="Fills")
        lines = out.splitlines()
        self.assertEqual(lines[0], "## Fills")
        self.assertEqual(lines[2], "| pair | amount |")
        self.assertEqual(lines[3], "| --- | --- |")
        self.assertEqual(lines[4], "| BTC-USDT | 1.5 |")
        self.assertEqual(lines[5], "| ETH-USDT |  |")   # None -> empty cell
        self.assertNotIn("hidden", out)                  # unselected column dropped

    def test_render_table_defaults_columns_from_first_row(self):
        out = render_table([{"a": 1, "b": 2}])
        self.assertEqual(out.splitlines()[0], "| a | b |")

    def test_render_kv_empty_record(self):
        self.assertEqual(render_kv({}, title="Bot"), "## Bot\n\n_(empty)_")

    def test_echo_prints_to_stdout(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            echo("hello")
        self.assertEqual(buf.getvalue(), "hello\n")


class SortedCommandsGroupTest(unittest.TestCase):
    def test_help_lists_commands_alphabetically(self):
        app = typer.Typer(cls=SortedCommandsGroup)

        @app.command("zeta")
        def zeta():
            pass

        @app.command("alpha")
        def alpha():
            pass

        result = CliRunner().invoke(app, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertLess(result.stdout.index("alpha"), result.stdout.index("zeta"))


class StatusJsonTest(unittest.TestCase):
    def _invoke(self, args):
        from hummingbot.cli.commands.status import status
        app = typer.Typer()
        app.command("status")(status)
        return CliRunner().invoke(app, args)

    def test_status_json_empty_state_is_success(self):
        with TemporaryDirectory() as d, patch.object(bot, "bot_dir", return_value=Path(d)):
            result = self._invoke(["--json"])
        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["running"])

    def test_status_markdown_default_unchanged(self):
        with TemporaryDirectory() as d, patch.object(bot, "bot_dir", return_value=Path(d)):
            result = self._invoke([])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("- running: no", result.stdout)


class LogsJsonTest(unittest.TestCase):
    def _invoke(self, args, botdir):
        from hummingbot.cli.commands.logs import logs
        app = typer.Typer()
        app.command("logs")(logs)
        with patch.object(bot, "bot_dir", return_value=botdir):
            return CliRunner().invoke(app, args)

    def test_json_snapshot_of_lines(self):
        with TemporaryDirectory() as d:
            botdir = Path(d) / "bot"
            bot._atomic_write(botdir / "meta.json", json.dumps({"name": "x"}))
            (botdir / "bot.log").write_text("one\ntwo\n")
            with patch.object(bot, "structured_log_file", return_value=botdir / "nope.log"):
                result = self._invoke(["--json", "-n", "1"], botdir)
        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["lines"], ["two"])
        self.assertTrue(payload["file"].endswith("bot.log"))

    def test_json_refuses_follow(self):
        with TemporaryDirectory() as d:
            result = self._invoke(["--json", "--follow"], Path(d))
        self.assertEqual(result.exit_code, 4)  # CONFIG_ERROR, before any file resolution


if __name__ == "__main__":
    unittest.main()
