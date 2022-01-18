#!/usr/bin/env python
from decimal import Decimal
from nose.plugins.attrib import attr

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
import logging; logging.basicConfig(level=logging.ERROR)
import pandas as pd
from typing import List
import unittest
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent
)
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.strategy.arbitrage.arbitrage import ArbitrageStrategy
from hummingbot.strategy.arbitrage.arbitrage_market_pair import ArbitrageMarketPair
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from test.mock.mock_paper_exchange import MockPaperExchange


@attr('stable')
class ArbitrageUnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    market_1_trading_pairs: List[str] = ["COINALPHA-WETH", "COINALPHA", "WETH"]
    market_2_trading_pairs: List[str] = ["COINALPHA-ETH", "COINALPHA", "ETH"]

    def setUp(self):
        self.maxDiff = None
        self.clock: Clock = Clock(ClockMode.BACKTEST, 1.0, self.start_timestamp, self.end_timestamp)
        self.market_1: MockPaperExchange = MockPaperExchange()
        self.market_2: MockPaperExchange = MockPaperExchange()

        self.market_1.set_balanced_order_book(self.market_1_trading_pairs[0], 1.0, 0.5, 1.5, 0.01, 10)
        self.market_2.set_balanced_order_book(self.market_2_trading_pairs[0], 1.0, 0.5, 1.5, 0.005, 5)

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

        self.strategy: ArbitrageStrategy = ArbitrageStrategy()
        self.strategy.init_params(
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

    def test_arbitrage_profitable(self):
        self.market_1.set_balance("COINALPHA", 5)
        self.market_2.set_balance("COINALPHA", 5)
        self.clock.backtest_til(self.start_timestamp + 1)
        taker_orders = self.strategy.tracked_limit_orders + self.strategy.tracked_market_orders
        market_1_taker_order = [order for market, order in taker_orders
                                if market == self.market_1][0]
        market_2_taker_order = [order for market, order in taker_orders
                                if market == self.market_2][0]

        self.assertTrue(len(taker_orders) == 2)
        # since backet test orders are Marker OrderType, we'll check for *_taker_order.amount
        self.assertEqual(Decimal("5"), market_1_taker_order.amount)
        self.assertEqual(Decimal("5"), market_2_taker_order.amount)

    def test_arbitrage_not_profitable(self):
        self.market_2.order_books[self.market_2_trading_pairs[0]].apply_diffs(
            [OrderBookRow(1.05, 1.0, 2)],
            [], 2)
        self.clock.backtest_til(self.start_timestamp + 1)
        taker_orders = self.strategy.tracked_limit_orders + self.strategy.tracked_market_orders
        self.assertTrue(len(taker_orders) == 0)

    def test_find_best_profitable_amount(self):
        self.market_2.order_books[self.market_2_trading_pairs[0]].apply_diffs(
            [OrderBookRow(1.1, 30, 2)],
            [],
            2
        )
        """
           raw_profitability  bid_price_adjusted  ask_price_adjusted  bid_price  ask_price  step_amount
        0           1.039801               1.045               1.005        1.1      1.005         10.0
        1           1.029557               1.045               1.015        1.1      1.015         20.0
        """
        amount, profitability, bid_price, ask_price = self.strategy.find_best_profitable_amount(self.market_trading_pair_tuple_1,
                                                                                                self.market_trading_pair_tuple_2)
        self.assertEqual(Decimal(30.0), amount)
        self.assertAlmostEqual(Decimal("1.0330510429366988"), profitability)

    def test_min_profitability_limit_1(self):
        self.strategy: ArbitrageStrategy = ArbitrageStrategy()
        self.strategy.init_params(
            [self.market_pair],
            min_profitability=Decimal("0.04"),
            logging_options=self.logging_options,
            secondary_to_primary_quote_conversion_rate=Decimal("0.95")
        )
        self.market_1.order_books[self.market_1_trading_pairs[0]].apply_diffs(
            [],
            [OrderBookRow(1.0, 30, 2)],
            2
        )
        self.market_2.order_books[self.market_2_trading_pairs[0]].apply_diffs(
            [OrderBookRow(1.1, 30, 2), OrderBookRow(1.08, 30, 2)],
            [],
            2
        )
        """" market_1_data
            price  amount  update_id
        0   0.995      10          1
        1   0.985      20          1
        2   0.975      30          1
        3   0.965      40          1
        4   0.955      50          1
            price  amount  update_id
        0       1      30          2
        1   1.005      10          1
        2   1.015      20          1
        3   1.025      30          1
        4   1.035      40          1
        market_2_data
             price  amount  update_id
        0      1.1      30          2 = 1.045
        1     1.08      30          2 = 1.026
        2   0.9975       5          1
        3   0.9925      10          1
        4   0.9875      15          1
            price  amount  update_id
        0  1.1025     105          1
        1  1.1075     110          1
        2  1.1125     115          1
        3  1.1175     120          1
        4  1.1225     125          1
        """
        amount, profitability, bid_price, ask_price = self.strategy.find_best_profitable_amount(self.market_trading_pair_tuple_1,
                                                                                                self.market_trading_pair_tuple_2)
        self.assertEqual(Decimal(30.0), amount)
        self.assertAlmostEqual(Decimal(1.045), profitability)

    def test_min_profitability_limit_2(self):
        self.strategy: ArbitrageStrategy = ArbitrageStrategy()
        self.strategy.init_params(
            [self.market_pair],
            min_profitability=Decimal("0.02"),
            logging_options=self.logging_options,
            secondary_to_primary_quote_conversion_rate=Decimal("0.95")
        )
        self.market_1.order_books[self.market_1_trading_pairs[0]].apply_diffs(
            [],
            [OrderBookRow(1.0, 30, 2)],
            2
        )
        self.market_2.order_books[self.market_2_trading_pairs[0]].apply_diffs(
            [OrderBookRow(1.1, 30, 2), OrderBookRow(1.08, 30, 2)],
            [],
            2
        )
        amount, profitability, bid_price, ask_price = self.strategy.find_best_profitable_amount(self.market_trading_pair_tuple_1,
                                                                                                self.market_trading_pair_tuple_2)
        self.assertEqual(Decimal(60.0), amount)
        self.assertAlmostEqual(Decimal("1.0295457934942913"), profitability)

    def test_asset_limit(self):
        self.market_2.order_books[self.market_2_trading_pairs[0]].apply_diffs(
            [OrderBookRow(1.1, 30, 2)],
            [],
            2
        )
        self.market_1.set_balance("COINALPHA", 40)
        self.market_2.set_balance("COINALPHA", 20)
        amount, profitability, bid_price, ask_price = self.strategy.find_best_profitable_amount(self.market_trading_pair_tuple_1,
                                                                                                self.market_trading_pair_tuple_2)

        self.assertEqual(20.0, amount)
        self.assertAlmostEqual(Decimal("1.0330510429366988"), profitability)

        self.market_2.set_balance("COINALPHA", 0)
        amount, profitability, bid_price, ask_price = self.strategy.find_best_profitable_amount(self.market_trading_pair_tuple_1,
                                                                                                self.market_trading_pair_tuple_2)

        self.assertEqual(Decimal("0"), amount)
        self.assertAlmostEqual(Decimal("1.0399044681062792"), profitability)

    def test_find_profitable_arbitrage_orders(self):
        self.market_2.order_books[self.market_2_trading_pairs[0]].apply_diffs(
            [OrderBookRow(1.1, 30, 2)], [], 2)
        """
        market_1 Ask
        price  amount  update_id
        0  1.005    10.0        1.0
        1  1.015    20.0        1.0
        2  1.025    30.0        1.0
        3  1.035    40.0        1.0
        4  1.045    50.0        1.0
        market_2 Bid
            price  amount  update_id
        0  1.1000    30.0        2.0
        1  0.9975     5.0        1.0
        2  0.9925    10.0        1.0
        3  0.9875    15.0        1.0
        4  0.9825    20.0        1.0
        """
        profitable_orders = ArbitrageStrategy.find_profitable_arbitrage_orders(Decimal("0"),
                                                                               self.market_trading_pair_tuple_1,
                                                                               self.market_trading_pair_tuple_2,
                                                                               Decimal("1"),
                                                                               Decimal("0.95"))
        self.assertEqual(profitable_orders, [
            (Decimal("1.045"), Decimal("1.0049"), Decimal("1.1"), Decimal("1.0049"), Decimal("10.0")),
            (Decimal("1.045"), Decimal("1.0149"), Decimal("1.1"), Decimal("1.0149"), Decimal("20.0"))
        ])
        """
        price  amount  update_id
        0  0.900     5.0        2.0
        1  0.950    15.0        2.0
        2  1.005    10.0        1.0
        3  1.015    20.0        1.0
        4  1.025    30.0        1.0
        market_2 Bid
            price  amount  update_id
        0  1.1000    30.0        2.0
        1  0.9975     5.0        1.0
        2  0.9925    10.0        1.0
        3  0.9875    15.0        1.0
        4  0.9825    20.0        1.0
        """
        self.market_1.order_books[self.market_1_trading_pairs[0]].apply_diffs(
            [],
            [OrderBookRow(0.9, 5, 2), OrderBookRow(0.95, 15, 2)],
            2
        )
        profitable_orders = ArbitrageStrategy.find_profitable_arbitrage_orders(Decimal("0"),
                                                                               self.market_trading_pair_tuple_1,
                                                                               self.market_trading_pair_tuple_2,
                                                                               Decimal("1"),
                                                                               Decimal("0.95"))
        self.assertEqual(profitable_orders, [
            (Decimal("1.045"), Decimal("0.9"), Decimal("1.1"), Decimal("0.9"), Decimal("5.0")),
            (Decimal("1.045"), Decimal("0.94999"), Decimal("1.1"), Decimal("0.94999"), Decimal("15.0")),
            (Decimal("1.045"), Decimal("1.0049"), Decimal("1.1"), Decimal("1.0049"), Decimal("10.0"))
        ])
