import asyncio
import unittest
from hummingbot.client.config.config_var import ConfigVar


class ConfigVarTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()

    def test_init_with_defaults(self):
        var = ConfigVar("key", "test prompt")
        self.assertEqual("test prompt", var.prompt)
        self.assertEqual(False, var.is_secure)
        self.assertEqual(None, var.default)
        self.assertEqual("str", var.type)
        self.assertTrue(callable(var._required_if))
