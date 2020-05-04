#!/usr/bin/env python
from decimal import Decimal
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

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
from hummingbot.strategy.celo_arb.celo_arb import CeloArbStrategy


class CeloArbUnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    market_trading_pairs: List[str] = ["cGLD-cUSD", "cGLD", "cUSD"]

    @classmethod
    def setUpClass(cls):
        pass

    def setUp(self):
        self.maxDiff = None
        self.clock: Clock = Clock(ClockMode.BACKTEST, 1.0, self.start_timestamp, self.end_timestamp)
        self.market: BacktestMarket = BacktestMarket()

        self.market_data: MockOrderBookLoader = MockOrderBookLoader(*self.market_trading_pairs)
        self.market_data.set_balanced_order_book(1.0, 0.5, 1.5, 0.01, 10)

        self.market.add_data(self.market_data)

        self.market.set_balance("cGLD", 500)
        self.market.set_balance("cUSD", 500)
        self.market.set_quantization_param(
            QuantizationParams(
                self.market_trading_pairs[0], 5, 5, 5, 5
            )
        )
        self.market_trading_pair_tuple = MarketTradingPairTuple(*([self.market] + self.market_trading_pairs))

        self.logging_options: int = CeloArbStrategy.OPTION_LOG_ALL

        self.strategy = CeloArbStrategy(
            self.market_trading_pair_tuple,
            min_profitability=Decimal("0.03"),
            order_amount=Decimal("100"),
            logging_options=self.logging_options
        )

        self.clock.add_iterator(self.market)
        self.clock.add_iterator(self.strategy)

        self.market_order_fill_logger: EventLogger = EventLogger()

        self.market.add_listener(MarketEvent.OrderFilled, self.market_order_fill_logger)
