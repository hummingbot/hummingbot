import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import typer

from hummingbot.cli.commands.config import _item_for, _leaf_items, _navigate, config
from hummingbot.cli.output import ExitCode
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter


class ConfigCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cm = ClientConfigAdapter(ClientConfigMap())

    def test_leaf_items_excludes_sections(self):
        items = _leaf_items(self.cm)
        self.assertTrue(items)
        self.assertTrue(all(not isinstance(i.value, ClientConfigAdapter) for i in items))
        self.assertIn("mqtt_bridge.mqtt_port", {i.config_path for i in items})

    def test_navigate_and_set_propagates(self):
        model, leaf = _navigate(self.cm, "mqtt_bridge.mqtt_port")
        self.assertEqual(leaf, "mqtt_port")
        setattr(model, leaf, "1884")  # set on the nested wrapper...
        self.assertEqual(int(self.cm.mqtt_bridge.mqtt_port), 1884)  # ...propagates to the root

    def test_set_invalid_value_raises(self):
        model, leaf = _navigate(self.cm, "mqtt_bridge.mqtt_port")
        with self.assertRaises(Exception):
            setattr(model, leaf, "not-an-int")

    def test_item_for(self):
        item = _item_for(self.cm, "mqtt_bridge.mqtt_port")
        self.assertIsNotNone(item)
        self.assertEqual(item.config_path, "mqtt_bridge.mqtt_port")


