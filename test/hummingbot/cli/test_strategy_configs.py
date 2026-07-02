import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import List
from unittest.mock import patch

import yaml
from pydantic import BaseModel, Field

from hummingbot.cli import strategy_configs as sc
from hummingbot.cli.strategy_configs import (
    _coerce,
    edit_config,
    get_value,
    set_value_preserving_comments,
    template_config_data,
)


class FakeControllerConfig(BaseModel):
    """Stand-in for a controller pydantic config (hermetic — no controller module import)."""
    controller_type: str = "generic"
    controller_name: str = "fake"
    id: str = ""
    total_amount_quote: float = Field(default=100.0, json_schema_extra={"is_updatable": True})
    fixed_field: int = 1


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
        self.assertIn("pmm_simple", available_sources("controller"))
        self.assertIn("simple_pmm.py", available_sources("v2-script"))
        self.assertIn("pure_market_making", available_sources("v1-strategy"))

    def test_describe_strategy_controller(self):
        from hummingbot.cli.strategy_configs import describe_strategy
        data, required, updatable = describe_strategy("controller", "pmm_simple")
        self.assertEqual(data["controller_name"], "pmm_simple")
        self.assertIn("total_amount_quote", updatable)
        self.assertNotIn("id", required)  # filled with a generated id, not prompted
        # A controller needs a STABLE, persisted id: blank ids make StrategyV2Base regenerate one each
        # start and spawn a duplicate controller every live-reload cycle. Create must fill it.
        self.assertTrue(data["id"], "controller config id must be generated, not blank")
        # two scaffolds get distinct ids
        data2, _, _ = describe_strategy("controller", "pmm_simple")
        self.assertNotEqual(data["id"], data2["id"])

    def test_parse_set_pairs(self):
        from hummingbot.cli.strategy_configs import parse_set_pairs
        self.assertEqual(parse_set_pairs(["a=1", "b=x=y"]), {"a": "1", "b": "x=y"})  # only first = splits
        with self.assertRaises(ValueError):
            parse_set_pairs(["noequals"])
        with self.assertRaises(ValueError):
            parse_set_pairs(["=novalue"])

    def test_fill_template_coerces_validates_and_reports_remaining(self):
        from hummingbot.cli.strategy_configs import fill_template
        data = {"a": None, "b": 0, "flag": False}
        # b's int placeholder coerces the string; a stays unfilled and is reported as remaining
        remaining = fill_template(data, required=["a", "b"], stype="v2-script", values={"b": "5", "flag": "true"})
        self.assertEqual(data["b"], 5)
        self.assertEqual(data["flag"], True)
        self.assertEqual(remaining, ["a"])

    def test_fill_template_unknown_field_raises(self):
        from hummingbot.cli.strategy_configs import fill_template
        with self.assertRaises(ValueError):
            fill_template({"a": 1}, required=[], stype="v2-script", values={"nope": "1"})

    def test_suggest_free_name_increments_past_existing(self):
        from hummingbot.cli import strategy_configs as sc
        existing = {"conf_x.yml", "conf_x_2.yml"}
        original = sc.matching_config_types
        sc.matching_config_types = lambda fn: ["controller"] if fn in existing else []
        try:
            self.assertEqual(sc.suggest_free_name("conf_new.yml"), "conf_new.yml")  # free → unchanged
            self.assertEqual(sc.suggest_free_name("conf_x"), "conf_x_3.yml")         # taken → next free, .yml added
            self.assertEqual(sc.suggest_free_name("conf_x_2.yml"), "conf_x_3.yml")   # strips trailing _n first
        finally:
            sc.matching_config_types = original

    def test_clone_config_copies_preserves_comments_and_applies_changes(self):
        from hummingbot.cli import strategy_configs as sc
        with TemporaryDirectory() as d:
            src = Path(d) / "src.yml"
            src.write_text("script_file_name: simple_pmm.py\norder_amount: 0.01  # tuned\n")
            # patch config_path so the helper resolves into the temp dir for this v2-script clone
            original = sc.config_path
            sc.config_path = lambda stype, fn: Path(d) / fn
            try:
                new_id = sc.clone_config("v2-script", "src.yml", "dest.yml", {"order_amount": "0.05"})
            finally:
                sc.config_path = original
            self.assertIsNone(new_id)  # only controllers get a regenerated id
            text = (Path(d) / "dest.yml").read_text()
            self.assertIn("order_amount: 0.05", text)
            self.assertIn("# tuned", text)               # inline comment preserved
            self.assertEqual(src.read_text().count("0.01"), 1)  # source untouched

    def test_clone_config_atomic_on_bad_value(self):
        from hummingbot.cli import strategy_configs as sc
        with TemporaryDirectory() as d:
            src = Path(d) / "src.yml"
            src.write_text("flag: true\n")
            original = sc.config_path
            sc.config_path = lambda stype, fn: Path(d) / fn
            try:
                with self.assertRaises(ValueError):
                    sc.clone_config("v2-script", "src.yml", "dest.yml", {"flag": "maybe"})
            finally:
                sc.config_path = original
            self.assertFalse((Path(d) / "dest.yml").exists())  # failed clone leaves nothing behind

    def test_template_config_data_fills_defaults_flags_required(self):
        class Model(BaseModel):
            x: int = 5
            y: str  # required, no default

        data, required = template_config_data(Model, {"x": 9})
        self.assertEqual(data["x"], 9)        # fixed override wins
        self.assertIsNone(data["y"])          # required -> placeholder
        self.assertEqual(required, ["y"])


