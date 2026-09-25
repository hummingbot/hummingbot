import io
import json
import sys
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import typer

from hummingbot.cli import bot, strategy_configs as sc
from hummingbot.cli.commands import start as start_mod
from hummingbot.cli.output import ExitCode


class LogTailTest(unittest.TestCase):
    def test_combines_both_logs_and_keeps_last_n(self):
        with patch.object(bot, "structured_log_file", return_value=Path("/s.log")), \
                patch.object(bot, "log_file", return_value=Path("/b.log")), \
                patch.object(bot, "tail_lines", side_effect=[["a", "b"], ["c", "d"]]):
            self.assertEqual(start_mod._log_tail(3), "b\nc\nd")


class ReplaceRunningTest(unittest.TestCase):
    def test_no_pid_is_a_noop(self):
        with patch.object(bot, "read_pid", return_value=None), \
                patch("hummingbot.cli.commands.start.os.kill") as kill:
            start_mod._replace_running(timeout=1.0)
        kill.assert_not_called()

    def test_dead_pid_clears_state(self):
        with patch.object(bot, "read_pid", return_value=123), \
                patch.object(bot, "clear_pid") as clear, \
                patch("hummingbot.cli.commands.start.os.kill", side_effect=ProcessLookupError):
            start_mod._replace_running(timeout=1.0)
        clear.assert_called_once()

    def test_stops_within_timeout(self):
        with patch.object(bot, "read_pid", return_value=123), \
                patch.object(bot, "pid_alive", return_value=False), \
                patch.object(bot, "clear_pid") as clear, \
                patch("hummingbot.cli.commands.start.os.kill") as kill:
            start_mod._replace_running(timeout=5.0)
        kill.assert_called_once()
        clear.assert_called_once()

    def test_still_alive_at_deadline_fails_with_timeout_code(self):
        fake_time = MagicMock()
        fake_time.time.side_effect = [0.0, 1.0, 100.0]  # deadline=30; one poll, then past deadline
        with patch.object(bot, "read_pid", return_value=123), \
                patch.object(bot, "pid_alive", return_value=True), \
                patch.object(bot, "clear_pid") as clear, \
                patch("hummingbot.cli.commands.start.os.kill"), \
                patch("hummingbot.cli.commands.start.time", fake_time):
            with self.assertRaises(typer.Exit) as ctx:
                start_mod._replace_running(timeout=30.0)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.TIMEOUT))
        fake_time.sleep.assert_called_once_with(0.5)
        clear.assert_not_called()


