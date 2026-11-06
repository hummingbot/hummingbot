import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import typer

from hummingbot.cli import bot, strategy_configs as sc
from hummingbot.cli.commands.import_cmd import import_config
from hummingbot.cli.output import ExitCode


def run_import(file, v1=False, v2=False, controller=False):
    return import_config(file=file, v1=v1, v2=v2, controller=controller)


class ImportConfigTest(unittest.TestCase):
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

    def test_imports_a_v2_script_config(self):
        (self.dirs["v2-script"] / "conf_s.yml").write_text("script_file_name: simple_pmm.py\norder_amount: 1\n")
        out = io.StringIO()
        with redirect_stdout(out):
            run_import("conf_s.yml")
        self.write_loaded.assert_called_once_with("conf_s.yml", "v2-script")
        text = out.getvalue()
        self.assertIn("imported conf_s.yml", text)
        self.assertIn("- type: v2-script", text)
        self.assertIn("- strategy: simple_pmm.py", text)   # script_file_name fallback
        self.assertIn("- next: hbot start", text)

    def test_imports_a_v1_strategy_config_with_explicit_flag(self):
        (self.dirs["v1-strategy"] / "conf_pmm.yml").write_text("strategy: pure_market_making\n")
        out = io.StringIO()
        with redirect_stdout(out):
            run_import("conf_pmm.yml", v1=True)
        self.write_loaded.assert_called_once_with("conf_pmm.yml", "v1-strategy")
        self.assertIn("- strategy: pure_market_making", out.getvalue())

    def test_controller_config_is_validated_now(self):
        path = self.dirs["controller"] / "conf_c.yml"
        path.write_text("controller_name: pmm_simple\ncontroller_type: generic\n")
        out = io.StringIO()
        with patch.object(sc, "validate_controller", return_value=(MagicMock(), set())) as validate:
            with redirect_stdout(out):
                run_import("conf_c.yml")
        validate.assert_called_once_with(path)
        self.write_loaded.assert_called_once_with("conf_c.yml", "controller")
        self.assertIn("- strategy: pmm_simple", out.getvalue())  # controller_name fallback

    def test_broken_controller_fails_at_import_not_start(self):
        (self.dirs["controller"] / "conf_c.yml").write_text("controller_name: x\ncontroller_type: y\n")
        err = io.StringIO()
        with patch.object(sc, "validate_controller", side_effect=ValueError("bad field")):
            with redirect_stderr(err), self.assertRaises(typer.Exit) as ctx:
                run_import("conf_c.yml")
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))
        self.assertIn("invalid config conf_c.yml: bad field", err.getvalue())
        self.write_loaded.assert_not_called()

    def test_missing_file_exits_not_found(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(typer.Exit) as ctx:
            run_import("nope.yml")
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.NOT_FOUND))
        self.write_loaded.assert_not_called()

    def test_cross_type_collision_needs_a_flag(self):
        (self.dirs["v2-script"] / "conf_dup.yml").write_text("a: 1\n")
        (self.dirs["controller"] / "conf_dup.yml").write_text("a: 1\n")
        err = io.StringIO()
        with redirect_stderr(err), self.assertRaises(typer.Exit) as ctx:
            run_import("conf_dup.yml")
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))
        self.assertIn("--v2-script / --controller", err.getvalue())

    def test_unparseable_yaml_is_a_config_error(self):
        (self.dirs["v2-script"] / "conf_bad.yml").write_text("a: [unclosed\nb: : :\n")
        err = io.StringIO()
        with redirect_stderr(err), self.assertRaises(typer.Exit) as ctx:
            run_import("conf_bad.yml")
        self.assertEqual(ctx.exception.exit_code, int(ExitCode.CONFIG_ERROR))
        self.assertIn("invalid config conf_bad.yml", err.getvalue())
        self.write_loaded.assert_not_called()


if __name__ == "__main__":
    unittest.main()
