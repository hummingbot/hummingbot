import json
import signal
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from hummingbot.cli import bot
from hummingbot.cli.commands import status as status_mod
from hummingbot.cli.commands.status import _recent_log_errors, _request_fresh_snapshot, status


class RecentLogErrorsTest(unittest.TestCase):
    def test_counts_errors_and_keeps_last_messages(self):
        lines = [
            "2026-01-01 - 1 - x - INFO - all good",
            "2026-01-01 - 1 - x - ERROR - boom one",
            "2026-01-01 - 1 - x - CRITICAL - boom two",
            "2026-01-01 - 1 - x - ERROR - boom three",
        ]
        with patch.object(bot, "tail_lines", return_value=lines), \
                patch.object(bot, "structured_log_file", return_value=Path("/nonexistent.log")):
            errs = _recent_log_errors()
        self.assertEqual(errs["count"], 3)
        self.assertEqual(errs["messages"], ["boom one", "boom two", "boom three"])
        self.assertEqual(errs["window"], status_mod.ERROR_SCAN_LINES)

    def test_no_errors(self):
        with patch.object(bot, "tail_lines", return_value=["a - b - c - INFO - fine"]), \
                patch.object(bot, "structured_log_file", return_value=Path("/nonexistent.log")):
            errs = _recent_log_errors()
        self.assertEqual(errs["count"], 0)
        self.assertEqual(errs["messages"], [])


class RequestFreshSnapshotTest(unittest.TestCase):
    def test_returns_when_no_pid(self):
        with patch.object(bot, "read_pid", return_value=None), \
                patch("hummingbot.cli.commands.status.os") as os_mock:
            _request_fresh_snapshot()
        os_mock.kill.assert_not_called()

    def test_returns_when_pid_dead(self):
        with patch.object(bot, "read_pid", return_value=123), \
                patch.object(bot, "pid_alive", return_value=False), \
                patch("hummingbot.cli.commands.status.os") as os_mock:
            _request_fresh_snapshot()
        os_mock.kill.assert_not_called()

    def test_returns_when_process_vanishes_on_kill(self):
        with patch.object(bot, "read_pid", return_value=123), \
                patch.object(bot, "pid_alive", return_value=True), \
                patch.object(bot, "read_status", return_value={"updated_at": 1.0}), \
                patch("hummingbot.cli.commands.status.os") as os_mock:
            os_mock.kill.side_effect = ProcessLookupError
            _request_fresh_snapshot()
        os_mock.kill.assert_called_once_with(123, signal.SIGUSR1)

    def test_waits_until_snapshot_refreshes(self):
        # prev read, one stale poll (sleeps), then a fresh snapshot appears
        reads = [{"updated_at": 1.0}, {"updated_at": 1.0}, {"updated_at": 2.0}]
        with patch.object(bot, "read_pid", return_value=123), \
                patch.object(bot, "pid_alive", return_value=True), \
                patch.object(bot, "read_status", side_effect=reads) as read_status, \
                patch("hummingbot.cli.commands.status.os") as os_mock, \
                patch("hummingbot.cli.commands.status.time") as time_mock:
            time_mock.time.return_value = 0.0
            _request_fresh_snapshot(timeout=5.0)
        os_mock.kill.assert_called_once_with(123, signal.SIGUSR1)
        time_mock.sleep.assert_called_once_with(0.1)
        self.assertEqual(read_status.call_count, 3)

    def test_gives_up_at_deadline(self):
        with patch.object(bot, "read_pid", return_value=123), \
                patch.object(bot, "pid_alive", return_value=True), \
                patch.object(bot, "read_status", return_value=None), \
                patch("hummingbot.cli.commands.status.os"), \
                patch("hummingbot.cli.commands.status.time") as time_mock:
            time_mock.time.side_effect = [0.0, 1.0, 100.0]  # deadline calc, one loop pass, expiry
            _request_fresh_snapshot(timeout=5.0)
        time_mock.sleep.assert_called_once_with(0.1)


