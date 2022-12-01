import asyncio
import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Awaitable, List, Optional
from unittest.mock import MagicMock, patch

from pydantic import Field, SecretStr

from hummingbot.client.config import config_helpers
from hummingbot.client.config.client_config_map import ClientConfigMap, CommandShortcutModel
from hummingbot.client.config.config_crypt import ETHKeyFileSecretManger
from hummingbot.client.config.config_data_types import BaseClientModel, BaseConnectorConfigMap
from hummingbot.client.config.config_helpers import (
    ClientConfigAdapter,
    ReadOnlyClientConfigAdapter,
    get_connector_config_yml_path,
    get_strategy_config_map,
    load_connector_config_map_from_file,
    save_to_yml,
)
from hummingbot.client.config.security import Security
from hummingbot.client.config.strategy_config_data_types import BaseStrategyConfigMap
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

    def test_save_command_shortcuts_to_yml(self):
        class DummyStrategy(BaseClientModel):
            command_shortcuts: List[CommandShortcutModel] = Field(
                default=[
                    CommandShortcutModel(
                        command="spreads",
                        help="Set bid and ask spread",
                        arguments=["Bid Spread", "Ask Spread"],
                        output=["config bid_spread $1", "config ask_spread $2"]
                    )
                ]
            )
            another_attr: Decimal = Field(
                default=Decimal("1.0"),
                description="Some other\nmultiline description",
            )

            class Config:
                title = "dummy_global_config"

        cm = ClientConfigAdapter(DummyStrategy())
        expected_str = (
            "######################################\n"
            "###   dummy_global_config config   ###\n"
            "######################################\n\n"
            "command_shortcuts:\n"
            "- command: spreads\n"
            "  help: Set bid and ask spread\n"
            "  arguments:\n"
            "  - Bid Spread\n"
            "  - Ask Spread\n"
            "  output:\n"
            "  - config bid_spread $1\n"
            "  - config ask_spread $2\n\n"
            "# Some other\n"
            "# multiline description\n"
            "another_attr: 1.0\n"
        )

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


class ReadOnlyClientAdapterTest(unittest.TestCase):

    def test_read_only_adapter_can_be_created(self):
        adapter = ClientConfigAdapter(ClientConfigMap())
        read_only_adapter = ReadOnlyClientConfigAdapter(adapter.hb_config)

        self.assertEqual(adapter.hb_config, read_only_adapter.hb_config)

    def test_read_only_adapter_raises_exception_when_setting_value(self):
        read_only_adapter = ReadOnlyClientConfigAdapter(ClientConfigMap())
        initial_instance_id = read_only_adapter.instance_id

        with self.assertRaises(AttributeError) as context:
            read_only_adapter.instance_id = "newInstanceID"

        self.assertEqual("Cannot set an attribute on a read-only client adapter", str(context.exception))
        self.assertEqual(initial_instance_id, read_only_adapter.instance_id)
