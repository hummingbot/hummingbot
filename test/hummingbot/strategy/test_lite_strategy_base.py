from decimal import Decimal
from typing import List

import pandas as pd
import unittest

from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from hummingbot.core.clock import Clock
from hummingbot.core.clock_mode import ClockMode
from hummingbot.core.event.events import OrderType
from hummingbot.strategy.lite_strategy_base import LiteStrategyBase
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from test.mock.mock_paper_exchange import MockPaperExchange


class MockLiteStrategy(LiteStrategyBase):
    pass


class LiteStrategyBaseTest(unittest.TestCase):
    level = 0
    log_records = []
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    connector_name: str = "mock_paper_exchange"
    trading_pair: str = "HBOT-USDT"
    base_asset, quote_asset = trading_pair.split("-")
    base_balance: int = 500
    quote_balance: int = 5000
    initial_mid_price: int = 100
    clock_tick_size = 10

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def setUp(self):
        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)
        self.connector: MockPaperExchange = MockPaperExchange()
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
        LiteStrategyBase.markets = {self.connector_name: {self.trading_pair}}
        self.strategy = LiteStrategyBase({self.connector_name: self.connector})
        self.strategy.logger().setLevel(1)
        self.strategy.logger().addHandler(self)

    def test_start(self):
        self.assertFalse(self.strategy.ready_to_trade)
        self.strategy.start(Clock(ClockMode.BACKTEST), self.start_timestamp)
        self.strategy.tick(self.start_timestamp + 10)
        self.assertTrue(self.strategy.ready_to_trade)
        self.assertTrue(self._is_logged('INFO', 'All connector(s) are ready. Trading started.'))

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

    def test_get_market_trading_pair_tuple(self):
        market_info: MarketTradingPairTuple = self.strategy.get_market_trading_pair_tuple(self.connector_name,
                                                                                          self.trading_pair)
        self.assertEqual(market_info.market, self.connector)
        self.assertEqual(market_info.trading_pair, self.trading_pair)
        self.assertEqual(market_info.base_asset, self.base_asset)
        self.assertEqual(market_info.quote_asset, self.quote_asset)

    def test_get_market_trading_pair_tuples(self):
        market_infos: List[MarketTradingPairTuple] = self.strategy.get_market_trading_pair_tuples()
        self.assertEqual(1, len(market_infos))
        market_info = market_infos[0]
        self.assertEqual(market_info.market, self.connector)
        self.assertEqual(market_info.trading_pair, self.trading_pair)
        self.assertEqual(market_info.base_asset, self.base_asset)
        self.assertEqual(market_info.quote_asset, self.quote_asset)

    def test_active_orders(self):
        self.strategy.start(Clock(ClockMode.BACKTEST), self.start_timestamp)
        self.strategy.tick(self.start_timestamp + 10)
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
        self.strategy.start(Clock(ClockMode.BACKTEST), self.start_timestamp)
        self.strategy.tick(self.start_timestamp + 10)
        self.strategy.buy(self.connector_name, self.trading_pair, Decimal("1"), OrderType.LIMIT, Decimal("90"))
        self.strategy.sell(self.connector_name, self.trading_pair, Decimal("1.1"), OrderType.LIMIT, Decimal("110"))
        expected_status = """
  Balances:
               Exchange Asset  Total Balance  Available Balance
    mock_paper_exchange  HBOT            500              498.9
    mock_paper_exchange  USDT           5000               4910

  Orders:
               Exchange    Market Side  Price  Amount Age
    mock_paper_exchange HBOT-USDT  buy     90       1 n/a
    mock_paper_exchange HBOT-USDT sell    110     1.1 n/a

*** WARNINGS ***
  Markets are offline for the HBOT-USDT pair. Continued trading with these markets may be dangerous.
"""
        self.assertEqual(expected_status, self.strategy.format_status())
