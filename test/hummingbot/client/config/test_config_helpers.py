import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Awaitable, Optional
from unittest.mock import MagicMock, patch

from pydantic import Field, SecretStr

from hummingbot.client.config import config_helpers
from hummingbot.client.config.config_crypt import ETHKeyFileSecretManger
from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, BaseStrategyConfigMap
from hummingbot.client.config.config_helpers import (
    ClientConfigAdapter,
    get_connector_config_yml_path,
    get_strategy_config_map,
    load_connector_config_map_from_file,
    save_to_yml,
)
from hummingbot.client.config.security import Security
from hummingbot.strategy.avellaneda_market_making.avellaneda_market_making_config_map_pydantic import (
    AvellanedaMarketMakingConfigMap,
)


class ConfigHelpersTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @staticmethod
    def get_async_sleep_fn(delay: float):
        async def async_sleep(*_, **__):
            await asyncio.sleep(delay)
        return async_sleep

    def test_get_strategy_config_map(self):
        cm = get_strategy_config_map(strategy="avellaneda_market_making")
        self.assertIsInstance(cm.hb_config, AvellanedaMarketMakingConfigMap)
        self.assertFalse(hasattr(cm, "market"))  # uninitialized instance

    def test_save_to_yml(self):
        class DummyStrategy(BaseStrategyConfigMap):
            class Config:
                title = "pure_market_making"

            strategy: str = "pure_market_making"

        cm = ClientConfigAdapter(DummyStrategy())
        expected_str = """\
#####################################
###   pure_market_making config   ###
#####################################

strategy: pure_market_making
"""
        with TemporaryDirectory() as d:
            d = Path(d)
            temp_file_name = d / "cm.yml"
            save_to_yml(temp_file_name, cm)
            with open(temp_file_name) as f:
                actual_str = f.read()
        self.assertEqual(expected_str, actual_str)

    @patch("hummingbot.client.config.config_helpers.AllConnectorSettings.get_connector_config_keys")
    def test_load_connector_config_map_from_file_with_secrets(self, get_connector_config_keys_mock: MagicMock):
        class DummyConnectorModel(BaseConnectorConfigMap):
            connector = "some-connector"
            secret_attr: Optional[SecretStr] = Field(default=None)

        password = "some-pass"
        Security.secrets_manager = ETHKeyFileSecretManger(password)
        cm = ClientConfigAdapter(DummyConnectorModel(secret_attr="some_secret"))
        get_connector_config_keys_mock.return_value = DummyConnectorModel()
        with TemporaryDirectory() as d:
            d = Path(d)
            config_helpers.CONNECTORS_CONF_DIR_PATH = d
            temp_file_name = get_connector_config_yml_path(cm.connector)
            save_to_yml(temp_file_name, cm)
            cm_loaded = load_connector_config_map_from_file(temp_file_name)

        self.assertEqual(cm, cm_loaded)
