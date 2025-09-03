import asyncio
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.mock.mock_cli import CLIMockingAssistant
from typing import Type
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import Field

from hummingbot.client.command import import_command
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_data_types import BaseClientModel, ClientConfigEnum
from hummingbot.client.config.config_helpers import ClientConfigAdapter, read_system_configs_from_yml, save_to_yml
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.strategy_config_data_types import BaseTradingStrategyConfigMap
from hummingbot.client.hummingbot_application import HummingbotApplication


class ImportCommandTest(IsolatedAsyncioWrapperTestCase):
    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher")
    @patch("hummingbot.core.gateway.gateway_http_client.GatewayHttpClient.start_monitor")
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication.mqtt_start")
    async def asyncSetUp(self, mock_mqtt_start, mock_gateway_start, mock_trading_pair_fetcher):
        await read_system_configs_from_yml()
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.app = HummingbotApplication(client_config_map=self.client_config_map)
        self.cli_mock_assistant = CLIMockingAssistant(self.app.app)
        self.cli_mock_assistant.start()

    def tearDown(self) -> None:
        self.cli_mock_assistant.stop()
        super().tearDown()

    @staticmethod
    async def raise_timeout(*args, **kwargs):
        raise asyncio.TimeoutError

    @staticmethod
    def build_dummy_strategy_config_cls(strategy_name: str) -> Type[BaseClientModel]:
        class SomeEnum(ClientConfigEnum):
            ONE = "one"

        class DoubleNestedModel(BaseClientModel):
            double_nested_attr: datetime = Field(
                default=datetime(2022, 1, 1, 10, 30),
                description="Double nested attr description"
            )

        class NestedModel(BaseClientModel):
            nested_attr: str = Field(
                default="some value",
                description="Nested attr\nmultiline description",
            )
            double_nested_model: DoubleNestedModel = Field(
                default=DoubleNestedModel(),
            )

        class DummyModel(BaseTradingStrategyConfigMap):
            strategy: str = strategy_name
            exchange: str = "binance"
            market: str = "BTC-USDT"
            some_attr: SomeEnum = Field(
                default=SomeEnum.ONE,
                description="Some description",
            )
            nested_model: NestedModel = Field(
                default=NestedModel(),
                description="Nested model description",
            )
            another_attr: Decimal = Field(
                default=Decimal("1.0"),
                description="Some other\nmultiline description",
            )
            non_nested_no_description: time = Field(default=time(10, 30),)
            date_attr: date = Field(default=date(2022, 1, 2))
            no_default: str = Field(default=...)

            class Config:
                title = "dummy_model"

        return DummyModel

    @patch("hummingbot.client.command.import_command.load_strategy_config_map_from_file")
    @patch("hummingbot.client.command.status_command.StatusCommand.status_check_all")
    async def test_import_config_file_success_legacy(
        self, status_check_all_mock: AsyncMock, load_strategy_config_map_from_file: AsyncMock
    ):
        strategy_name = "some_strategy"
        strategy_file_name = f"{strategy_name}.yml"
        status_check_all_mock.return_value = True
        strategy_conf_var = ConfigVar("strategy", None)
        strategy_conf_var.value = strategy_name
        load_strategy_config_map_from_file.return_value = {"strategy": strategy_conf_var}

        await self.app.import_config_file(strategy_file_name)
        self.assertEqual(strategy_file_name, self.app.strategy_file_name)
        self.assertEqual(strategy_name, self.app.strategy_name)
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with("\nEnter \"start\" to start market making.")
        )

    @patch("hummingbot.client.command.import_command.load_strategy_config_map_from_file")
    @patch("hummingbot.client.command.status_command.StatusCommand.status_check_all")
    async def test_import_config_file_handles_network_timeouts_legacy(
        self, status_check_all_mock: AsyncMock, load_strategy_config_map_from_file: AsyncMock
    ):
        strategy_name = "some_strategy"
        strategy_file_name = f"{strategy_name}.yml"
        status_check_all_mock.side_effect = self.raise_timeout
        strategy_conf_var = ConfigVar("strategy", None)
        strategy_conf_var.value = strategy_name
        load_strategy_config_map_from_file.return_value = {"strategy": strategy_conf_var}

        with self.assertRaises(asyncio.TimeoutError):
            await self.app.import_config_file(strategy_file_name)
        self.assertEqual(None, self.app.strategy_file_name)
        self.assertEqual(None, self.app.strategy_name)

    @patch("hummingbot.client.config.config_helpers.get_strategy_pydantic_config_cls")
    @patch("hummingbot.client.command.status_command.StatusCommand.status_check_all")
    async def test_import_config_file_success(
        self, status_check_all_mock: AsyncMock, get_strategy_pydantic_config_cls: MagicMock
    ):
        strategy_name = "perpetual_market_making"
        strategy_file_name = f"{strategy_name}.yml"
        status_check_all_mock.return_value = True
        dummy_strategy_config_cls = self.build_dummy_strategy_config_cls(strategy_name)
        get_strategy_pydantic_config_cls.return_value = dummy_strategy_config_cls
        cm = ClientConfigAdapter(dummy_strategy_config_cls(no_default="some value"))

        with TemporaryDirectory() as d:
            d = Path(d)
            import_command.STRATEGIES_CONF_DIR_PATH = d
            temp_file_name = d / strategy_file_name
            save_to_yml(temp_file_name, cm)
            await self.app.import_config_file(strategy_file_name)

        self.assertEqual(strategy_file_name, self.app.strategy_file_name)
        self.assertEqual(strategy_name, self.app.strategy_name)
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with("\nEnter \"start\" to start market making.")
        )
        self.assertEqual(cm, self.app.strategy_config_map)

    @patch("hummingbot.client.config.config_helpers.get_strategy_pydantic_config_cls")
    @patch("hummingbot.client.command.status_command.StatusCommand.status_check_all")
    async def test_import_config_file_wrong_name(
        self, status_check_all_mock: AsyncMock, get_strategy_pydantic_config_cls: MagicMock
    ):
        strategy_name = "perpetual_market_making"
        strategy_file_name = f"{strategy_name}.yml"
        status_check_all_mock.return_value = True
        dummy_strategy_config_cls = self.build_dummy_strategy_config_cls(strategy_name)
        get_strategy_pydantic_config_cls.return_value = dummy_strategy_config_cls
        cm = ClientConfigAdapter(dummy_strategy_config_cls(no_default="some value"))

        wrong_strategy_file_name = f"wrong-{strategy_file_name}"
        with TemporaryDirectory() as d:
            d = Path(d)
            import_command.STRATEGIES_CONF_DIR_PATH = d
            temp_file_name = d / strategy_file_name
            save_to_yml(temp_file_name, cm)
            try:
                await self.app.import_config_file(wrong_strategy_file_name)
            except FileNotFoundError:
                self.assertNotEqual(strategy_file_name, self.app.strategy_file_name)
                self.assertNotEqual(strategy_name, self.app.strategy_name)
                return
            self.assertTrue(False)
