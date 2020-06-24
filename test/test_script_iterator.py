#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

import pandas as pd
import unittest
from decimal import Decimal
import inspect
import asyncio

from hummingsim.backtest.backtest_market import BacktestMarket
from hummingsim.backtest.market import QuantizationParams
from hummingsim.backtest.mock_order_book_loader import MockOrderBookLoader

from hummingbot.core.clock import Clock, ClockMode
from hummingbot.script.script_iterator import ScriptIterator
from hummingbot.strategy.pure_market_making import PureMarketMakingStrategy
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.core.event.events import (
    OrderBookTradeEvent,
    TradeType
)
from test.test_pmm import simulate_order_book_widening


class ScriptIteratorUnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    trading_pair = "HBOT-ETH"
    base_asset = trading_pair.split("-")[0]
    quote_asset = trading_pair.split("-")[1]

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
        self.market.set_balance("HBOT", 500)
        self.market.set_balance("ETH", 5000)
        self.market.set_quantization_param(
            QuantizationParams(
                self.trading_pair, 6, 6, 6, 6
            )
        )
        self.market_info = MarketTradingPairTuple(self.market, self.trading_pair,
                                                  self.base_asset, self.quote_asset)
        self.clock.add_iterator(self.market)
        self.one_level_strategy = PureMarketMakingStrategy(
            self.market_info,
            bid_spread=Decimal("0.01"),
            ask_spread=Decimal("0.01"),
            order_amount=Decimal("1"),
            order_refresh_time=5.0,
            filled_order_delay=5.0,
            order_refresh_tolerance_pct=-1,
            minimum_spread=-1,
        )
        self.multi_levels_strategy = PureMarketMakingStrategy(
            self.market_info,
            bid_spread=Decimal("0.01"),
            ask_spread=Decimal("0.01"),
            order_amount=Decimal("1"),
            order_refresh_time=5.0,
            filled_order_delay=5.0,
            order_refresh_tolerance_pct=-1,
            order_levels=3,
            order_level_spread=Decimal("0.01"),
            order_level_amount=Decimal("1"),
            minimum_spread=-1,
        )
        self._ev_loop = asyncio.get_event_loop()

    def test_price_band_price_ceiling_breach(self):
        self._ev_loop.run_until_complete(self._test_price_band_price_ceiling_breach_async())

    async def _test_price_band_price_ceiling_breach_async(self):
        # script_file = "/Users/jack/github/hummingbot/test/scripts/price_band_script.py"
        self._script_iterator = ScriptIterator("none", [self.market], self.multi_levels_strategy, 0.0)
        # self._script_iterator.start_process()
        self.clock.add_iterator(self._script_iterator)
        #
        strategy = self.multi_levels_strategy
        # strategy.price_ceiling = Decimal("105")

        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

        self.clock.backtest_til(self.start_timestamp + 2)
        await asyncio.sleep(1)
        # parent_queue.put(OnTick(Decimal(100), StrategyParameters(1, 2, 3)))
        # simulate_order_book_widening(self.book_data.order_book, self.mid_price, 115, )
        # import time
        # time.sleep(2)
        # parent_queue.put(None)
        # time.sleep(1)
        # script_process.join()
        # return
        # self.clock.backtest_til(self.start_timestamp + 7)
        # self.assertEqual(0, len(strategy.active_buys))
        # self.assertEqual(3, len(strategy.active_sells))
        self._script_iterator.stop(self.clock)

    def test_price_band_price_floor_breach(self):
        script_file = "scripts/price_band_script.py"
        self._script_iterator = ScriptIterator(script_file, [self.market], self.multi_levels_strategy)
        self.clock.add_iterator(self._script_iterator)
        strategy = self.multi_levels_strategy
        # strategy.price_floor = Decimal("95")

        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

        simulate_order_book_widening(self.book_data.order_book, 85, self.mid_price)

        self.clock.backtest_til(self.start_timestamp + 7)
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))

    def get_writeable_properties(self, cls):
        return [attr for attr, value in vars(cls).items()
                if inspect.isgetsetdescriptor(value)]

    def test_dir(self):
        attrs = self.get_writeable_properties(PureMarketMakingStrategy)
        print(attrs)
        members = inspect.isgetsetdescriptor(self.one_level_strategy.buy_levels)
        [print(m) for m in members]
