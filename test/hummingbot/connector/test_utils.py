import importlib
import unittest
from os import DirEntry, scandir
from os.path import exists, join
from typing import cast

from pydantic import SecretStr

from hummingbot import root_path
from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.client.settings import CONNECTOR_SUBMODULES_THAT_ARE_NOT_TYPES
from hummingbot.connector.utils import get_new_client_order_id


class UtilsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = "HBOT"
        cls.quote = "COINALPHA"
        cls.trading_pair = f"{cls.base}-{cls.quote}"

    def test_get_new_client_order_id(self):
        host_prefix = "hbot"

        id0 = get_new_client_order_id(is_buy=True, trading_pair=self.trading_pair)
        id1 = get_new_client_order_id(is_buy=True, trading_pair=self.trading_pair, hbot_order_id_prefix=host_prefix)

        self.assertFalse(id0.startswith(host_prefix))
        self.assertTrue(id1.startswith(host_prefix))

        id2 = get_new_client_order_id(is_buy=True, trading_pair=self.trading_pair, max_id_len=len(id0) - 2)

        self.assertEqual(len(id0) - 2, len(id2))

    def test_connector_config_maps(self):
        connector_exceptions = ["mock_paper_exchange", "mock_pure_python_paper_exchange", "paper_trade", "celo", "amm", "clob"]

        type_dirs = [
            cast(DirEntry, f) for f in
            scandir(f"{root_path() / 'hummingbot' / 'connector'}")
            if f.is_dir() and f.name not in CONNECTOR_SUBMODULES_THAT_ARE_NOT_TYPES
        ]
        for type_dir in type_dirs:
            connector_dirs = [
                cast(DirEntry, f) for f in scandir(type_dir.path)
                if f.is_dir() and exists(join(f.path, "__init__.py"))
            ]
            for connector_dir in connector_dirs:
                if connector_dir.name.startswith("_") or connector_dir.name in connector_exceptions:
                    continue
                util_module_path: str = (
                    f"hummingbot.connector.{type_dir.name}.{connector_dir.name}.{connector_dir.name}_utils"
                )
                util_module = importlib.import_module(util_module_path)
                connector_config = getattr(util_module, "KEYS")

                self.assertIsInstance(connector_config, BaseConnectorConfigMap)
                for el in ClientConfigAdapter(connector_config).traverse():
                    if el.attr == "connector":
                        self.assertEqual(el.value, connector_dir.name)
                    elif el.client_field_data.is_secure:
                        self.assertEqual(el.type_, SecretStr)
                    else:
                        self.assertEqual(el.type_, str)
