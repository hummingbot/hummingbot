#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

from decimal import Decimal
import logging; logging.basicConfig(level=logging.ERROR)
import pandas as pd
from typing import List
import unittest

from hummingbot.cli.utils.exchange_rate_conversion import ExchangeRateConversion
from hummingsim.backtest.backtest_market import BacktestMarket
from hummingsim.backtest.market import (
    AssetType,
    Market,
    MarketConfig,
    QuantizationParams
)
from hummingsim.backtest.mock_order_book_loader import MockOrderBookLoader
from wings.clock import (
    Clock,
    ClockMode
)
from wings.event_logger import EventLogger
from wings.events import (
    MarketEvent,
    OrderBookTradeEvent,
    TradeType,
    OrderType,
    OrderFilledEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent
)
from wings.order_book import OrderBook
from wings.order_book_row import OrderBookRow
from wings.limit_order import LimitOrder
from hummingbot.strategy.arbitrage.arbitrage import ArbitrageStrategy
from hummingbot.strategy.arbitrage.arbitrage_market_pair import ArbitrageMarketPair


class ArbitrageUnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    market_1_symbols: List[str] = ["COINALPHA-WETH", "COINALPHA", "WETH"]
    market_2_symbols: List[str] = ["coinalpha/eth", "COINALPHA", "ETH"]

    @classmethod
    def setUpClass(cls):
        ExchangeRateConversion.set_global_exchange_rate_config([
            ("WETH", 1.0, "None"),
            ("QETH", 0.95, "None"),
        ])

    def setUp(self):
        self.clock: Clock = Clock(ClockMode.BACKTEST, 1.0, self.start_timestamp, self.end_timestamp)
        self.market_1: BacktestMarket = BacktestMarket()
        self.market_2: BacktestMarket = BacktestMarket()
        self.market_1_data: MockOrderBookLoader = MockOrderBookLoader(*self.market_1_symbols)
        self.market_2_data: MockOrderBookLoader = MockOrderBookLoader(*self.market_2_symbols)
        self.market_1_data.set_balanced_order_book(1.0, 0.5, 1.5, 0.01, 10)
        self.market_2_data.set_balanced_order_book(1.3, 0.5, 1.5, 0.001, 4)

        self.market_1.add_data(self.market_1_data)
        self.market_2.add_data(self.market_2_data)

        self.market_1.set_balance("COINALPHA", 5)
        self.market_1.set_balance("ETH", 5)

        self.market_2.set_balance("COINALPHA", 5)
        self.market_2.set_balance("WETH", 5)

        self.market_1.set_quantization_param(
            QuantizationParams(
                self.market_1_symbols[0], 5, 5, 5, 5
            )
        )
        self.market_2.set_quantization_param(
            QuantizationParams(
                self.market_2_symbols[0], 5, 5, 5, 5
            )
        )
        self.market_pair: ArbitrageMarketPair = ArbitrageMarketPair(
            *(
                [self.market_1] + self.market_1_symbols + [self.market_2] + self.market_2_symbols
            )
        )

        logging_options: int = ArbitrageStrategy.OPTION_LOG_ALL
        self.strategy: ArbitrageStrategy = ArbitrageStrategy(
            [self.market_pair],
            min_profitability=0.01
        )
        self.logging_options = logging_options
        self.clock.add_iterator(self.market_1)
        self.clock.add_iterator(self.market_2)
        self.clock.add_iterator(self.strategy)

        self.market_1_order_fill_logger: EventLogger = EventLogger()
        self.market_2_order_fill_logger: EventLogger = EventLogger()

        self.market_1.add_listener(MarketEvent.OrderFilled, self.market_1_order_fill_logger)
        self.market_2.add_listener(MarketEvent.OrderFilled, self.market_2_order_fill_logger)

    def test_find_profitable_arbitrage_orders(self):
        pass

    def test_find_best_profitable_amount(self):
        pass

    def test_process_market_pair(self):
        pass

    def test_process_market_pair_inner(self):
        pass

    def test_ready_for_new_orders(self):
        pass

def main():
    unittest.main()


if __name__ == "__main__":
    main()
