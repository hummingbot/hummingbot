import asyncio
import time
import unittest
from copy import deepcopy
from decimal import Decimal
from typing import Awaitable, List
from unittest.mock import patch, MagicMock, AsyncMock

from hummingbot.client.config.config_helpers import read_system_configs_from_yml
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.model.trade_fill import TradeFill
from test.mock.mock_cli import CLIMockingAssistant


class HistoryCommandTest(unittest.TestCase):
    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher")
    def setUp(self, _: MagicMock) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()

        self.async_run_with_timeout(read_system_configs_from_yml())

        self.app = HummingbotApplication()

        self.cli_mock_assistant = CLIMockingAssistant(self.app.app)
        self.cli_mock_assistant.start()
        self.global_config_backup = deepcopy(global_config_map)

    def tearDown(self) -> None:
        self.cli_mock_assistant.stop()
        self.reset_global_config()
        super().tearDown()

    def reset_global_config(self):
        for key, value in self.global_config_backup.items():
            global_config_map[key] = value

    @staticmethod
    def get_async_sleep_fn(delay: float):
        async def async_sleep(*_, **__):
            await asyncio.sleep(delay)

        return async_sleep

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def async_run_with_timeout_coroutine_must_raise_timeout(self, coroutine: Awaitable, timeout: float = 1):
        class DesiredError(Exception):
            pass

        async def run_coro_that_raises(coro: Awaitable):
            try:
                await coro
            except asyncio.TimeoutError:
                raise DesiredError

        try:
            self.async_run_with_timeout(run_coro_that_raises(coroutine), timeout)
        except DesiredError:  # the coroutine raised an asyncio.TimeoutError as expected
            raise asyncio.TimeoutError
        except asyncio.TimeoutError:  # the coroutine did not finish on time
            raise RuntimeError

    @staticmethod
    def get_trades() -> List[TradeFill]:
        trade_fee = AddedToCostTradeFee(percent=Decimal("5"))
        trades = [
            TradeFill(
                config_file_path="some-strategy.yml",
                strategy="pure_market_making",
                market="binance",
                symbol="BTC-USDT",
                base_asset="BTC",
                quote_asset="USDT",
                timestamp=int(time.time()),
                order_id="someId",
                trade_type="BUY",
                order_type="LIMIT",
                price=1,
                amount=2,
                leverage=1,
                trade_fee=trade_fee.to_json(),
                exchange_trade_id="someExchangeId",
            )
        ]
        return trades

    @patch("hummingbot.client.command.history_command.HistoryCommand.get_current_balances")
    def test_history_report_raises_on_get_current_balances_network_timeout(self, get_current_balances_mock: AsyncMock):
        get_current_balances_mock.side_effect = self.get_async_sleep_fn(delay=0.02)
        global_config_map["other_commands_timeout"].value = 0.01
        trades = self.get_trades()

        with self.assertRaises(asyncio.TimeoutError):
            self.async_run_with_timeout_coroutine_must_raise_timeout(
                self.app.history_report(start_time=time.time(), trades=trades), 10000
            )
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with(
                msg="\nA network error prevented the balances retrieval to complete. See logs for more details."
            )
        )