class LaunchTest(unittest.TestCase):
    """launch() with the engine spawn fully mocked — no process, no fs outside a tempdir."""

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.tmp = Path(self.stack.enter_context(TemporaryDirectory()))
        self.stack.enter_context(patch.object(bot, "bot_dir", return_value=self.tmp / "bot"))
        self.write_loaded = self.stack.enter_context(patch.object(bot, "write_loaded"))
        self.write_meta = self.stack.enter_context(patch.object(bot, "write_meta"))
        self.stack.enter_context(patch.object(bot, "running", return_value=False))
        self.login = self.stack.enter_context(
            patch("hummingbot.cli.commands.start.login", return_value=("keystore", "pw")))
        self.spawn = self.stack.enter_context(
            patch("hummingbot.cli.commands.start._spawn_detached",
                  return_value={"name": "n", "pid": 1, "status": "running"}))

    def test_v1_strategy_uses_config_flag(self):
        with patch.object(sc, "resolve_config_type", return_value="v1-strategy") as resolve:
            record = start_mod.launch(file="conf_v1.yml")
        resolve.assert_called_once_with("conf_v1.yml", None)
        cmd, env, name, timeout = self.spawn.call_args.args
        self.assertEqual(cmd, [sys.executable, "-m", "hummingbot.cli.engine",
                               "--name", "conf_v1", "--config", "conf_v1.yml"])
        self.assertEqual(env["HBOT_PASSWORD"], "pw")
        self.assertEqual((name, timeout), ("conf_v1", 120.0))
        self.assertEqual(record, self.spawn.return_value)
        self.write_loaded.assert_called_once_with("conf_v1.yml", "v1-strategy")
        meta = self.write_meta.call_args.args[0]
        self.assertEqual((meta["name"], meta["type"], meta["file"], meta["config"], meta["script_config"]),
                         ("conf_v1", "v1-strategy", "conf_v1.yml", "conf_v1.yml", None))

    def test_v2_script_uses_script_config_flag(self):
        with patch.object(sc, "resolve_config_type", return_value="v2-script"):
            start_mod.launch(file="conf_pmm.yml")
        cmd = self.spawn.call_args.args[0]
        self.assertIn("--script-config", cmd)
        self.assertIn("conf_pmm.yml", cmd)
        self.assertNotIn("--config", cmd)

    def test_controller_is_wrapped_in_a_v2_loader(self):
        with patch.object(sc, "resolve_config_type", return_value="controller"), \
                patch.object(sc, "config_path", side_effect=lambda t, f: self.tmp / t / f) as cpath, \
                patch.object(sc, "validate_controller", return_value=(object(), set())) as validate, \
                patch.object(sc, "wrap_controller_as_v2", return_value="conf_ctrl_loader.yml") as wrap:
            start_mod.launch(file="conf_ctrl.yml")
        validate.assert_called_once_with(self.tmp / "controller" / "conf_ctrl.yml")
        cpath.assert_called_once_with("controller", "conf_ctrl.yml")
        wrap.assert_called_once_with("conf_ctrl.yml")
        cmd, _env, name, _timeout = self.spawn.call_args.args
        self.assertEqual(name, "conf_ctrl_loader")  # the loader stem names the bot/DB/log
        self.assertIn("--script-config", cmd)
        self.assertIn("conf_ctrl_loader.yml", cmd)

    def test_invalid_controller_config_fails(self):
        with patch.object(sc, "resolve_config_type", return_value="controller"), \
                patch.object(sc, "config_path", side_effect=lambda t, f: self.tmp / t / f), \
                patch.object(sc, "validate_controller", side_effect=ValueError("bad field")):
            with self.assertRaises(typer.Exit) as ctx:
                start_mod.launch(file="conf_ctrl.yml")
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))
        self.spawn.assert_not_called()

    def test_auto_set_permissions_is_forwarded(self):
        with patch.object(sc, "resolve_config_type", return_value="v2-script"):
            start_mod.launch(file="conf_pmm.yml", auto_set_permissions="hbot:hbot")
        cmd = self.spawn.call_args.args[0]
        self.assertIn("--auto-set-permissions", cmd)
        self.assertIn("hbot:hbot", cmd)

    def test_password_stdin_is_forwarded_to_login(self):
        with patch.object(sc, "resolve_config_type", return_value="v2-script"):
            start_mod.launch(file="conf_pmm.yml", password_stdin=True)
        self.login.assert_called_once_with(password_stdin=True)

    def test_no_file_and_nothing_loaded_fails(self):
        with patch.object(bot, "read_loaded", return_value=None):
            with self.assertRaises(typer.Exit) as ctx:
                start_mod.launch(file=None)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))

    def test_no_file_runs_the_loaded_config_with_its_recorded_type(self):
        with patch.object(bot, "read_loaded", return_value={"file": "conf_s.yml", "type": "v2-script"}), \
                patch.object(sc, "resolve_config_type", return_value="v2-script") as resolve:
            start_mod.launch(file=None)
        resolve.assert_called_once_with("conf_s.yml", "v2-script")

    def test_missing_config_fails_not_found(self):
        with patch.object(sc, "resolve_config_type", side_effect=FileNotFoundError("config not found: x")):
            with self.assertRaises(typer.Exit) as ctx:
                start_mod.launch(file="x.yml")
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.NOT_FOUND))

    def test_cross_type_collision_fails_config_error(self):
        with patch.object(sc, "resolve_config_type", side_effect=ValueError("exists as both")):
            with self.assertRaises(typer.Exit) as ctx:
                start_mod.launch(file="dup.yml")
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))

    def test_already_running_without_replace_fails(self):
        with patch.object(sc, "resolve_config_type", return_value="v2-script"), \
                patch.object(bot, "running", return_value=True), \
                patch.object(bot, "read_pid", return_value=777):
            with self.assertRaises(typer.Exit) as ctx:
                start_mod.launch(file="conf_pmm.yml")
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.ERROR))
        self.spawn.assert_not_called()

    def test_replace_stops_the_running_bot_first(self):
        with patch.object(sc, "resolve_config_type", return_value="v2-script"), \
                patch.object(bot, "running", return_value=True), \
                patch("hummingbot.cli.commands.start._replace_running") as replace:
            start_mod.launch(file="conf_pmm.yml", replace=True)
        replace.assert_called_once_with(timeout=30.0)
        self.spawn.assert_called_once()

    def test_foreground_execs_the_engine_in_place(self):
        fake_os = MagicMock()
        fake_os.environ = {"PATH": "/bin"}
        fake_os.getpid.return_value = 4321
        with patch.object(sc, "resolve_config_type", return_value="v1-strategy"), \
                patch.object(bot, "write_pid") as write_pid, \
                patch.object(bot, "update_meta") as update_meta, \
                patch("hummingbot.cli.commands.start.prefix_path", return_value=str(self.tmp)), \
                patch("hummingbot.cli.commands.start.os", fake_os):
            start_mod.launch(file="conf_v1.yml", foreground=True)
        write_pid.assert_called_once_with(4321)
        update_meta.assert_called_once_with(pid=4321)
        fake_os.chdir.assert_called_once_with(str(self.tmp))
        exec_python, exec_cmd, exec_env = fake_os.execve.call_args.args
        self.assertEqual(exec_python, sys.executable)
        self.assertEqual(exec_cmd[:3], [sys.executable, "-m", "hummingbot.cli.engine"])
        self.assertEqual(exec_env, {"PATH": "/bin", "HBOT_PASSWORD": "pw"})


class SpawnDetachedTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.tmp = Path(self.stack.enter_context(TemporaryDirectory()))
        self.stack.enter_context(patch.object(bot, "log_file", return_value=self.tmp / "bot.log"))
        self.write_pid = self.stack.enter_context(patch.object(bot, "write_pid"))
        self.update_meta = self.stack.enter_context(patch.object(bot, "update_meta"))
        self.clear_pid = self.stack.enter_context(patch.object(bot, "clear_pid"))
        self.stack.enter_context(patch("hummingbot.cli.commands.start.prefix_path", return_value=str(self.tmp)))
        self.fake_subprocess = MagicMock()
        self.proc = MagicMock(pid=4242)
        self.fake_subprocess.Popen.return_value = self.proc
        self.stack.enter_context(patch("hummingbot.cli.commands.start.subprocess", self.fake_subprocess))
        self.fake_time = MagicMock()
        self.stack.enter_context(patch("hummingbot.cli.commands.start.time", self.fake_time))
        self.cmd = [sys.executable, "-m", "hummingbot.cli.engine", "--name", "n"]
        self.env = {"HBOT_PASSWORD": "pw"}

    def test_ready_bot_returns_the_start_record(self):
        self.fake_time.time.side_effect = [0.0, 1.0]
        self.proc.poll.return_value = None
        with patch.object(bot, "read_status", return_value={"engine": {"strategy_running": True}}):
            record = start_mod._spawn_detached(self.cmd, self.env, "n", 60.0)
        self.assertEqual(record, {"name": "n", "pid": 4242, "status": "running"})
        self.write_pid.assert_called_once_with(4242)
        self.update_meta.assert_called_once_with(pid=4242)
        popen_kwargs = self.fake_subprocess.Popen.call_args.kwargs
        self.assertEqual(popen_kwargs["cwd"], str(self.tmp))
        self.assertEqual(popen_kwargs["env"], self.env)
        self.assertTrue(popen_kwargs["start_new_session"])
        self.fake_time.sleep.assert_not_called()

    def test_polls_until_the_strategy_is_running(self):
        self.fake_time.time.side_effect = [0.0, 1.0, 2.0]
        self.proc.poll.return_value = None
        with patch.object(bot, "read_status",
                          side_effect=[None, {"engine": {"strategy_running": True}}]):
            record = start_mod._spawn_detached(self.cmd, self.env, "n", 60.0)
        self.assertEqual(record["status"], "running")
        self.fake_time.sleep.assert_called_once_with(1.0)

    def test_engine_exit_during_startup_fails_with_the_log_tail(self):
        self.fake_time.time.side_effect = [0.0, 1.0]
        self.proc.poll.return_value = 3
        self.proc.returncode = 3
        with patch("hummingbot.cli.commands.start._log_tail", return_value="boom"):
            with self.assertRaises(typer.Exit) as ctx:
                start_mod._spawn_detached(self.cmd, self.env, "n", 60.0)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.ERROR))
        self.clear_pid.assert_called_once()

    def test_timeout_waiting_for_readiness(self):
        self.fake_time.time.side_effect = [0.0, 100.0]  # past the deadline before the first poll
        with self.assertRaises(typer.Exit) as ctx:
            start_mod._spawn_detached(self.cmd, self.env, "n", 10.0)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.TIMEOUT))


class StartCommandTest(unittest.TestCase):
    RECORD = {"name": "n", "pid": 7, "status": "running"}

    def _run(self, as_json):
        buf = io.StringIO()
        with patch("hummingbot.cli.commands.start.launch", return_value=dict(self.RECORD)) as launch, \
                redirect_stdout(buf):
            start_mod.start(file="conf_pmm.yml", v1=False, v2=True, controller=False, replace=True,
                            foreground=False, password_stdin=False, auto_set_permissions=None,
                            timeout=9.0, as_json=as_json)
        return launch, buf.getvalue()

    def test_json_output_emits_the_raw_record(self):
        launch, out = self._run(as_json=True)
        self.assertEqual(json.loads(out), self.RECORD)
        launch.assert_called_once_with(file="conf_pmm.yml", v1=False, v2=True, controller=False,
                                       replace=True, foreground=False, password_stdin=False,
                                       auto_set_permissions=None, timeout=9.0)

    def test_default_output_is_markdown_kv(self):
        _launch, out = self._run(as_json=False)
        self.assertIn("## start", out)
        self.assertIn("- pid: 7", out)


if __name__ == "__main__":
    unittest.main()
