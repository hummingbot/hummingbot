import unittest

from hummingbot.cli.commands.config import _item_for, _leaf_items, _navigate
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


if __name__ == "__main__":
    unittest.main()
