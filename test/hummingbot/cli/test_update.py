import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import typer

from hummingbot.cli import bot, strategy_configs as sc
from hummingbot.cli.commands.update import update
from hummingbot.cli.output import ExitCode

META = {"type": "controller", "file": "conf_x.yml", "name": "mybot"}


class UpdateCommandTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cfg = Path(self._tmp.name) / "conf_x.yml"
        self.cfg.write_text("target_base_pct: 0.5\nother: 1\n")

    def test_no_bot_exits_not_found(self):
        with patch.object(bot, "exists", return_value=False):
            with self.assertRaises(typer.Exit) as ctx:
                update(key=None, value=None)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.NOT_FOUND))

    def test_meta_without_config_exits_error(self):
        with patch.object(bot, "exists", return_value=True), \
                patch.object(bot, "read_meta", return_value={"name": "mybot"}):
            with self.assertRaises(typer.Exit) as ctx:
                update(key=None, value=None)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.ERROR))

    def test_missing_config_file_exits_error(self):
        with patch.object(bot, "exists", return_value=True), \
                patch.object(bot, "read_meta", return_value=META), \
                patch.object(sc, "config_path", return_value=Path(self._tmp.name) / "gone.yml"):
            with self.assertRaises(typer.Exit) as ctx:
                update(key=None, value=None)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.ERROR))

    def test_show_lists_fields_with_live_flag(self):
        with patch.object(bot, "exists", return_value=True), \
                patch.object(bot, "read_meta", return_value=META), \
                patch.object(bot, "running", return_value=True), \
                patch.object(sc, "config_path", return_value=self.cfg), \
                patch.object(sc, "updatable_for", return_value={"target_base_pct"}), \
                patch.object(sc, "read_yaml", return_value={"target_base_pct": 0.5, "other": 1}), \
                patch("hummingbot.cli.commands.update.echo") as echo_mock:
            update(key=None, value=None)
        rendered = echo_mock.call_args.args[0]
        self.assertIn("update conf_x.yml (controller, running)", rendered)
        self.assertIn("target_base_pct", rendered)
        self.assertIn("other", rendered)

    def test_get_existing_key(self):
        with patch.object(bot, "exists", return_value=True), \
                patch.object(bot, "read_meta", return_value=META), \
                patch.object(bot, "running", return_value=False), \
                patch.object(sc, "config_path", return_value=self.cfg), \
                patch.object(sc, "updatable_for", return_value=set()), \
                patch.object(sc, "read_yaml", return_value={"target_base_pct": 0.5}), \
                patch.object(sc, "get_value", return_value=0.5) as get_value, \
                patch("hummingbot.cli.commands.update.echo") as echo_mock:
            update(key="target_base_pct", value=None)
        get_value.assert_called_once_with({"target_base_pct": 0.5}, "target_base_pct")
        self.assertIn("value: 0.5", echo_mock.call_args.args[0])

    def test_get_unknown_key_exits_config_error(self):
        with patch.object(bot, "exists", return_value=True), \
                patch.object(bot, "read_meta", return_value=META), \
                patch.object(bot, "running", return_value=False), \
                patch.object(sc, "config_path", return_value=self.cfg), \
                patch.object(sc, "updatable_for", return_value=set()), \
                patch.object(sc, "read_yaml", return_value={}), \
                patch.object(sc, "get_value", side_effect=KeyError("nope")):
            with self.assertRaises(typer.Exit) as ctx:
                update(key="nope", value=None)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))

    def _set_patches(self, running, edit_result=None, edit_side_effect=None):
        return [
            patch.object(bot, "exists", return_value=True),
            patch.object(bot, "read_meta", return_value=META),
            patch.object(bot, "running", return_value=running),
            patch.object(sc, "config_path", return_value=self.cfg),
            patch.object(sc, "updatable_for", return_value={"target_base_pct"}),
            patch.object(sc, "read_yaml", return_value={"target_base_pct": 0.5}),
            patch.object(sc, "edit_config", return_value=edit_result,
                         side_effect=edit_side_effect),
        ]

    def _run_set(self, key, value, running, edit_result=None, edit_side_effect=None):
        ps = self._set_patches(running, edit_result, edit_side_effect)
        with ps[0], ps[1], ps[2], ps[3], ps[4], ps[5], ps[6], \
                patch("hummingbot.cli.commands.update.echo") as echo_mock:
            update(key=key, value=value)
        return echo_mock.call_args.args[0]

    def test_set_live_field_while_running(self):
        rendered = self._run_set("target_base_pct", "0.55", running=True,
                                 edit_result=(0.55, {"target_base_pct"}))
        self.assertIn("applied_live: yes", rendered)
        self.assertIn("applied live (~10s)", rendered)

    def test_set_non_live_field_while_running(self):
        rendered = self._run_set("other", "2", running=True,
                                 edit_result=(2, {"target_base_pct"}))
        self.assertIn("applied_live: no", rendered)
        self.assertIn("restart to apply", rendered)

    def test_set_while_stopped(self):
        rendered = self._run_set("target_base_pct", "0.55", running=False,
                                 edit_result=(0.55, {"target_base_pct"}))
        self.assertIn("applied_live: no", rendered)
        self.assertIn("saved; applies on next start", rendered)

    def test_set_unknown_key_exits_config_error(self):
        with self.assertRaises(typer.Exit) as ctx:
            self._run_set("nope", "1", running=True, edit_side_effect=KeyError("nope"))
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))

    def test_set_rejected_value_exits_config_error(self):
        with self.assertRaises(typer.Exit) as ctx:
            self._run_set("target_base_pct", "junk", running=True,
                          edit_side_effect=ValueError("not a number"))
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))


if __name__ == "__main__":
    unittest.main()
