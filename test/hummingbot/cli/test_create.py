import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import typer
import yaml

from hummingbot.cli import bot, strategy_configs as sc
from hummingbot.cli.commands.create import _collect_values, _resolve_strategy_type, create, create_config
from hummingbot.cli.output import ExitCode


class ResolveStrategyTypeTest(unittest.TestCase):
    def test_explicit_flag_wins(self):
        # an explicit type flag skips source discovery entirely
        self.assertEqual(_resolve_strategy_type("anything", True, False, False), "v1-strategy")
        self.assertEqual(_resolve_strategy_type("anything", False, True, False), "v2-script")
        self.assertEqual(_resolve_strategy_type("anything", False, False, True), "controller")

    def test_single_match_detected(self):
        with patch.object(sc, "matching_strategy_types", return_value=["controller"]):
            self.assertEqual(_resolve_strategy_type("pmm_simple", False, False, False), "controller")

    def test_cross_type_collision_needs_a_flag(self):
        with patch.object(sc, "matching_strategy_types", return_value=["v2-script", "controller"]):
            err = io.StringIO()
            with redirect_stderr(err), self.assertRaises(typer.Exit) as ctx:
                _resolve_strategy_type("dup", False, False, False)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))
        self.assertIn("--v2-script / --controller", err.getvalue())

    def test_not_found_lists_available_sources(self):
        many_scripts = [f"script_{i}.py" for i in range(9)]  # >8 → the hint gets an ellipsis
        avail = {"v1-strategy": [], "v2-script": many_scripts, "controller": ["pmm_simple"]}
        with patch.object(sc, "matching_strategy_types", return_value=[]), \
                patch.object(sc, "available_sources", side_effect=avail.__getitem__):
            err = io.StringIO()
            with redirect_stderr(err), self.assertRaises(typer.Exit) as ctx:
                _resolve_strategy_type("nope", False, False, False)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.NOT_FOUND))
        message = err.getvalue()
        self.assertIn("pmm_simple", message)   # name discovery in the error
        self.assertIn("script_0.py", message)
        self.assertIn("…", message)            # long lists are truncated
        self.assertNotIn("script_8.py", message)


class CollectValuesTest(unittest.TestCase):
    def test_empty_without_sources(self):
        self.assertEqual(_collect_values(None, False), {})

    def test_stdin_then_set_pairs_with_set_winning(self):
        with patch("hummingbot.cli.commands.create.read_json_object_from_stdin",
                   return_value={"a": 1, "b": 2}):
            values = _collect_values(["b=9"], True)
        self.assertEqual(values, {"a": 1, "b": "9"})  # --set overrides stdin

    def test_bad_set_pair_fails(self):
        err = io.StringIO()
        with redirect_stderr(err), self.assertRaises(typer.Exit) as ctx:
            _collect_values(["noequals"], False)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))
        self.assertIn("noequals", err.getvalue())


