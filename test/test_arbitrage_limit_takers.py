#!/usr/bin/env python
from decimal import Decimal
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

from nose.plugins.attrib import attr

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
import logging; logging.basicConfig(level=logging.ERROR)
import pandas as pd
from typing import List
import unittest
from hummingsim.backtest.backtest_market import BacktestMarket
from hummingsim.backtest.market import (
    QuantizationParams
)
from hummingsim.backtest.mock_order_book_loader import MockOrderBookLoader
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent
)
from hummingbot.strategy.arbitrage.arbitrage import ArbitrageStrategy
from hummingbot.strategy.arbitrage.arbitrage_market_pair import ArbitrageMarketPair


@attr('stable')
class ArbitrageUnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    market_1_trading_pairs: List[str] = ["COINALPHA-WETH", "COINALPHA", "WETH"]
    market_2_trading_pairs: List[str] = ["coinalpha/eth", "COINALPHA", "ETH"]

    def setUp(self):
        self.maxDiff = None
        self.clock: Clock = Clock(ClockMode.BACKTEST, 1.0, self.start_timestamp, self.end_timestamp)
        self.market_1: BacktestMarket = BacktestMarket()
        self.market_2: BacktestMarket = BacktestMarket()

        self.market_1_data: MockOrderBookLoader = MockOrderBookLoader(*self.market_1_trading_pairs)
        self.market_2_data: MockOrderBookLoader = MockOrderBookLoader(*self.market_2_trading_pairs)
        self.market_1_data.set_balanced_order_book(1.0, 0.5, 1.5, 0.01, 10)
        self.market_2_data.set_balanced_order_book(1.0, 0.5, 1.5, 0.005, 5)

        self.market_1.add_data(self.market_1_data)
        self.market_2.add_data(self.market_2_data)

        self.market_1.set_balance("COINALPHA", 500)
        self.market_1.set_balance("WETH", 500)
        self.market_2.set_balance("COINALPHA", 500)
        self.market_2.set_balance("ETH", 500)
        self.market_1.set_quantization_param(
            QuantizationParams(
                self.market_1_trading_pairs[0], 5, 5, 5, 5
            )
        )
        self.market_2.set_quantization_param(
            QuantizationParams(
                self.market_2_trading_pairs[0], 5, 5, 5, 5
            )
        )
        self.market_trading_pair_tuple_1 = MarketTradingPairTuple(*([self.market_1] + self.market_1_trading_pairs))
        self.market_trading_pair_tuple_2 = MarketTradingPairTuple(*([self.market_2] + self.market_2_trading_pairs))
        self.market_pair: ArbitrageMarketPair = ArbitrageMarketPair(
            self.market_trading_pair_tuple_1, self.market_trading_pair_tuple_2
        )

        self.logging_options: int = ArbitrageStrategy.OPTION_LOG_ALL

        self.strategy: ArbitrageStrategy = ArbitrageStrategy(
            [self.market_pair],
            min_profitability=Decimal("0.03"),
            logging_options=self.logging_options,
            secondary_to_primary_quote_conversion_rate=Decimal("0.95")
        )

        self.clock.add_iterator(self.market_1)
        self.clock.add_iterator(self.market_2)
        self.clock.add_iterator(self.strategy)

        self.market_1_order_fill_logger: EventLogger = EventLogger()
        self.market_2_order_fill_logger: EventLogger = EventLogger()

        self.market_1.add_listener(MarketEvent.OrderFilled, self.market_1_order_fill_logger)
        self.market_2.add_listener(MarketEvent.OrderFilled, self.market_2_order_fill_logger)

    def test_ready_for_new_orders(self):
        # No pending orders
        self.assertTrue(self.strategy.ready_for_new_orders([self.market_trading_pair_tuple_1, self.market_trading_pair_tuple_2]))

        self.clock.backtest_til(self.start_timestamp + 6)
        # prevent making new orders
        self.market_1.set_balance("COINALPHA", Decimal("0"))
        self.assertFalse(self.strategy.ready_for_new_orders([self.market_trading_pair_tuple_1, self.market_trading_pair_tuple_2]))

        # run till market orders complete and cool off period passes
        self.clock.backtest_til(self.start_timestamp + 20)

        self.assertTrue(self.strategy.ready_for_new_orders([self.market_trading_pair_tuple_1, self.market_trading_pair_tuple_2]))

    def test_arbitrage_limit_orders(self):
        self.market_1.set_balance("COINALPHA", 5)
        self.market_2.set_balance("COINALPHA", 5)
        self.clock.backtest_til(self.start_timestamp + 1)
        limit_orders = self.strategy.tracked_limit_orders

        # Orders tracked by arbitrage's tracked_maker_orders are limit orders
        self.assertTrue(len(limit_orders) == 2)
