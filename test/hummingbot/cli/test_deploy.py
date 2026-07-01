import unittest
from unittest.mock import patch

import typer

from hummingbot.cli import strategy_configs as sc
from hummingbot.cli.commands.deploy import resolve_target
from hummingbot.cli.output import ExitCode


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


if __name__ == "__main__":
    unittest.main()
