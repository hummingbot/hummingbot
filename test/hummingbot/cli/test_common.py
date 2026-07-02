import io
import sys
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import typer

from hummingbot.cli import bot
from hummingbot.cli.commands._common import one_type, position_dict, read_json_object_from_stdin, resolve_db_for_command
from hummingbot.cli.output import ExitCode


class OneTypeTest(unittest.TestCase):
    def test_single_flag_returns_its_type(self):
        self.assertEqual(one_type(True, False, False, required=False), "v1-strategy")
        self.assertEqual(one_type(False, True, False, required=False), "v2-script")
        self.assertEqual(one_type(False, False, True, required=False), "controller")

    def test_no_flag_optional_returns_none(self):
        self.assertIsNone(one_type(False, False, False, required=False))

    def test_multiple_flags_fail_config_error(self):
        with self.assertRaises(typer.Exit) as ctx:
            one_type(True, False, True, required=False)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))

    def test_no_flag_required_fails_config_error(self):
        with self.assertRaises(typer.Exit) as ctx:
            one_type(False, False, False, required=True)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))


class PositionDictTest(unittest.TestCase):
    def _position(self, amount="2", upnl="10"):
        return SimpleNamespace(trading_pair="BTC-USDT",
                               position_side=SimpleNamespace(name="LONG"),
                               amount=Decimal(amount),
                               entry_price=Decimal("100"),
                               unrealized_pnl=Decimal(upnl),
                               leverage=Decimal("5"))

    def test_mark_price_derived_from_upnl(self):
        d = position_dict(self._position())
        self.assertEqual(d["trading_pair"], "BTC-USDT")
        self.assertEqual(d["side"], "LONG")
        self.assertEqual(d["entry_price"], 100.0)
        self.assertEqual(d["mark_price"], 105.0)   # entry + upnl/amount
        self.assertEqual(d["value"], 210.0)        # |amount| * mark
        self.assertEqual(d["notional"], 200.0)     # |amount| * entry
        self.assertEqual(d["unrealized_pnl"], 10.0)
        self.assertEqual(d["leverage"], 5)

    def test_zero_amount_uses_entry_as_mark(self):
        d = position_dict(self._position(amount="0", upnl="0"))
        self.assertEqual(d["mark_price"], 100.0)   # no division by zero
        self.assertEqual(d["value"], 0.0)

    def test_side_falls_back_to_str_without_name(self):
        p = self._position()
        p.position_side = "SHORT"
        self.assertEqual(position_dict(p)["side"], "SHORT")


class ReadJsonStdinTest(unittest.TestCase):
    def test_valid_object(self):
        with patch.object(sys, "stdin", io.StringIO('{"a": 1}')):
            self.assertEqual(read_json_object_from_stdin(), {"a": 1})

    def test_empty_stdin_is_empty_object(self):
        with patch.object(sys, "stdin", io.StringIO("  \n")):
            self.assertEqual(read_json_object_from_stdin(), {})

    def test_invalid_json_fails_config_error(self):
        with patch.object(sys, "stdin", io.StringIO("{oops")):
            with self.assertRaises(typer.Exit) as ctx:
                read_json_object_from_stdin()
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))

    def test_non_object_fails_config_error(self):
        with patch.object(sys, "stdin", io.StringIO("[1, 2]")):
            with self.assertRaises(typer.Exit) as ctx:
                read_json_object_from_stdin()
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))


class ResolveDbForCommandTest(unittest.TestCase):
    def test_named_bot_resolves_its_db_with_no_filter(self):
        with patch.object(bot, "db_path_for", return_value="/data/past.sqlite"):
            self.assertEqual(resolve_db_for_command("past"), ("/data/past.sqlite", None, False))

    def test_named_bot_without_db_fails_not_found(self):
        with patch.object(bot, "db_path_for", return_value=None), \
                patch.object(bot, "list_bots", return_value=["a", "b"]):
            with self.assertRaises(typer.Exit) as ctx:
                resolve_db_for_command("ghost")
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.NOT_FOUND))

    def test_no_bot_started_fails_not_found(self):
        with patch.object(bot, "exists", return_value=False):
            with self.assertRaises(typer.Exit) as ctx:
                resolve_db_for_command(None)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.NOT_FOUND))

    def test_current_bot_without_db_fails_error(self):
        with patch.object(bot, "exists", return_value=True), \
                patch.object(bot, "resolve_db_path", return_value=None):
            with self.assertRaises(typer.Exit) as ctx:
                resolve_db_for_command(None)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.ERROR))

    def test_current_bot_reports_db_filter_and_running(self):
        with patch.object(bot, "exists", return_value=True), \
                patch.object(bot, "resolve_db_path", return_value="/data/n.sqlite"), \
                patch.object(bot, "read_pid", return_value=123), \
                patch.object(bot, "pid_alive", return_value=True), \
                patch.object(bot, "config_file_path", return_value="conf_x.yml"):
            self.assertEqual(resolve_db_for_command(None), ("/data/n.sqlite", "conf_x.yml", True))

    def test_current_bot_not_running_without_pid(self):
        with patch.object(bot, "exists", return_value=True), \
                patch.object(bot, "resolve_db_path", return_value="/data/n.sqlite"), \
                patch.object(bot, "read_pid", return_value=None), \
                patch.object(bot, "config_file_path", return_value=None):
            self.assertEqual(resolve_db_for_command(None), ("/data/n.sqlite", None, False))


if __name__ == "__main__":
    unittest.main()