class StatusCommandTest(unittest.TestCase):
    def test_no_bot_and_nothing_loaded(self):
        with patch.object(bot, "exists", return_value=False), \
                patch.object(bot, "read_loaded", return_value=None), \
                patch("hummingbot.cli.commands.status.emit") as emit_mock:
            status(as_json=False)
        record = emit_mock.call_args.args[0]
        self.assertFalse(record["running"])
        self.assertEqual(record["note"], "no strategy config loaded")

    def test_no_bot_but_config_imported(self):
        with patch.object(bot, "exists", return_value=False), \
                patch.object(bot, "read_loaded", return_value={"file": "conf_x.yml", "type": "controller"}), \
                patch("hummingbot.cli.commands.status.emit") as emit_mock:
            status(as_json=True)
        record = emit_mock.call_args.args[0]
        self.assertEqual(record["note"], "imported, not started")
        self.assertEqual(record["config"], "conf_x.yml")
        self.assertEqual(record["type"], "controller")
        self.assertEqual(record["next"], "hbot start")

    def _running_patches(self, snapshot, meta, errors):
        return [
            patch.object(bot, "exists", return_value=True),
            patch.object(bot, "running", return_value=True),
            patch.object(bot, "read_status", return_value=snapshot),
            patch.object(bot, "read_meta", return_value=meta),
            patch.object(bot, "read_pid", return_value=4242),
            patch("hummingbot.cli.commands.status._request_fresh_snapshot"),
            patch("hummingbot.cli.commands.status._recent_log_errors", return_value=errors),
        ]

    def test_running_markdown_with_uptime_snapshot_and_errors(self):
        now = time.time()
        snapshot = {"updated_at": now - 3, "engine": {"strategy_name": "pmm"},
                    "format_status": "live status text", "balances": {"binance": {"BTC": 1}}}
        meta = {"name": "mybot", "file": "conf_x.yml", "type": "controller", "started_at": now - 60}
        errors = {"count": 2, "messages": ["first", "last err"], "window": 600}
        patches = self._running_patches(snapshot, meta, errors)
        echo_mock = MagicMock()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], \
                patch("hummingbot.cli.commands.status.echo", echo_mock):
            status(as_json=False)
        rendered = echo_mock.call_args_list[0].args[0]
        self.assertIn("state: running", rendered)
        self.assertIn("pid: 4242", rendered)
        self.assertIn("strategy: pmm", rendered)
        self.assertIn("uptime", rendered)
        self.assertIn("snapshot", rendered)
        self.assertIn("2 in last 600 log lines", rendered)
        self.assertIn("last err", rendered)
        # format_status is echoed as a second block
        self.assertIn("live status text", echo_mock.call_args_list[1].args[0])

    def test_running_json_output(self):
        now = time.time()
        snapshot = {"updated_at": now - 3, "engine": {"strategy_name": "pmm"},
                    "format_status": "txt", "balances": {"binance": {"BTC": 1}}}
        meta = {"name": "mybot", "file": "conf_x.yml", "type": "controller", "started_at": now - 60}
        errors = {"count": 0, "messages": [], "window": 600}
        patches = self._running_patches(snapshot, meta, errors)
        emit_mock = MagicMock()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], \
                patch("hummingbot.cli.commands.status.emit", emit_mock):
            status(as_json=True)
        payload = emit_mock.call_args.args[0]
        self.assertTrue(payload["running"])
        self.assertEqual(payload["name"], "mybot")
        self.assertEqual(payload["pid"], 4242)
        self.assertEqual(payload["strategy"], "pmm")
        self.assertGreater(payload["uptime_s"], 0)
        self.assertGreaterEqual(payload["snapshot_age_s"], 0)
        self.assertEqual(payload["balances"], {"binance": {"BTC": 1}})
        self.assertEqual(payload["format_status"], "txt")
        json.dumps(payload)  # payload must be JSON-serializable

    def test_stopped_bot_minimal_fields(self):
        # exists but not running, no snapshot, no errors, no format_status
        echo_mock = MagicMock()
        with patch.object(bot, "exists", return_value=True), \
                patch.object(bot, "running", return_value=False), \
                patch.object(bot, "read_status", return_value=None), \
                patch.object(bot, "read_meta", return_value={"name": "mybot"}), \
                patch.object(bot, "read_pid", return_value=None), \
                patch("hummingbot.cli.commands.status._request_fresh_snapshot"), \
                patch("hummingbot.cli.commands.status._recent_log_errors",
                      return_value={"count": 0, "messages": [], "window": 600}), \
                patch("hummingbot.cli.commands.status.echo", echo_mock):
            status(as_json=False)
        rendered = echo_mock.call_args.args[0]
        self.assertIn("state: stopped", rendered)
        self.assertIn("pid: -", rendered)
        self.assertNotIn("uptime", rendered)
        self.assertNotIn("errors", rendered)
        self.assertEqual(echo_mock.call_count, 1)  # no format_status block


if __name__ == "__main__":
    unittest.main()