class ConfigRunTest(unittest.TestCase):
    """End-to-end runs of the `config` command with the config map, bot state and conf dirs faked."""

    def setUp(self) -> None:
        self.cm = ClientConfigAdapter(ClientConfigMap())
        patch("hummingbot.client.config.config_helpers.load_client_config_map_from_file",
              return_value=self.cm).start()
        self.save_to_yml = patch("hummingbot.client.config.config_helpers.save_to_yml").start()
        self.running = patch("hummingbot.cli.bot.running", return_value=False).start()
        self.read_meta = patch("hummingbot.cli.bot.read_meta", return_value=None).start()
        self.read_loaded = patch("hummingbot.cli.bot.read_loaded", return_value=None).start()
        self.addCleanup(patch.stopall)

    def _run(self, key=None, value=None, as_json=False) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            config(key, value, as_json)
        return buf.getvalue()

    def _fail(self, key=None, value=None, as_json=False) -> int:
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(typer.Exit) as ctx:
                config(key, value, as_json)
        return ctx.exception.exit_code

    def _strategy(self, content: str, file="conf_x.yml", stype="v2-script", running=False) -> Path:
        """Write a strategy config in a temp conf dir and mark it loaded (or running)."""
        d = TemporaryDirectory()
        self.addCleanup(d.cleanup)
        path = Path(d.name) / file
        path.write_text(content)
        dict_patch = patch.dict("hummingbot.cli.strategy_configs.TYPE_DIRS", {stype: Path(d.name)})
        dict_patch.start()
        self.addCleanup(dict_patch.stop)
        if running:
            self.running.return_value = True
            self.read_meta.return_value = {"file": file, "type": stype}
        else:
            self.read_loaded.return_value = {"file": file, "type": stype}
        return path

    # -- listing --

    def test_list_global_only_when_nothing_loaded(self):
        out = self._run()
        self.assertIn("global settings", out)
        self.assertIn("mqtt_bridge.mqtt_port", out)
        self.assertNotIn("strategy config", out)

    def test_list_includes_loaded_strategy(self):
        self._strategy("market: binance\nflag: true\n")
        out = self._run()
        self.assertIn("global settings", out)
        self.assertIn("strategy config — conf_x.yml (v2-script, loaded)", out)
        self.assertIn("market", out)

    def test_list_shows_running_state(self):
        self._strategy("market: binance\n", running=True)
        out = self._run()
        self.assertIn("(v2-script, running)", out)

    def test_list_json_payload(self):
        self._strategy("market: binance\nflag: true\n")
        payload = json.loads(self._run(as_json=True))
        self.assertIn("mqtt_bridge.mqtt_port", payload["global"])
        self.assertEqual(payload["strategy"]["state"], "loaded")
        self.assertEqual(payload["strategy"]["file"], "conf_x.yml")
        self.assertEqual(payload["strategy"]["fields"]["market"], "binance")
        self.assertEqual(payload["strategy"]["live_fields"], [])

    def test_running_without_meta_falls_back_to_loaded(self):
        # running() True but meta.json has no file/type, and nothing imported -> global only
        self.running.return_value = True
        self.read_meta.return_value = {}
        out = self._run()
        self.assertNotIn("strategy config", out)

    # -- global scope --

    def test_read_global_key(self):
        out = self._run("mqtt_bridge.mqtt_port")
        self.assertIn("scope: global", out)
        self.assertIn("1883", out)

    def test_set_global_key_saves(self):
        out = self._run("mqtt_bridge.mqtt_port", "1884")
        self.assertEqual(int(self.cm.mqtt_bridge.mqtt_port), 1884)
        self.save_to_yml.assert_called_once()
        self.assertIn("1884", out)

    def test_set_global_invalid_value_fails(self):
        code = self._fail("mqtt_bridge.mqtt_port", "not-an-int")
        self.assertEqual(code, int(ExitCode.CONFIG_ERROR))
        self.save_to_yml.assert_not_called()

    def test_global_section_key_fails(self):
        code = self._fail("mqtt_bridge")
        self.assertEqual(code, int(ExitCode.CONFIG_ERROR))

    def test_unknown_key_with_no_strategy_loaded_fails(self):
        code = self._fail("totally_unknown_key")
        self.assertEqual(code, int(ExitCode.CONFIG_ERROR))

    # -- strategy scope --

    def test_read_strategy_key(self):
        self._strategy("market: binance\nflag: true\n")
        out = self._run("market")
        self.assertIn("scope: v2-script:conf_x.yml", out)
        self.assertIn("binance", out)

    def test_read_strategy_key_json_keeps_raw_value(self):
        self._strategy("market: binance\nflag: true\n")
        record = json.loads(self._run("flag", as_json=True))
        self.assertIs(record["value"], True)
        self.assertEqual(record["scope"], "v2-script:conf_x.yml")

    def test_strategy_unknown_key_fails(self):
        self._strategy("market: binance\n")
        code = self._fail("missing_key")
        self.assertEqual(code, int(ExitCode.CONFIG_ERROR))

    def test_set_strategy_key_writes_file(self):
        path = self._strategy("market: binance\n")
        out = self._run("market", "kraken")
        self.assertIn("market: kraken", path.read_text())
        self.assertIn("set conf_x.yml", out)
        self.assertNotIn("applies", out)  # not running -> no applies note

    def test_set_strategy_rejected_value_rolls_back(self):
        path = self._strategy("flag: true\n")
        code = self._fail("flag", "maybe")
        self.assertEqual(code, int(ExitCode.CONFIG_ERROR))
        self.assertIn("flag: true", path.read_text())  # rolled back

    def test_set_strategy_edit_key_error_fails(self):
        self._strategy("market: binance\n")
        with patch("hummingbot.cli.strategy_configs.edit_config", side_effect=KeyError("market")):
            code = self._fail("market", "kraken")
        self.assertEqual(code, int(ExitCode.CONFIG_ERROR))

    def test_set_running_controller_updatable_field_applies_live(self):
        self._strategy("amount: 10\n", file="conf_c.yml", stype="controller", running=True)
        with patch("hummingbot.cli.strategy_configs.edit_config", return_value=(42, {"amount"})):
            out = self._run("amount", "42")
        self.assertIn("live (~10s)", out)

    def test_set_running_v2_script_applies_on_next_start(self):
        self._strategy("market: binance\n", running=True)
        out = self._run("market", "kraken")
        self.assertIn("on next start", out)


if __name__ == "__main__":
    unittest.main()
