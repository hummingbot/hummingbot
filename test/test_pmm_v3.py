#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from decimal import Decimal
import logging; logging.basicConfig(level=logging.ERROR)
import pandas as pd
import unittest
from hummingsim.backtest.backtest_market import BacktestMarket
from hummingsim.backtest.market import QuantizationParams
from hummingsim.backtest.mock_order_book_loader import MockOrderBookLoader
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
    OrderBookTradeEvent,
    TradeType
)
from hummingbot.strategy.pure_market_making.pure_market_making_v3 import PureMarketMakingStrategyV3


class PMMV3UnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    trading_pair = "HBOT-ETH"
    base_asset = trading_pair.split("-")[0]
    quote_asset = trading_pair.split("-")[1]

    def setUp(self):
        self.clock_tick_size = 1
        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)
        self.market: BacktestMarket = BacktestMarket()
        self.book_data: MockOrderBookLoader = MockOrderBookLoader(self.trading_pair, self.base_asset, self.quote_asset)
        self.mid_price = 100
        self.bid_spread = 0.01
        self.ask_spread = 0.01
        self.order_refresh_time = 30
        self.book_data.set_balanced_order_book(mid_price=self.mid_price,
                                               min_price=1,
                                               max_price=200,
                                               price_step_size=1,
                                               volume_step_size=10)
        self.market.add_data(self.book_data)
        self.market.set_balance("HBOT", 50)
        self.market.set_balance("ETH", 500)
        self.market.set_quantization_param(
            QuantizationParams(
                self.trading_pair, 6, 6, 6, 6
            )
        )
        self.market_info = MarketTradingPairTuple(self.market, self.trading_pair,
                                                  self.base_asset, self.quote_asset)
        self.clock.add_iterator(self.market)
        self.maker_order_fill_logger: EventLogger = EventLogger()
        self.cancel_order_logger: EventLogger = EventLogger()
        self.market.add_listener(MarketEvent.OrderFilled, self.maker_order_fill_logger)
        self.market.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)

    def simulate_maker_market_trade(self, is_buy: bool, quantity: Decimal, price: Decimal):
        order_book = self.market.get_order_book(self.trading_pair)
        trade_event = OrderBookTradeEvent(
            self.trading_pair,
            self.clock.current_timestamp,
            TradeType.BUY if is_buy else TradeType.SELL,
            price,
            quantity
        )
        order_book.apply_trade(trade_event)

    def test_basic_one_level(self):
        self.strategy = PureMarketMakingStrategyV3(
            self.market_info,
            bid_spread=Decimal("0.01"),
            ask_spread=Decimal("0.01"),
            order_amount=Decimal("1"),
            order_refresh_time=5.0,
            filled_order_delay=5.0,
            order_refresh_tolerance_pct=-1
        )
        self.clock.add_iterator(self.strategy)

        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(1, len(self.strategy.active_sells))
        buy_1 = self.strategy.active_buys[0]
        self.assertEqual(99, buy_1.price)
        self.assertEqual(1, buy_1.quantity)
        sell_1 = self.strategy.active_sells[0]
        self.assertEqual(101, sell_1.price)
        self.assertEqual(1, sell_1.quantity)

        # After order_refresh_time, a new set of orders is created
        self.clock.backtest_til(self.start_timestamp + 7)
        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(1, len(self.strategy.active_sells))
        self.assertNotEqual(buy_1.client_order_id, self.strategy.active_buys[0].client_order_id)
        self.assertNotEqual(sell_1.client_order_id, self.strategy.active_sells[0].client_order_id)

        # Simulate buy order filled
        self.clock.backtest_til(self.start_timestamp + 8)
        self.simulate_maker_market_trade(False, 100, 98.9)
        self.assertEqual(0, len(self.strategy.active_buys))
        self.assertEqual(1, len(self.strategy.active_sells))

        # After filled_ore
        self.clock.backtest_til(self.start_timestamp + 14)
        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(1, len(self.strategy.active_sells))

    def test_basic_multiple_levels(self):
        self.strategy = PureMarketMakingStrategyV3(
            self.market_info,
            bid_spread=Decimal("0.01"),
            ask_spread=Decimal("0.01"),
            order_amount=Decimal("1"),
            order_refresh_time=5.0,
            filled_order_delay=5.0,
            order_refresh_tolerance_pct=-1,
            order_levels=3,
            order_level_spread=Decimal("0.01"),
            order_level_amount=Decimal("1")
        )
        self.clock.add_iterator(self.strategy)

        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(3, len(self.strategy.active_buys))
        self.assertEqual(3, len(self.strategy.active_sells))
        buys = self.strategy.active_buys
        sells = self.strategy.active_sells
        self.assertEqual(3, len(buys))
        self.assertEqual(3, len(sells))
        self.assertEqual(Decimal("99"), buys[0].price)
        self.assertEqual(Decimal("1"), buys[0].quantity)
        self.assertEqual(Decimal("98"), buys[1].price)
        self.assertEqual(Decimal("2"), buys[1].quantity)
        self.assertEqual(Decimal("101"), sells[0].price)
        self.assertEqual(Decimal("1"), sells[0].quantity)
        self.assertEqual(Decimal("103"), sells[2].price)
        self.assertEqual(Decimal("3"), sells[2].quantity)

        # After order_refresh_time, a new set of orders is created
        self.clock.backtest_til(self.start_timestamp + 7)
        self.assertEqual(3, len(self.strategy.active_buys))
        self.assertEqual(3, len(self.strategy.active_sells))
        self.assertNotEqual(buys[0].client_order_id, self.strategy.active_buys[0].client_order_id)
        self.assertNotEqual(sells[0].client_order_id, self.strategy.active_sells[0].client_order_id)

        # Simulate buy order filled
        self.clock.backtest_til(self.start_timestamp + 8)
        self.simulate_maker_market_trade(False, 100, 97.9)
        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(3, len(self.strategy.active_sells))

        # After filled_ore
        self.clock.backtest_til(self.start_timestamp + 14)
        self.assertEqual(3, len(self.strategy.active_buys))
        self.assertEqual(3, len(self.strategy.active_sells))
