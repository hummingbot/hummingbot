import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import BaseModel

from hummingbot.cli.strategy_configs import (
    _coerce,
    edit_config,
    get_value,
    set_value_preserving_comments,
    template_config_data,
)


class StrategyConfigHelpersTest(unittest.TestCase):
    def test_coerce_matches_existing_type(self):
        self.assertEqual(_coerce(True, "false"), False)
        self.assertEqual(_coerce(False, "yes"), True)
        self.assertEqual(_coerce(10, "42"), 42)
        self.assertEqual(_coerce(1.5, "2.5"), 2.5)
        # Decimals are stored as strings in yaml -> stay strings
        self.assertEqual(_coerce("2000", "3000"), "3000")

    def test_coerce_bad_bool_raises(self):
        with self.assertRaises(ValueError):
            _coerce(True, "maybe")

    def test_get_value_dotted(self):
        data = {"a": 1, "nested": {"b": {"c": 7}}}
        self.assertEqual(get_value(data, "a"), 1)
        self.assertEqual(get_value(data, "nested.b.c"), 7)
        with self.assertRaises(KeyError):
            get_value(data, "nested.b.x")

    def test_set_preserves_comments_and_coerces(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "ctrl.yml"
            path.write_text(
                "total_amount_quote: '2000'   # deployed size\n"
                "manual_kill_switch: false\n"
                "# trailing comment\n"
            )
            new_value = set_value_preserving_comments(path, "manual_kill_switch", "true")
            self.assertEqual(new_value, True)
            text = path.read_text()
            self.assertIn("# deployed size", text)     # inline comment preserved
            self.assertIn("# trailing comment", text)   # standalone comment preserved
            self.assertIn("manual_kill_switch: true", text)
            # untouched Decimal-as-string keeps its quote style
            self.assertIn("total_amount_quote: '2000'", text)

    def test_set_missing_key_raises(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "c.yml"
            path.write_text("a: 1\n")
            with self.assertRaises(KeyError):
                set_value_preserving_comments(path, "nope", "1")

    def test_edit_config_v2_no_validation(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "c.yml"
            path.write_text("a: 1\n")
            new_value, updatable = edit_config(path, "v2-script", "a", "5")
            self.assertEqual(new_value, 5)
            self.assertEqual(updatable, set())

    def test_edit_config_rolls_back_on_bad_value(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "c.yml"
            path.write_text("flag: true\n")
            with self.assertRaises(ValueError):
                edit_config(path, "v2-script", "flag", "maybe")
            self.assertIn("flag: true", path.read_text())  # unchanged

    def test_template_legacy_handles_raising_required_property(self):
        # pure_market_making's `required` evaluates a required_if lambda that touches still-unset
        # values and raises on access; template_legacy_data must tolerate that, not crash.
        from hummingbot.cli.strategy_configs import template_legacy_data
        from hummingbot.client.config.config_helpers import get_strategy_config_map

        config_map = get_strategy_config_map("pure_market_making")
        data, required = template_legacy_data(config_map)
        self.assertEqual(data["strategy"], "pure_market_making")
        self.assertIn("exchange", required)

    def test_available_sources(self):
        from hummingbot.cli.strategy_configs import available_sources
        self.assertIn("lp_jit", available_sources("controller"))
        self.assertIn("simple_pmm.py", available_sources("v2-script"))
        self.assertIn("pure_market_making", available_sources("v1-strategy"))

    def test_describe_strategy_controller(self):
        from hummingbot.cli.strategy_configs import describe_strategy
        data, required, updatable = describe_strategy("controller", "lp_jit")
        self.assertEqual(data["controller_name"], "lp_jit")
        self.assertIn("total_amount_quote", updatable)
        self.assertNotIn("id", required)  # filled with a generated id, not prompted
        # A controller needs a STABLE, persisted id: blank ids make StrategyV2Base regenerate one each
        # start and spawn a duplicate controller every live-reload cycle. Create must fill it.
        self.assertTrue(data["id"], "controller config id must be generated, not blank")
        # two scaffolds get distinct ids
        data2, _, _ = describe_strategy("controller", "lp_jit")
        self.assertNotEqual(data["id"], data2["id"])

    def test_template_config_data_fills_defaults_flags_required(self):
        class Model(BaseModel):
            x: int = 5
            y: str  # required, no default

        data, required = template_config_data(Model, {"x": 9})
        self.assertEqual(data["x"], 9)        # fixed override wins
        self.assertIsNone(data["y"])          # required -> placeholder
        self.assertEqual(required, ["y"])


if __name__ == "__main__":
    unittest.main()
