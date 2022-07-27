import asyncio
import datetime
import time
import unittest
from decimal import Decimal
from pathlib import Path
from test.mock.mock_cli import CLIMockingAssistant
from typing import Awaitable, List
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.client.config.client_config_map import ClientConfigMap, DBSqliteMode
from hummingbot.client.config.config_helpers import ClientConfigAdapter, read_system_configs_from_yml
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.exchange.paper_trade import PaperTradeExchange
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.model.order import Order
from hummingbot.model.sql_connection_manager import SQLConnectionManager
from hummingbot.model.trade_fill import TradeFill


class HistoryCommandTest(unittest.TestCase):
    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher")
    def setUp(self, _: MagicMock) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()

        self.async_run_with_timeout(read_system_configs_from_yml())
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

        self.app = HummingbotApplication(client_config_map=self.client_config_map)

        self.cli_mock_assistant = CLIMockingAssistant(self.app.app)
        self.cli_mock_assistant.start()
        self.mock_strategy_name = "test-strategy"

    def tearDown(self) -> None:
        self.cli_mock_assistant.stop()
        db_path = Path(SQLConnectionManager.create_db_path(db_name=self.mock_strategy_name))
        db_path.unlink(missing_ok=True)
        super().tearDown()

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

    def get_trades(self) -> List[TradeFill]:
        trade_fee = AddedToCostTradeFee(percent=Decimal("5"))
        trades = [
            TradeFill(
                config_file_path=f"{self.mock_strategy_name}.yml",
                strategy=self.mock_strategy_name,
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
        self.client_config_map.commands_timeout.other_commands_timeout = 0.01
        trades = self.get_trades()

        with self.assertRaises(asyncio.TimeoutError):
            self.async_run_with_timeout_coroutine_must_raise_timeout(
                self.app.history_report(start_time=time.time(), trades=trades)
            )
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with(
                msg="\nA network error prevented the balances retrieval to complete. See logs for more details."
            )
        )

    @patch("hummingbot.client.hummingbot_application.HummingbotApplication.notify")
    def test_list_trades(self, notify_mock):
        self.client_config_map.db_mode = DBSqliteMode()

        captures = []
        notify_mock.side_effect = lambda s: captures.append(s)
        self.app.strategy_file_name = f"{self.mock_strategy_name}.yml"

        trade_fee = AddedToCostTradeFee(percent=Decimal("5"))
        order_id = PaperTradeExchange.random_order_id(order_side="BUY", trading_pair="BTC-USDT")
        with self.app.trade_fill_db.get_new_session() as session:
            o = Order(
                id=order_id,
                config_file_path=f"{self.mock_strategy_name}.yml",
                strategy=self.mock_strategy_name,
                market="binance",
                symbol="BTC-USDT",
                base_asset="BTC",
                quote_asset="USDT",
                creation_timestamp=0,
                order_type="LMT",
                amount=4,
                leverage=0,
                price=3,
                last_status="PENDING",
                last_update_timestamp=0,
            )
            session.add(o)
            for i in [1, 2]:
                t = TradeFill(
                    config_file_path=f"{self.mock_strategy_name}.yml",
                    strategy=self.mock_strategy_name,
                    market="binance",
                    symbol="BTC-USDT",
                    base_asset="BTC",
                    quote_asset="USDT",
                    timestamp=i,
                    order_id=order_id,
                    trade_type="BUY",
                    order_type="LIMIT",
                    price=i,
                    amount=2,
                    leverage=1,
                    trade_fee=trade_fee.to_json(),
                    exchange_trade_id=f"someExchangeId{i}",
                )
                session.add(t)
            session.commit()

        self.app.list_trades(start_time=0)

        self.assertEqual(1, len(captures))

        creation_time_str = str(datetime.datetime.fromtimestamp(0))

        df_str_expected = (
            f"\n  Recent trades:"
            f"\n    +---------------------+------------+----------+--------------+--------+---------+----------+------------+------------+----------+"  # noqa: E501
            f"\n    | Timestamp           | Exchange   | Market   | Order_type   | Side   |   Price |   Amount |   Leverage | Position   | Age      |"  # noqa: E501
            f"\n    |---------------------+------------+----------+--------------+--------+---------+----------+------------+------------+----------|"  # noqa: E501
            f"\n    | {creation_time_str} | binance    | BTC-USDT | limit        | buy    |       1 |        2 |          1 | NIL        | 00:00:00 |"  # noqa: E501
            f"\n    | {creation_time_str} | binance    | BTC-USDT | limit        | buy    |       2 |        2 |          1 | NIL        | 00:00:00 |"  # noqa: E501
            f"\n    +---------------------+------------+----------+--------------+--------+---------+----------+------------+------------+----------+"  # noqa: E501
        )

        self.assertEqual(df_str_expected, captures[0])
