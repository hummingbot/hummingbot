#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

import pandas as pd
import unittest
from decimal import Decimal
import asyncio

from hummingsim.backtest.backtest_market import BacktestMarket
from hummingsim.backtest.market import QuantizationParams
from hummingsim.backtest.mock_order_book_loader import MockOrderBookLoader
from hummingbot.core.data_type.order_book_row import OrderBookRow
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
        self._last_clock_tick = 0
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

    async def turn_clock(self, seconds_from_start: float, delay_between_ticks: float = 0.05):
        """
        turns the clock back test one second at a time, with a delay between ticks.
        this is st. the messages in the queues are relayed in a proper sequence.
        """
        for i in range(self._last_clock_tick, seconds_from_start):
            self.clock.backtest_til(self.start_timestamp + self._last_clock_tick + 1)
            self._last_clock_tick += 1
            await asyncio.sleep(delay_between_ticks)

    def test_update_parameters(self):
        self._ev_loop.run_until_complete(self._test_update_parameters())

    async def _test_update_parameters(self):
        try:
            script_file = realpath(join(__file__, "../../scripts/update_parameters_test_script.py"))

            self._script_iterator = ScriptIterator(script_file, [self.market], self.multi_levels_strategy, 0.01, True)
            self.clock.add_iterator(self._script_iterator)
            strategy = self.multi_levels_strategy

            self.clock.add_iterator(strategy)
            await self.turn_clock(1)

            self.assertEqual(3, len(strategy.active_buys))
            self.assertEqual(3, len(strategy.active_sells))

            await self.turn_clock(6)

            strategy.buy_levels = 1
            strategy.sell_levels = 2
            strategy.order_levels = 3
            strategy.bid_spread = Decimal("0.1")
            strategy.ask_spread = Decimal("0.2")
            strategy.hanging_orders_cancel_pct = Decimal("0.3")
            strategy.hanging_orders_enabled = True
            strategy.filled_order_delay = 50.0
            strategy.order_refresh_tolerance_pct = Decimal("0.01")
            strategy.order_refresh_time = 10.0
            strategy.order_level_amount = Decimal("4")
            strategy.order_level_spread = Decimal("0.05")
            strategy.order_amount = Decimal("20")

            strategy.inventory_skew_enabled = True
            strategy.inventory_range_multiplier = 2
            strategy.inventory_target_base_pct = 0.6
            strategy.order_override = {"order_1": ["buy", 0.5, 100], "order_2": ["sell", 0.55, 102]}
        finally:
            self._script_iterator.stop(self.clock)

    def test_price_band_price_ceiling_breach(self):
        self._ev_loop.run_until_complete(self._test_price_band_price_ceiling_breach_async())

    async def _test_price_band_price_ceiling_breach_async(self):
        try:
            script_file = realpath(join(__file__, "../../scripts/price_band_script.py"))
            self._script_iterator = ScriptIterator(script_file, [self.market], self.multi_levels_strategy, 0.01, True)
            self.clock.add_iterator(self._script_iterator)
            strategy = self.multi_levels_strategy

            self.clock.add_iterator(strategy)
            await self.turn_clock(1)

            self.assertEqual(3, len(strategy.active_buys))
            self.assertEqual(3, len(strategy.active_sells))

            simulate_order_book_widening(self.book_data.order_book, self.mid_price, 115, )
            await self.turn_clock(2)

            await self.turn_clock(7)
            self.assertEqual(0, len(strategy.active_buys))
            self.assertEqual(3, len(strategy.active_sells))
        finally:
            self._script_iterator.stop(self.clock)

    def test_price_band_price_floor_breach_async(self):
        self._ev_loop.run_until_complete(self._test_price_band_price_floor_breach_async())

    async def _test_price_band_price_floor_breach_async(self):
        try:
            script_file = realpath(join(__file__, "../../scripts/price_band_script.py"))
            self._script_iterator = ScriptIterator(script_file, [self.market], self.multi_levels_strategy, 0.01, True)
            self.clock.add_iterator(self._script_iterator)

            strategy = self.multi_levels_strategy
            self.clock.add_iterator(strategy)
            await self.turn_clock(1)

            self.assertEqual(3, len(strategy.active_buys))
            self.assertEqual(3, len(strategy.active_sells))

            simulate_order_book_widening(self.book_data.order_book, 85, self.mid_price)
            await self.turn_clock(2)

            await self.turn_clock(7)
            self.assertEqual(3, len(strategy.active_buys))
            self.assertEqual(0, len(strategy.active_sells))
        finally:
            self._script_iterator.stop(self.clock)

    def test_strategy_ping_pong_on_ask_fill(self):
        self._ev_loop.run_until_complete(self._test_strategy_ping_pong_on_ask_fill())

    async def _test_strategy_ping_pong_on_ask_fill(self):
        try:
            script_file = realpath(join(__file__, "../../scripts/ping_pong_script.py"))
            self._script_iterator = ScriptIterator(script_file, [self.market], self.one_level_strategy, 0.01, True)
            self.clock.add_iterator(self._script_iterator)

            strategy = self.one_level_strategy
            self.clock.add_iterator(strategy)

            await self.turn_clock(1)
            self.assertEqual(1, len(strategy.active_buys))
            self.assertEqual(1, len(strategy.active_sells))

            self.simulate_maker_market_trade(True, Decimal(100), Decimal("101.1"))

            await self.turn_clock(2)
            self.assertEqual(1, len(strategy.active_buys))
            self.assertEqual(0, len(strategy.active_sells))
            old_bid = strategy.active_buys[0]

            await self.turn_clock(8)
            self.assertEqual(1, len(strategy.active_buys))
            self.assertEqual(0, len(strategy.active_sells))
            # After new order create cycle (after filled_order_delay), check if a new order is created
            self.assertTrue(old_bid.client_order_id != strategy.active_buys[0].client_order_id)

            self.simulate_maker_market_trade(False, Decimal(100), Decimal("98.9"))
            await self.turn_clock(10)
            await self.turn_clock(15)
            self.assertEqual(1, len(strategy.active_buys))
            self.assertEqual(1, len(strategy.active_sells))
        finally:
            self._script_iterator.stop(self.clock)

    def test_strategy_ping_pong_on_bid_fill(self):
        self._ev_loop.run_until_complete(self._test_strategy_ping_pong_on_bid_fill())

    async def _test_strategy_ping_pong_on_bid_fill(self):
        try:
            script_file = realpath(join(__file__, "../../scripts/ping_pong_script.py"))
            self._script_iterator = ScriptIterator(script_file, [self.market], self.one_level_strategy, 0.01, True)
            self.clock.add_iterator(self._script_iterator)

            strategy = self.one_level_strategy
            self.clock.add_iterator(strategy)

            await self.turn_clock(1)
            self.assertEqual(1, len(strategy.active_buys))
            self.assertEqual(1, len(strategy.active_sells))

            self.simulate_maker_market_trade(False, Decimal(100), Decimal("98.9"))

            await self.turn_clock(2)
            self.assertEqual(0, len(strategy.active_buys))
            self.assertEqual(1, len(strategy.active_sells))
            old_ask = strategy.active_sells[0]

            await self.turn_clock(8)
            self.assertEqual(0, len(strategy.active_buys))
            self.assertEqual(1, len(strategy.active_sells))
            # After new order create cycle (after filled_order_delay), check if a new order is created
            self.assertTrue(old_ask.client_order_id != strategy.active_sells[0].client_order_id)

            self.simulate_maker_market_trade(True, Decimal(100), Decimal("101.1"))
            await self.turn_clock(10)
            await self.turn_clock(15)
            self.assertEqual(1, len(strategy.active_buys))
            self.assertEqual(1, len(strategy.active_sells))
        finally:
            self._script_iterator.stop(self.clock)

    def test_dynamic_price_band_price(self):
        self._ev_loop.run_until_complete(self._test_dynamic_price_band_price_async())

    async def _test_dynamic_price_band_price_async(self):
        try:
            script_file = realpath(join(__file__, "../../scripts/dynamic_price_band_script.py"))
            self._script_iterator = ScriptIterator(script_file, [self.market], self.multi_levels_strategy, 0.01, True)
            self.clock.add_iterator(self._script_iterator)

            strategy = self.multi_levels_strategy
            self.clock.add_iterator(strategy)
            await self.turn_clock(1)

            self.assertEqual(3, len(strategy.active_buys))
            self.assertEqual(3, len(strategy.active_sells))

            await self.turn_clock(4)
            # self.book_data.order_book.apply_diffs([OrderBookRow(99.97, 30, 2)], [OrderBookRow(100.3, 30, 2)], 2)
            simulate_order_book_widening(self.book_data.order_book, 85, self.mid_price)
            mid_price = self.market.get_mid_price(self.trading_pair)
            await self.turn_clock(10)
            mid_price = self.market.get_mid_price(self.trading_pair)
            print(mid_price)
            self.assertLess(mid_price, Decimal(100 * 0.97))
            # mid_price is now below 3% from the original (at 92.5), but band script won't kick in until at least 50s
            self.assertEqual(3, len(strategy.active_buys))
            self.assertEqual(3, len(strategy.active_sells))
            await self.turn_clock(55)
            self.assertEqual(3, len(strategy.active_buys))
            self.assertEqual(3, len(strategy.active_sells))
            simulate_order_book_widening(self.book_data.order_book, 75, self.mid_price)
            self.book_data.order_book.apply_diffs([], [OrderBookRow(76, 30, 2)], 2)
            mid_price = self.market.get_mid_price(self.trading_pair)
            print(mid_price)
            await self.turn_clock(80)
            self.assertEqual(3, len(strategy.active_buys))
            self.assertEqual(0, len(strategy.active_sells))
            # after another 40 ticks, the mid price avg is now at 75.25, both buys and sells back on the market
            await self.turn_clock(110)
            self.assertEqual(3, len(strategy.active_buys))
            self.assertEqual(3, len(strategy.active_sells))

            simulate_order_book_widening(self.book_data.order_book, 76, 90)
            self.book_data.order_book.apply_diffs([OrderBookRow(85, 30, 2)], [OrderBookRow(86, 30, 2)], 3)
            mid_price = self.market.get_mid_price(self.trading_pair)
            print(mid_price)
            # Market now move up over 10%
            await self.turn_clock(120)
            self.assertEqual(0, len(strategy.active_buys))
            self.assertEqual(3, len(strategy.active_sells))
            # As no further movement in market prices, avg starts to catch up to the mid price
            await self.turn_clock(160)
            self.assertEqual(3, len(strategy.active_buys))
            self.assertEqual(3, len(strategy.active_sells))
        finally:
            self._script_iterator.stop(self.clock)

    def test_spreads_adjusted_on_volatility(self):
        self._ev_loop.run_until_complete(self._test_spreads_adjusted_on_volatility_async())

    async def _test_spreads_adjusted_on_volatility_async(self):
        try:
            script_file = realpath(join(__file__, "../../scripts/spreads_adjusted_on_volatility_script.py"))
            self._script_iterator = ScriptIterator(script_file, [self.market], self.one_level_strategy, 0.01, True)
            self.clock.add_iterator(self._script_iterator)

            strategy = self.one_level_strategy
            self.clock.add_iterator(strategy)
            await self.turn_clock(1)

            self.assertEqual(1, len(strategy.active_buys))
            self.assertEqual(1, len(strategy.active_sells))
            self.assertEqual(Decimal("0.01"), strategy.bid_spread)
            self.assertEqual(Decimal("0.01"), strategy.ask_spread)
            await self.turn_clock(155)
            self.assertEqual(1, len(strategy.active_buys))
            self.assertEqual(1, len(strategy.active_sells))
            simulate_order_book_widening(self.book_data.order_book, 100, 105)
            self.book_data.order_book.apply_diffs([OrderBookRow(100, 30, 2)], [], 2)
            await self.turn_clock(160)
            mid_price = self.market.get_mid_price(self.trading_pair)
            print(mid_price)
            # The median volatility over the long period is at 0
            # The average volatility over the short period is now at 0.00916
            # So the adjustment is 0.0075 (rounded by 0.0025 increment)
            # await self.turn_clock(161)
            self.assertEqual(Decimal("0.0175"), strategy.bid_spread)
            self.assertEqual(Decimal("0.0175"), strategy.ask_spread)
            self.assertEqual(1, len(strategy.active_buys))
            self.assertEqual(1, len(strategy.active_sells))
            await self.turn_clock(185)
            # No more further price movement, which means volatility is now back to 0.
            # Spreads are adjusted back to the originals
            self.assertEqual(Decimal("0.01"), strategy.bid_spread)
            self.assertEqual(Decimal("0.01"), strategy.ask_spread)
            self.assertEqual(1, len(strategy.active_buys))
            self.assertEqual(1, len(strategy.active_sells))
        finally:
            self._script_iterator.stop(self.clock)
