import unittest
from decimal import Decimal
from typing import List

import pandas as pd

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from hummingbot.connector.test_support.mock_paper_exchange import MockPaperExchange
from hummingbot.core.clock import Clock
from hummingbot.core.clock_mode import ClockMode
from hummingbot.core.event.events import OrderType
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class MockScriptStrategy(ScriptStrategyBase):
    pass


class ScriptStrategyBaseTest(unittest.TestCase):
    level = 0

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage().startswith(message)
                   for record in self.log_records)

    def setUp(self):
        self.log_records = []
        self.start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
        self.end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
        self.start_timestamp: float = self.start.timestamp()
        self.end_timestamp: float = self.end.timestamp()
        self.connector_name: str = "mock_paper_exchange"
        self.trading_pair: str = "HBOT-USDT"
        self.base_asset, self.quote_asset = self.trading_pair.split("-")
        self.base_balance: int = 500
        self.quote_balance: int = 5000
        self.initial_mid_price: int = 100
        self.clock_tick_size = 1
        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)
        self.connector: MockPaperExchange = MockPaperExchange(
            client_config_map=ClientConfigAdapter(ClientConfigMap())
        )
        self.connector.set_balanced_order_book(trading_pair=self.trading_pair,
                                               mid_price=100,
                                               min_price=50,
                                               max_price=150,
                                               price_step_size=1,
                                               volume_step_size=10)
        self.connector.set_balance(self.base_asset, self.base_balance)
        self.connector.set_balance(self.quote_asset, self.quote_balance)
        self.connector.set_quantization_param(
            QuantizationParams(
                self.trading_pair, 6, 6, 6, 6
            )
        )
        self.clock.add_iterator(self.connector)
        ScriptStrategyBase.markets = {self.connector_name: {self.trading_pair}}
        self.strategy = ScriptStrategyBase({self.connector_name: self.connector})
        self.strategy.logger().setLevel(1)
        self.strategy.logger().addHandler(self)

    def test_load_valid_script_class(self):
        loaded_class = ScriptStrategyBase.load_script_class("dca_example")

        self.assertEqual({"binance_paper_trade": {"BTC-USDT"}}, loaded_class.markets)
        self.assertEqual(Decimal("100"), loaded_class.buy_quote_amount)

    def test_load_script_class_raises_exception_for_non_existing_script(self):
        self.assertRaises(ImportError, ScriptStrategyBase.load_script_class, "non_existing_script")

    def test_start(self):
        self.assertFalse(self.strategy.ready_to_trade)
        self.strategy.start(Clock(ClockMode.BACKTEST), self.start_timestamp)
        self.strategy.tick(self.start_timestamp + 10)
        self.assertTrue(self.strategy.ready_to_trade)

    def test_get_assets(self):
        self.strategy.markets = {"con_a": {"HBOT-USDT", "BTC-USDT"}, "con_b": {"HBOT-BTC", "HBOT-ETH"}}
        self.assertRaises(KeyError, self.strategy.get_assets, "con_c")
        assets = self.strategy.get_assets("con_a")
        self.assertEqual(3, len(assets))
        self.assertEqual("BTC", assets[0])
        self.assertEqual("HBOT", assets[1])
        self.assertEqual("USDT", assets[2])

        assets = self.strategy.get_assets("con_b")
        self.assertEqual(3, len(assets))
        self.assertEqual("BTC", assets[0])
        self.assertEqual("ETH", assets[1])
        self.assertEqual("HBOT", assets[2])

    def test_get_market_trading_pair_tuples(self):
        market_infos: List[MarketTradingPairTuple] = self.strategy.get_market_trading_pair_tuples()
        self.assertEqual(1, len(market_infos))
        market_info = market_infos[0]
        self.assertEqual(market_info.market, self.connector)
        self.assertEqual(market_info.trading_pair, self.trading_pair)
        self.assertEqual(market_info.base_asset, self.base_asset)
        self.assertEqual(market_info.quote_asset, self.quote_asset)

    def test_active_orders(self):
        self.clock.add_iterator(self.strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.strategy.buy(self.connector_name, self.trading_pair, Decimal("1"), OrderType.LIMIT, Decimal("90"))
        self.strategy.sell(self.connector_name, self.trading_pair, Decimal("1.1"), OrderType.LIMIT, Decimal("110"))
        orders = self.strategy.get_active_orders(self.connector_name)
        self.assertEqual(2, len(orders))
        self.assertTrue(orders[0].is_buy)
        self.assertEqual(Decimal("1"), orders[0].quantity)
        self.assertEqual(Decimal("90"), orders[0].price)
        self.assertFalse(orders[1].is_buy)
        self.assertEqual(Decimal("1.1"), orders[1].quantity)
        self.assertEqual(Decimal("110"), orders[1].price)

    def test_format_status(self):
        self.clock.add_iterator(self.strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.strategy.buy(self.connector_name, self.trading_pair, Decimal("1"), OrderType.LIMIT, Decimal("90"))
        self.strategy.sell(self.connector_name, self.trading_pair, Decimal("1.1"), OrderType.LIMIT, Decimal("110"))
        expected_status = """
  Balances:
               Exchange Asset  Total Balance  Available Balance
    mock_paper_exchange  HBOT            500              498.9
    mock_paper_exchange  USDT           5000               4910

  Orders:
               Exchange    Market Side  Price  Amount      Age
    mock_paper_exchange HBOT-USDT  buy     90       1"""
        self.assertTrue(expected_status in self.strategy.format_status())
        self.assertTrue("mock_paper_exchange HBOT-USDT sell    110     1.1 " in self.strategy.format_status())

    def test_cancel_buy_order(self):
        self.clock.add_iterator(self.strategy)
        self.clock.backtest_til(self.start_timestamp)

        order_id = self.strategy.buy(
            connector_name=self.connector_name,
            trading_pair=self.trading_pair,
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
            price=Decimal("1000"),
        )

        self.assertIn(order_id,
                      [order.client_order_id for order in self.strategy.get_active_orders(self.connector_name)])

        self.strategy.cancel(
            connector_name=self.connector_name,
            trading_pair=self.trading_pair,
            order_id=order_id
        )

        self.assertTrue(
            self._is_logged(
                log_level="INFO",
                message=f"({self.trading_pair}) Canceling the limit order {order_id}."
            )
        )
