import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import typer

from hummingbot.cli import bot, strategy_configs as sc
from hummingbot.cli.commands.deploy import deploy, resolve_target
from hummingbot.cli.output import ExitCode


def run_deploy(target, **kwargs):
    params = dict(set_values=None, values_stdin=False, name=None, v1=False, v2=False,
                  controller=False, replace=False, foreground=False, password_stdin=False,
                  timeout=1.0, as_json=False)
    params.update(kwargs)
    return deploy(target=target, **params)


class ResolveTargetTest(unittest.TestCase):
    def test_existing_config_file_wins(self):
        # 'conf_x' normalizes to 'conf_x.yml'; a matching config file deploys that file.
        with patch.object(sc, "matching_config_types",
                          side_effect=lambda fn: ["controller"] if fn == "conf_x.yml" else []):
            self.assertEqual(resolve_target("conf_x", None), ("config", "conf_x.yml", "controller"))

    def test_strategy_name_when_no_config_matches(self):
        with patch.object(sc, "matching_config_types", return_value=[]), \
                patch.object(sc, "matching_strategy_types", return_value=["controller"]):
            self.assertEqual(resolve_target("pmm_simple", None), ("strategy", "pmm_simple", None))

    def test_explicit_type_flag_trusts_the_strategy_path(self):
        # an explicit --controller/--v2-script/--v1-strategy skips source discovery
        with patch.object(sc, "matching_config_types", return_value=[]), \
                patch.object(sc, "matching_strategy_types", return_value=[]):
            self.assertEqual(resolve_target("brand_new", "controller"), ("strategy", "brand_new", None))

    def test_unknown_target_exits_not_found(self):
        with patch.object(sc, "matching_config_types", return_value=[]), \
                patch.object(sc, "matching_strategy_types", return_value=[]):
            with self.assertRaises(typer.Exit) as ctx:
                resolve_target("nope", None)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.NOT_FOUND))

    def test_cross_type_config_collision_needs_a_flag(self):
        with patch.object(sc, "matching_config_types", return_value=["v1-strategy", "controller"]):
            with self.assertRaises(typer.Exit) as ctx:
                resolve_target("conf_dup.yml", None)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))