class CreateConfigTest(unittest.TestCase):
    """End-to-end create_config against tempdir TYPE_DIRS, real helpers, faked describe_strategy."""

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

    def _describe(self, template: dict, required):
        # fresh template each call (create_config mutates it in place)
        return patch.object(sc, "describe_strategy",
                            side_effect=lambda *a, **k: (dict(template), list(required), set()))

    def test_ready_to_run_with_all_required_set(self):
        with self._describe({"script_file_name": "s.py", "a": None, "b": 1}, ["a"]):
            record = create_config(strategy="s", set_values=["a=hello"], v2=True)
        self.assertEqual(record["file"], "conf_s.yml")
        self.assertEqual(record["type"], "v2-script")
        self.assertEqual(record["applied"], "a")
        self.assertTrue(record["ready"])
        self.assertEqual(record["next"], "hbot start")
        data = yaml.safe_load((self.dirs["v2-script"] / "conf_s.yml").read_text())
        self.assertEqual(data, {"script_file_name": "s.py", "a": "hello", "b": 1})
        self.write_loaded.assert_called_once_with("conf_s.yml", "v2-script")

    def test_missing_required_fails_and_writes_nothing(self):
        err = io.StringIO()
        with self._describe({"a": None, "b": None}, ["a", "b"]):
            with redirect_stderr(err), self.assertRaises(typer.Exit) as ctx:
                create_config(strategy="s", set_values=["a=1"], v2=True)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))
        self.assertIn("missing required fields: b", err.getvalue())
        self.assertFalse((self.dirs["v2-script"] / "conf_s.yml").exists())
        self.write_loaded.assert_not_called()

    def test_with_defaults_scaffolds_and_reports_remaining(self):
        with self._describe({"a": None, "b": 1}, ["a"]):
            record = create_config(strategy="s", with_defaults=True, v2=True)
        self.assertFalse(record["ready"])
        self.assertEqual(record["required_remaining"], "a")
        self.assertEqual(record["next"], "hbot config a <value>")
        self.assertEqual(record["applied"], "-")
        data = yaml.safe_load((self.dirs["v2-script"] / "conf_s.yml").read_text())
        self.assertIsNone(data["a"])  # left blank for `hbot config`

    def test_explicit_name_collision_suggests_a_free_name(self):
        (self.dirs["controller"] / "conf_x.yml").write_text("a: 1\n")
        err = io.StringIO()
        with self._describe({"a": 1}, []):
            with redirect_stderr(err), self.assertRaises(typer.Exit) as ctx:
                create_config(strategy="s", name="conf_x", v2=True)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))
        self.assertIn("--name conf_x_2.yml", err.getvalue())

    def test_default_name_rolls_forward_silently(self):
        (self.dirs["v2-script"] / "conf_s.yml").write_text("a: 1\n")
        with self._describe({"a": 1}, []):
            record = create_config(strategy="s", v2=True)
        self.assertEqual(record["file"], "conf_s_2.yml")
        self.assertTrue((self.dirs["v2-script"] / "conf_s_2.yml").exists())

    def test_controller_id_is_scaffold_generated_not_user_supplied(self):
        template = {"controller_name": "s", "controller_type": "generic", "id": "scaffolded", "a": None}
        with self._describe(template, ["a"]), \
                patch.object(sc, "controller_config_class", return_value=MagicMock()):
            record = create_config(strategy="s", set_values=["id=mine", "a=1"], controller=True)
        data = yaml.safe_load((self.dirs["controller"] / "conf_s.yml").read_text())
        self.assertEqual(data["id"], "scaffolded")   # user-supplied id ignored
        self.assertEqual(record["applied"], "a")     # id not reported as applied
        self.write_loaded.assert_called_once_with("conf_s.yml", "controller")

    def test_describe_failure_is_a_config_error(self):
        with patch.object(sc, "describe_strategy", side_effect=ValueError("boom")):
            with redirect_stderr(io.StringIO()), self.assertRaises(typer.Exit) as ctx:
                create_config(strategy="s", v2=True)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))

    def test_unknown_field_is_an_invalid_value_error(self):
        err = io.StringIO()
        with self._describe({"a": 1}, []):
            with redirect_stderr(err), self.assertRaises(typer.Exit) as ctx:
                create_config(strategy="s", set_values=["nope=1"], v2=True)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))
        self.assertIn("invalid field value", err.getvalue())

    def test_write_race_file_exists_fails_cleanly(self):
        with self._describe({"a": 1}, []), \
                patch.object(sc, "create_config_file", side_effect=FileExistsError("already there")):
            with redirect_stderr(io.StringIO()), self.assertRaises(typer.Exit) as ctx:
                create_config(strategy="s", v2=True)
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))
        self.write_loaded.assert_not_called()


class CreateCommandTest(unittest.TestCase):
    def test_command_renders_the_record(self):
        record = {"file": "conf_s.yml", "type": "v2-script", "applied": "a", "ready": True, "next": "hbot start"}
        out = io.StringIO()
        with patch("hummingbot.cli.commands.create.create_config", return_value=record) as cc:
            with redirect_stdout(out):
                create(strategy="s", set_values=["a=1"], values_stdin=False, with_defaults=False,
                       name=None, v1=False, v2=True, controller=False)
        cc.assert_called_once_with(strategy="s", set_values=["a=1"], values_stdin=False,
                                   with_defaults=False, name=None, v1=False, v2=True, controller=False)
        text = out.getvalue()
        self.assertIn("created v2-script/conf_s.yml", text)
        self.assertIn("- next: hbot start", text)


if __name__ == "__main__":
    unittest.main()
