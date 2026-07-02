import signal
import unittest
from unittest.mock import call, patch

import typer

from hummingbot.cli import bot
from hummingbot.cli.commands.stop import stop
from hummingbot.cli.output import ExitCode


class StopCommandTest(unittest.TestCase):
    def test_no_bot_exits_not_found(self):
        with patch.object(bot, "exists", return_value=False):
            with self.assertRaises(typer.Exit) as ctx:
                stop(timeout=30.0, force=False, as_json=False)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.NOT_FOUND))

    def test_no_pid_exits_not_running_and_clears_pid(self):
        with patch.object(bot, "exists", return_value=True), \
                patch.object(bot, "read_pid", return_value=None), \
                patch.object(bot, "clear_pid") as clear_pid:
            with self.assertRaises(typer.Exit) as ctx:
                stop(timeout=30.0, force=False, as_json=False)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.NOT_RUNNING))
        clear_pid.assert_called_once()

    def test_dead_pid_exits_not_running(self):
        with patch.object(bot, "exists", return_value=True), \
                patch.object(bot, "read_pid", return_value=4242), \
                patch.object(bot, "pid_alive", return_value=False), \
                patch.object(bot, "clear_pid") as clear_pid:
            with self.assertRaises(typer.Exit) as ctx:
                stop(timeout=30.0, force=False, as_json=False)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.NOT_RUNNING))
        clear_pid.assert_called_once()

    def test_graceful_stop(self):
        # alive on the initial check, dead on the first poll after SIGTERM
        with patch.object(bot, "exists", return_value=True), \
                patch.object(bot, "read_pid", return_value=4242), \
                patch.object(bot, "pid_alive", side_effect=[True, False, False]), \
                patch.object(bot, "clear_pid") as clear_pid, \
                patch("hummingbot.cli.commands.stop.os") as os_mock, \
                patch("hummingbot.cli.commands.stop.time") as time_mock, \
                patch("hummingbot.cli.commands.stop.emit") as emit_mock:
            time_mock.time.return_value = 0.0
            stop(timeout=30.0, force=False, as_json=False)
        os_mock.kill.assert_called_once_with(4242, signal.SIGTERM)
        time_mock.sleep.assert_not_called()
        clear_pid.assert_called_once()
        self.assertEqual(emit_mock.call_args.args[0], {"stopped": True, "killed": False})

    def test_timeout_without_force_exits_timeout(self):
        # stays alive through one poll (sleep), then the deadline expires
        with patch.object(bot, "exists", return_value=True), \
                patch.object(bot, "read_pid", return_value=4242), \
                patch.object(bot, "pid_alive", return_value=True), \
                patch.object(bot, "clear_pid") as clear_pid, \
                patch("hummingbot.cli.commands.stop.os") as os_mock, \
                patch("hummingbot.cli.commands.stop.time") as time_mock:
            time_mock.time.side_effect = [0.0, 1.0, 100.0]  # deadline calc, one loop pass, expiry
            with self.assertRaises(typer.Exit) as ctx:
                stop(timeout=30.0, force=False, as_json=False)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.TIMEOUT))
        os_mock.kill.assert_called_once_with(4242, signal.SIGTERM)
        time_mock.sleep.assert_called_once_with(0.5)
        clear_pid.assert_not_called()

    def test_force_kills_after_timeout(self):
        with patch.object(bot, "exists", return_value=True), \
                patch.object(bot, "read_pid", return_value=4242), \
                patch.object(bot, "pid_alive", return_value=True), \
                patch.object(bot, "clear_pid") as clear_pid, \
                patch("hummingbot.cli.commands.stop.os") as os_mock, \
                patch("hummingbot.cli.commands.stop.time") as time_mock, \
                patch("hummingbot.cli.commands.stop.emit") as emit_mock:
            time_mock.time.side_effect = [0.0, 100.0]  # deadline calc, immediate expiry
            stop(timeout=30.0, force=True, as_json=True)
        self.assertEqual(os_mock.kill.call_args_list,
                         [call(4242, signal.SIGTERM), call(4242, signal.SIGKILL)])
        clear_pid.assert_called_once()
        record = emit_mock.call_args.args[0]
        self.assertEqual(record, {"stopped": True, "killed": True})
        self.assertTrue(emit_mock.call_args.args[2])  # as_json passed through


if __name__ == "__main__":
    unittest.main()
