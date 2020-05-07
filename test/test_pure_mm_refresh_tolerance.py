#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from decimal import Decimal
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
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.strategy.pure_market_making.pure_market_making_v2 import PureMarketMakingStrategyV2
from hummingbot.strategy.pure_market_making import (
    ConstantSpreadPricingDelegate,
    PassThroughFilterDelegate,
    ConstantMultipleSpreadPricingDelegate,
    ConstantSizeSizingDelegate,
    StaggeredMultipleSizeSizingDelegate,
)
from test.test_pure_market_making_v2 import simulate_limit_order_fill


class PureMMRefreshToleranceUnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    maker_trading_pairs: List[str] = ["COINALPHA-WETH", "COINALPHA", "WETH"]

    def setUp(self):
        self.clock_tick_size = 1
        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)
        self.maker_market: BacktestMarket = BacktestMarket()
        self.maker_data: MockOrderBookLoader = MockOrderBookLoader(*self.maker_trading_pairs)
        self.mid_price = 100
        self.bid_spread = 0.01
        self.ask_spread = 0.01
        self.order_refresh_time = 30
        self.maker_data.set_balanced_order_book(mid_price=self.mid_price, min_price=1,
                                                max_price=200, price_step_size=1, volume_step_size=10)
        self.constant_pricing_delegate = ConstantSpreadPricingDelegate(Decimal(self.bid_spread),
                                                                       Decimal(self.ask_spread))
        self.constant_sizing_delegate = ConstantSizeSizingDelegate(Decimal("1.0"))
        self.filter_delegate = PassThroughFilterDelegate()
        self.maker_market.add_data(self.maker_data)
        self.maker_market.set_balance("COINALPHA", 500)
        self.maker_market.set_balance("WETH", 5000)
        self.maker_market.set_balance("QETH", 500)
        self.maker_market.set_quantization_param(
            QuantizationParams(
                self.maker_trading_pairs[0], 6, 6, 6, 6
            )
        )
        self.market_info: MarketTradingPairTuple = MarketTradingPairTuple(
            *([self.maker_market] + self.maker_trading_pairs)
        )

        logging_options: int = (PureMarketMakingStrategyV2.OPTION_LOG_ALL &
                                (~PureMarketMakingStrategyV2.OPTION_LOG_NULL_ORDER_SIZE))

        self.one_level_strategy: PureMarketMakingStrategyV2 = PureMarketMakingStrategyV2(
            [self.market_info],
            filter_delegate=self.filter_delegate,
            pricing_delegate=self.constant_pricing_delegate,
            sizing_delegate=self.constant_sizing_delegate,
            order_refresh_time=4,
            filled_order_delay=8,
            hanging_orders_enabled=True,
            logging_options=logging_options,
            hanging_orders_cancel_pct=0.05,
            order_refresh_tolerance_pct=0
        )
        self.multiple_order_pricing_delegate = ConstantMultipleSpreadPricingDelegate(
            bid_spread=Decimal(self.bid_spread),
            ask_spread=Decimal(self.ask_spread),
            order_level_spread=Decimal("0.01"),
            order_levels=Decimal("5")
        )
        self.equal_sizing_delegate = StaggeredMultipleSizeSizingDelegate(
            order_start_size=Decimal("1.0"),
            order_step_size=Decimal("0"),
            order_levels=Decimal("5")
        )
        self.multi_levels_strategy: PureMarketMakingStrategyV2 = PureMarketMakingStrategyV2(
            [self.market_info],
            filter_delegate=self.filter_delegate,
            pricing_delegate=self.multiple_order_pricing_delegate,
            sizing_delegate=self.equal_sizing_delegate,
            order_refresh_time=4,
            filled_order_delay=8,
            hanging_orders_enabled=True,
            logging_options=logging_options,
            hanging_orders_cancel_pct=0.1,
            order_refresh_tolerance_pct=0
        )

        self.hanging_order_multiple_strategy: PureMarketMakingStrategyV2 = PureMarketMakingStrategyV2(
            [self.market_info],
            filter_delegate=self.filter_delegate,
            pricing_delegate=self.multiple_order_pricing_delegate,
            sizing_delegate=self.equal_sizing_delegate,
            order_refresh_time=4,
            filled_order_delay=8,
            hanging_orders_enabled=True,
            logging_options=logging_options,
            order_refresh_tolerance_pct=0
        )
        self.logging_options = logging_options
        self.clock.add_iterator(self.maker_market)
        self.maker_order_fill_logger: EventLogger = EventLogger()
        self.cancel_order_logger: EventLogger = EventLogger()
        self.maker_market.add_listener(MarketEvent.OrderFilled, self.maker_order_fill_logger)
        self.maker_market.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)

    def test_active_orders_are_cancelled_when_mid_price_moves(self):
        strategy = self.one_level_strategy
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(strategy.active_bids))
        self.assertEqual(1, len(strategy.active_asks))
        old_bid = strategy.active_bids[0][1]
        old_ask = strategy.active_asks[0][1]
        # Not the order refresh time yet, orders should remain the same
        self.clock.backtest_til(self.start_timestamp + 3 * self.clock_tick_size)
        self.assertEqual(1, len(strategy.active_bids))
        self.assertEqual(1, len(strategy.active_asks))
        self.assertEqual(old_bid.client_order_id, strategy.active_bids[0][1].client_order_id)
        self.assertEqual(old_ask.client_order_id, strategy.active_asks[0][1].client_order_id)
        self.maker_data.order_book.apply_diffs([OrderBookRow(99.5, 30, 2)], [OrderBookRow(100.1, 30, 2)], 2)
        self.clock.backtest_til(self.start_timestamp + 6 * self.clock_tick_size)
        new_bid = strategy.active_bids[0][1]
        new_ask = strategy.active_asks[0][1]
        self.assertEqual(1, len(strategy.active_bids))
        self.assertEqual(1, len(strategy.active_asks))
        self.assertNotEqual(old_ask, new_ask)
        self.assertNotEqual(old_bid, new_bid)

    def test_active_orders_are_kept_when_within_tolerance(self):
        strategy = self.one_level_strategy
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(strategy.active_bids))
        self.assertEqual(1, len(strategy.active_asks))
        old_bid = strategy.active_bids[0][1]
        old_ask = strategy.active_asks[0][1]
        self.clock.backtest_til(self.start_timestamp + 6 * self.clock_tick_size)
        self.assertEqual(1, len(strategy.active_bids))
        self.assertEqual(1, len(strategy.active_asks))
        new_bid = strategy.active_bids[0][1]
        new_ask = strategy.active_asks[0][1]
        self.assertEqual(old_ask, new_ask)
        self.assertEqual(old_bid, new_bid)
        self.clock.backtest_til(self.start_timestamp + 10 * self.clock_tick_size)
        self.assertEqual(1, len(strategy.active_bids))
        self.assertEqual(1, len(strategy.active_asks))
        new_bid = strategy.active_bids[0][1]
        new_ask = strategy.active_asks[0][1]
        self.assertEqual(old_ask, new_ask)
        self.assertEqual(old_bid, new_bid)

    def test_multi_levels_active_orders_are_cancelled_when_mid_price_moves(self):
        strategy = self.multi_levels_strategy
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(5, len(strategy.active_bids))
        self.assertEqual(5, len(strategy.active_asks))
        old_bids = strategy.active_bids
        old_asks = strategy.active_asks
        self.maker_data.order_book.apply_diffs([OrderBookRow(99.5, 30, 2)], [OrderBookRow(100.1, 30, 2)], 2)
        self.clock.backtest_til(self.start_timestamp + 6 * self.clock_tick_size)
        new_bids = strategy.active_bids
        new_asks = strategy.active_asks
        self.assertEqual(5, len(strategy.active_bids))
        self.assertEqual(5, len(strategy.active_asks))
        self.assertNotEqual([o[1].client_order_id for o in old_asks], [o[1].client_order_id for o in new_asks])
        self.assertNotEqual([o[1].client_order_id for o in old_bids], [o[1].client_order_id for o in new_bids])

    def test_multiple_active_orders_are_kept_when_within_tolerance(self):
        strategy = self.multi_levels_strategy
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(5, len(strategy.active_bids))
        self.assertEqual(5, len(strategy.active_asks))
        old_bids = strategy.active_bids
        old_asks = strategy.active_asks
        self.clock.backtest_til(self.start_timestamp + 6 * self.clock_tick_size)
        self.assertEqual(5, len(strategy.active_bids))
        self.assertEqual(5, len(strategy.active_asks))
        new_bids = strategy.active_bids
        new_asks = strategy.active_asks
        self.assertEqual([o[1].client_order_id for o in old_asks], [o[1].client_order_id for o in new_asks])
        self.assertEqual([o[1].client_order_id for o in old_bids], [o[1].client_order_id for o in new_bids])
        self.clock.backtest_til(self.start_timestamp + 10 * self.clock_tick_size)
        self.assertEqual(5, len(strategy.active_bids))
        self.assertEqual(5, len(strategy.active_asks))
        new_bids = strategy.active_bids
        new_asks = strategy.active_asks
        self.assertEqual([o[1].client_order_id for o in old_asks], [o[1].client_order_id for o in new_asks])
        self.assertEqual([o[1].client_order_id for o in old_bids], [o[1].client_order_id for o in new_bids])

    def test_hanging_orders_multiple_orders_with_refresh_tolerance(self):
        strategy = self.hanging_order_multiple_strategy
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(5, len(strategy.active_bids))
        self.assertEqual(5, len(strategy.active_asks))
        ask_order = strategy.active_asks[0][1]

        simulate_limit_order_fill(self.maker_market, ask_order)

        # Ask is filled and due to delay is not replenished immediately
        # Bid orders are now hanging and active
        self.clock.backtest_til(self.start_timestamp + 2 * self.clock_tick_size)
        self.assertEqual(1, len(self.maker_order_fill_logger.event_log))
        self.assertEqual(5, len(strategy.active_bids))
        self.assertEqual(4, len(strategy.active_asks))
        self.assertEqual(5, len(strategy.hanging_order_ids))

        # At order_refresh_time (4 seconds), hanging order remains, asks all got canceled
        self.clock.backtest_til(self.start_timestamp + 5 * self.clock_tick_size)
        self.assertEqual(5, len(strategy.active_bids))
        self.assertEqual(0, len(strategy.active_asks))

        # At filled_order_delay (8 seconds), new sets of bid and ask orders are created
        self.clock.backtest_til(self.start_timestamp + 10 * self.clock_tick_size)
        self.assertEqual(10, len(strategy.active_bids))
        self.assertEqual(5, len(strategy.active_asks))

        # Check all hanging order ids are indeed in active bids list
        self.assertTrue(all(h in [order.client_order_id for market, order in strategy.active_bids]
                            for h in strategy.hanging_order_ids))

        old_bids = [o[1] for o in strategy.active_bids if o[1].client_order_id not in strategy.hanging_order_ids]
        old_asks = [o[1] for o in strategy.active_asks if o[1].client_order_id not in strategy.hanging_order_ids]

        self.clock.backtest_til(self.start_timestamp + 15 * self.clock_tick_size)
        self.assertEqual(10, len(strategy.active_bids))
        self.assertEqual(5, len(strategy.active_asks))

        new_bids = [o[1] for o in strategy.active_bids if o[1].client_order_id not in strategy.hanging_order_ids]
        new_asks = [o[1] for o in strategy.active_asks if o[1].client_order_id not in strategy.hanging_order_ids]
        self.assertEqual([o.client_order_id for o in old_asks], [o.client_order_id for o in new_asks])
        self.assertEqual([o.client_order_id for o in old_bids], [o.client_order_id for o in new_bids])