class DeployCommandTest(unittest.TestCase):
    """deploy() body against tempdir TYPE_DIRS, with the launch entry (hbot start's core) patched."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dirs = {}
        for t in sc.STRATEGY_TYPES:
            d = Path(self._tmp.name) / t
            d.mkdir()
            self.dirs[t] = d
        dirs_patch = patch.object(sc, "TYPE_DIRS", self.dirs)
        dirs_patch.start()
        self.addCleanup(dirs_patch.stop)
        loaded_patch = patch.object(bot, "write_loaded")
        self.write_loaded = loaded_patch.start()
        self.addCleanup(loaded_patch.stop)
        launch_patch = patch("hummingbot.cli.commands.start.launch",
                             return_value={"state": "running", "pid": 4242})
        self.launch = launch_patch.start()
        self.addCleanup(launch_patch.stop)

    def test_existing_config_is_edited_loaded_and_started(self):
        path = self.dirs["v2-script"] / "conf_x.yml"
        path.write_text("script_file_name: s.py\na: 1\n")
        out = io.StringIO()
        with redirect_stdout(out):
            run_deploy("conf_x", set_values=["a=5"], replace=True, timeout=7.0)
        self.assertIn("a: 5", path.read_text())  # comment-preserving edit applied
        self.write_loaded.assert_called_once_with("conf_x.yml", "v2-script")
        self.launch.assert_called_once_with(file="conf_x.yml", v1=False, v2=True, controller=False,
                                            replace=True, foreground=False, password_stdin=False,
                                            timeout=7.0)
        text = out.getvalue()
        self.assertIn("deployed conf_x.yml", text)
        self.assertIn("- config: existing", text)
        self.assertIn("- applied: a", text)
        self.assertIn("- state: running", text)

    def test_existing_config_stdin_values_applied(self):
        path = self.dirs["v2-script"] / "conf_x.yml"
        path.write_text("a: 1\n")
        with patch("hummingbot.cli.commands._common.read_json_object_from_stdin",
                   return_value={"a": 7}):
            with redirect_stdout(io.StringIO()):
                run_deploy("conf_x.yml", values_stdin=True)
        self.assertIn("a: 7", path.read_text())
        self.launch.assert_called_once()

    def test_existing_config_no_edits_launches_untouched(self):
        path = self.dirs["v2-script"] / "conf_x.yml"
        path.write_text("a: 1\n")
        out = io.StringIO()
        with redirect_stdout(out):
            run_deploy("conf_x.yml")
        self.assertEqual(path.read_text(), "a: 1\n")
        self.assertIn("- applied: -", out.getvalue())

    def test_name_flag_rejected_for_an_existing_config(self):
        (self.dirs["v2-script"] / "conf_x.yml").write_text("a: 1\n")
        err = io.StringIO()
        with redirect_stderr(err), self.assertRaises(typer.Exit) as ctx:
            run_deploy("conf_x.yml", name="conf_other")
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))
        self.assertIn("--name only applies when creating", err.getvalue())
        self.launch.assert_not_called()

    def test_bad_set_pair_is_a_config_error(self):
        (self.dirs["v2-script"] / "conf_x.yml").write_text("a: 1\n")
        with redirect_stderr(io.StringIO()), self.assertRaises(typer.Exit) as ctx:
            run_deploy("conf_x.yml", set_values=["noequals"])
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))
        self.launch.assert_not_called()

    def test_unknown_key_is_a_config_error(self):
        (self.dirs["v2-script"] / "conf_x.yml").write_text("a: 1\n")
        err = io.StringIO()
        with redirect_stderr(err), self.assertRaises(typer.Exit) as ctx:
            run_deploy("conf_x.yml", set_values=["nope=1"])
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))
        self.assertIn("key 'nope' not found in conf_x.yml", err.getvalue())

    def test_rejected_value_is_a_config_error_and_rolled_back(self):
        path = self.dirs["v2-script"] / "conf_x.yml"
        path.write_text("flag: true\n")
        err = io.StringIO()
        with redirect_stderr(err), self.assertRaises(typer.Exit) as ctx:
            run_deploy("conf_x.yml", set_values=["flag=maybe"])
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))
        self.assertIn("value rejected for 'flag'", err.getvalue())
        self.assertEqual(path.read_text(), "flag: true\n")  # edit rolled back

    def test_controller_config_is_validated_before_launch(self):
        path = self.dirs["controller"] / "conf_c.yml"
        path.write_text("controller_name: x\ncontroller_type: y\n")
        with patch.object(sc, "validate_controller", return_value=(MagicMock(), set())) as validate:
            with redirect_stdout(io.StringIO()):
                run_deploy("conf_c.yml")
        validate.assert_called_once_with(path)
        self.launch.assert_called_once_with(file="conf_c.yml", v1=False, v2=False, controller=True,
                                            replace=False, foreground=False, password_stdin=False,
                                            timeout=1.0)

    def test_broken_controller_fails_before_launch(self):
        (self.dirs["controller"] / "conf_c.yml").write_text("controller_name: x\ncontroller_type: y\n")
        err = io.StringIO()
        with patch.object(sc, "validate_controller", side_effect=ValueError("bad")):
            with redirect_stderr(err), self.assertRaises(typer.Exit) as ctx:
                run_deploy("conf_c.yml")
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))
        self.assertIn("invalid controller config: bad", err.getvalue())
        self.launch.assert_not_called()

    def test_strategy_name_creates_a_config_then_starts(self):
        created = {"file": "conf_pmm.yml", "type": "controller", "applied": "a, b", "ready": True,
                   "next": "hbot start"}
        out = io.StringIO()
        with patch("hummingbot.cli.commands.deploy.resolve_target",
                   return_value=("strategy", "pmm_simple", None)), \
                patch("hummingbot.cli.commands.create.create_config", return_value=created) as cc:
            with redirect_stdout(out):
                run_deploy("pmm_simple", set_values=["a=1", "b=2"], controller=True,
                           password_stdin=True)
        cc.assert_called_once_with(strategy="pmm_simple", set_values=["a=1", "b=2"],
                                   values_stdin=False, with_defaults=False, name=None,
                                   v1=False, v2=False, controller=True)
        self.launch.assert_called_once_with(file="conf_pmm.yml", v1=False, v2=False, controller=True,
                                            replace=False, foreground=False, password_stdin=True,
                                            timeout=1.0)
        text = out.getvalue()
        self.assertIn("deployed conf_pmm.yml", text)
        self.assertIn("- config: created", text)
        self.assertIn("- applied: a, b", text)

    def test_json_output_merges_config_and_start_records(self):
        (self.dirs["v2-script"] / "conf_x.yml").write_text("a: 1\n")
        out = io.StringIO()
        with redirect_stdout(out):
            run_deploy("conf_x.yml", as_json=True)
        record = json.loads(out.getvalue())
        self.assertEqual(record["file"], "conf_x.yml")
        self.assertEqual(record["config"], "existing")
        self.assertEqual(record["state"], "running")
        self.assertEqual(record["pid"], 4242)


if __name__ == "__main__":
    unittest.main()