class ConfigDirLookupsTest(unittest.TestCase):
    """list_configs / config_path / matching_config_types / resolve_config_type against temp dirs
    (TYPE_DIRS fully patched so the real conf/ tree is never touched)."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.dirs = {t: root / t for t in sc.STRATEGY_TYPES}
        for t in ("v1-strategy", "controller"):  # leave v2-script's dir non-existent
            self.dirs[t].mkdir()
        patcher = patch.dict(sc.TYPE_DIRS, self.dirs)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_list_configs_sorted_yml_only(self):
        (self.dirs["controller"] / "b.yml").write_text("a: 1\n")
        (self.dirs["controller"] / "a.yml").write_text("a: 1\n")
        (self.dirs["controller"] / "notes.txt").write_text("x")
        self.assertEqual(sc.list_configs("controller"), ["a.yml", "b.yml"])

    def test_list_configs_missing_dir_is_empty(self):
        self.assertEqual(sc.list_configs("v2-script"), [])

    def test_config_path_joins_type_dir(self):
        self.assertEqual(sc.config_path("controller", "c.yml"), self.dirs["controller"] / "c.yml")

    def test_matching_config_types(self):
        (self.dirs["controller"] / "dup.yml").write_text("a: 1\n")
        (self.dirs["v1-strategy"] / "dup.yml").write_text("a: 1\n")
        self.assertEqual(sc.matching_config_types("dup.yml"), ["v1-strategy", "controller"])
        self.assertEqual(sc.matching_config_types("nope.yml"), [])

    def test_resolve_config_type_explicit_verifies_existence(self):
        (self.dirs["controller"] / "c.yml").write_text("a: 1\n")
        self.assertEqual(sc.resolve_config_type("c.yml", explicit="controller"), "controller")
        with self.assertRaises(FileNotFoundError):
            sc.resolve_config_type("c.yml", explicit="v1-strategy")

    def test_resolve_config_type_detects_single_match(self):
        (self.dirs["v1-strategy"] / "only.yml").write_text("a: 1\n")
        self.assertEqual(sc.resolve_config_type("only.yml"), "v1-strategy")

    def test_resolve_config_type_absent_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            sc.resolve_config_type("ghost.yml")

    def test_resolve_config_type_collision_raises(self):
        (self.dirs["controller"] / "dup.yml").write_text("a: 1\n")
        (self.dirs["v1-strategy"] / "dup.yml").write_text("a: 1\n")
        with self.assertRaises(ValueError):
            sc.resolve_config_type("dup.yml")

    def test_create_config_file_writes_and_refuses_overwrite(self):
        path = sc.create_config_file("controller", "new.yml", {"a": 1})
        self.assertEqual(yaml.safe_load(path.read_text()), {"a": 1})
        with self.assertRaises(FileExistsError):
            sc.create_config_file("controller", "new.yml", {"a": 2})

    def test_clone_config_src_missing_raises(self):
        with self.assertRaises(FileNotFoundError):
            sc.clone_config("controller", "ghost.yml", "dest.yml", {})

    def test_clone_config_dest_exists_raises(self):
        (self.dirs["controller"] / "src.yml").write_text("a: 1\n")
        (self.dirs["controller"] / "dest.yml").write_text("a: 1\n")
        with self.assertRaises(FileExistsError):
            sc.clone_config("controller", "src.yml", "dest.yml", {})

    def test_wrap_controller_as_v2_writes_loader_with_flattened_name(self):
        self.dirs["v2-script"].mkdir()
        loader = sc.wrap_controller_as_v2("conf_x.lp.yml")
        self.assertEqual(loader, "conf_x_lp.yml")
        content = yaml.safe_load((self.dirs["v2-script"] / loader).read_text())
        self.assertEqual(content["script_file_name"], sc.V2_CONTROLLER_RUNNER)
        self.assertEqual(content["controllers_config"], ["conf_x.lp.yml"])
        self.assertIn("max_global_drawdown_quote", content)


class SourceCatalogTest(unittest.TestCase):
    def test_matching_strategy_types_matches_scripts_with_or_without_py(self):
        catalogs = {"v1-strategy": ["pmm"], "v2-script": ["foo.py"], "controller": ["pmm"]}
        with patch.object(sc, "available_sources", side_effect=lambda t: catalogs[t]):
            self.assertEqual(sc.matching_strategy_types("pmm"), ["v1-strategy", "controller"])
            self.assertEqual(sc.matching_strategy_types("foo"), ["v2-script"])
            self.assertEqual(sc.matching_strategy_types("foo.py"), ["v2-script"])
            self.assertEqual(sc.matching_strategy_types("nope"), [])

    def test_available_controllers_and_scripts_empty_when_dirs_missing(self):
        with TemporaryDirectory() as d, patch.object(sc, "prefix_path", return_value=d):
            self.assertEqual(sc.available_controllers(), [])
            self.assertEqual(sc.available_scripts(), [])


class DescribeStrategyTest(unittest.TestCase):
    def test_v2_script_uses_script_config_class(self):
        data, required, updatable = sc.describe_strategy("v2-script", "simple_pmm")
        self.assertEqual(data["script_file_name"], "simple_pmm.py")
        self.assertEqual(updatable, set())

    def test_v1_pydantic_config_class(self):
        class FakeV1Config(BaseModel):
            strategy: str = "fake_v1"
            exchange: str  # required, no default

        with patch("hummingbot.client.config.config_helpers.get_strategy_pydantic_config_cls",
                   return_value=FakeV1Config):
            data, required, updatable = sc.describe_strategy("v1-strategy", "fake_v1")
        self.assertEqual(data["strategy"], "fake_v1")
        self.assertEqual(required, ["exchange"])
        self.assertEqual(updatable, set())

    def test_v1_legacy_config_map(self):
        config_map = {"strategy": SimpleNamespace(default="legacy_v1", required=False),
                      "exchange": SimpleNamespace(default=None, required=True)}
        with patch("hummingbot.client.config.config_helpers.get_strategy_pydantic_config_cls",
                   return_value=None), \
                patch("hummingbot.client.config.config_helpers.get_strategy_config_map",
                      return_value=config_map):
            data, required, updatable = sc.describe_strategy("v1-strategy", "legacy_v1")
        self.assertEqual(data["strategy"], "legacy_v1")
        self.assertEqual(required, ["exchange"])

    def test_v1_unknown_strategy_raises(self):
        with patch("hummingbot.client.config.config_helpers.get_strategy_pydantic_config_cls",
                   return_value=None), \
                patch("hummingbot.client.config.config_helpers.get_strategy_config_map",
                      return_value=None):
            with self.assertRaises(ValueError):
                sc.describe_strategy("v1-strategy", "nope")


class ResolverErrorsTest(unittest.TestCase):
    def test_controller_config_class_requires_type_and_name(self):
        with self.assertRaises(ValueError):
            sc.controller_config_class({"controller_name": "x"})   # missing type
        with self.assertRaises(ValueError):
            sc.controller_config_class({"controller_type": "generic"})  # missing name

    def test_controller_config_class_no_class_in_module_raises(self):
        fake_importlib = SimpleNamespace(import_module=lambda name: SimpleNamespace())
        with patch.object(sc, "importlib", fake_importlib):
            with self.assertRaises(ValueError):
                sc.controller_config_class({"controller_type": "generic", "controller_name": "empty"})

    def test_resolve_controller_class_by_name_unknown_raises(self):
        with self.assertRaises(ValueError):
            sc.resolve_controller_class_by_name("definitely_not_a_controller_xyz")

    def test_resolve_script_config_class_finds_class(self):
        cls = sc.resolve_script_config_class("simple_pmm.py")
        self.assertEqual(cls.__name__, "SimplePMMConfig")
        self.assertIs(sc.resolve_script_config_class("simple_pmm"), cls)  # .py optional

    def test_resolve_script_config_class_none_found_raises(self):
        fake_importlib = SimpleNamespace(import_module=lambda name: SimpleNamespace())
        with patch.object(sc, "importlib", fake_importlib):
            with self.assertRaises(ValueError):
                sc.resolve_script_config_class("empty_script.py")


class ControllerValidationTest(unittest.TestCase):
    def _write(self, d, text="controller_type: generic\ncontroller_name: fake\n"):
        path = Path(d) / "ctrl.yml"
        path.write_text(text)
        return path

    def test_validate_controller_returns_config_and_updatable(self):
        with TemporaryDirectory() as d, \
                patch.object(sc, "controller_config_class", return_value=FakeControllerConfig):
            config, updatable = sc.validate_controller(self._write(d))
        self.assertEqual(config.controller_name, "fake")
        self.assertEqual(updatable, {"total_amount_quote"})

    def test_updatable_for_non_controller_is_empty(self):
        self.assertEqual(sc.updatable_for("v2-script", Path("whatever.yml")), set())

    def test_updatable_for_controller(self):
        with patch.object(sc, "validate_controller", return_value=(object(), {"x"})):
            self.assertEqual(sc.updatable_for("controller", Path("c.yml")), {"x"})

    def test_updatable_for_swallows_validation_errors(self):
        with patch.object(sc, "validate_controller", side_effect=ValueError("bad")):
            self.assertEqual(sc.updatable_for("controller", Path("c.yml")), set())

    def test_edit_config_missing_key_keyerror_no_rewrite(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "c.yml"
            path.write_text("a: 1\n")
            with self.assertRaises(KeyError):
                edit_config(path, "v2-script", "missing", "1")
            self.assertEqual(path.read_text(), "a: 1\n")

    def test_edit_config_controller_validates_and_reports_updatable(self):
        with TemporaryDirectory() as d:
            path = self._write(d, "total_amount_quote: 100.0\n")
            with patch.object(sc, "validate_controller", return_value=(object(), {"total_amount_quote"})):
                new_value, updatable = edit_config(path, "controller", "total_amount_quote", "250.0")
        self.assertEqual(new_value, 250.0)
        self.assertEqual(updatable, {"total_amount_quote"})

    def test_edit_config_controller_rolls_back_on_invalid_model(self):
        with TemporaryDirectory() as d:
            path = self._write(d, "total_amount_quote: 100.0\n")
            with patch.object(sc, "validate_controller", side_effect=ValueError("invalid")):
                with self.assertRaises(ValueError):
                    edit_config(path, "controller", "total_amount_quote", "250.0")
            self.assertEqual(path.read_text(), "total_amount_quote: 100.0\n")  # restored

    def test_fill_template_controller_full_validation_when_complete(self):
        data = {"controller_type": "generic", "controller_name": "fake", "id": "abc",
                "total_amount_quote": 100.0, "fixed_field": 1}
        with patch.object(sc, "controller_config_class", return_value=FakeControllerConfig):
            remaining = sc.fill_template(data, required=[], stype="controller",
                                         values={"total_amount_quote": "42.5"})
        self.assertEqual(remaining, [])
        self.assertEqual(data["total_amount_quote"], 42.5)


class YamlHelpersTest(unittest.TestCase):
    def test_read_yaml(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "a.yml"
            path.write_text("a: 1\n")
            self.assertEqual(sc.read_yaml(path), {"a": 1})
            path.write_text("")
            self.assertEqual(sc.read_yaml(path), {})  # empty file -> {}

    def test_set_value_traverses_nested_keys(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "n.yml"
            path.write_text("outer:\n  inner: 1  # keep\n")
            self.assertEqual(set_value_preserving_comments(path, "outer.inner", "5"), 5)
            text = path.read_text()
            self.assertIn("inner: 5", text)
            self.assertIn("# keep", text)

    def test_yaml_safe_covers_models_dicts_and_fallback(self):
        class Nested(BaseModel):
            amount: int = 3

        self.assertEqual(sc._yaml_safe(Nested()), {"amount": 3})            # pydantic -> dict
        self.assertEqual(sc._yaml_safe({"d": Decimal("1.5")}), {"d": "1.5"})  # dict values recurse
        self.assertEqual(sc._yaml_safe(Path("/x")), "/x")                   # last-resort str()

    def test_template_config_data_uses_default_factory(self):
        class M(BaseModel):
            items: List[str] = Field(default_factory=lambda: ["a"])

        data, required = template_config_data(M, {})
        self.assertEqual(data["items"], ["a"])
        self.assertEqual(required, [])

    def test_safe_attr_calls_callables_and_swallows_errors(self):
        class Obj:
            def ok(self):
                return 3

            def bad(self):
                raise RuntimeError("boom")

        obj = Obj()
        self.assertEqual(sc._safe_attr(obj, "ok"), 3)      # callable -> invoked
        self.assertIsNone(sc._safe_attr(obj, "bad"))       # raising callable -> None
        self.assertIsNone(sc._safe_attr(obj, "missing"))   # absent attr -> None

    def test_set_in_template_nested_and_unknown_paths(self):
        data = {"outer": {"inner": 1}}
        sc._set_in_template(data, "outer.inner", "9")
        self.assertEqual(data["outer"]["inner"], 9)
        with self.assertRaises(ValueError):
            sc._set_in_template(data, "ghost.inner", "1")   # unknown intermediate
        with self.assertRaises(ValueError):
            sc._set_in_template(data, "outer.ghost", "1")   # unknown leaf

    def test_regenerate_controller_id_preserves_comments(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "c.yml"
            path.write_text("controller_name: fake  # keep me\nid: old-id\n")
            new_id = sc.regenerate_controller_id(path)
            self.assertTrue(new_id)
            self.assertNotEqual(new_id, "old-id")
            text = path.read_text()
            self.assertIn(f"id: {new_id}", text)
            self.assertIn("# keep me", text)


if __name__ == "__main__":
    unittest.main()
