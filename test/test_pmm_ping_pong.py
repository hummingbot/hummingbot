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
from hummingsim.backtest.market import QuantizationParams
from hummingsim.backtest.mock_order_book_loader import MockOrderBookLoader
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
    OrderBookTradeEvent,
    TradeType
)
from hummingbot.strategy.pure_market_making.pure_market_making_v2 import PureMarketMakingStrategyV2
from hummingbot.strategy.pure_market_making import (
    ConstantSpreadPricingDelegate,
    PassThroughFilterDelegate,
    ConstantMultipleSpreadPricingDelegate,
    ConstantSizeSizingDelegate,
    StaggeredMultipleSizeSizingDelegate,
)


class PureMMPingPongUnitTest(unittest.TestCase):
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
        self.maker_data.set_balanced_order_book(mid_price=self.mid_price,
                                                min_price=1,
                                                max_price=200,
                                                price_step_size=1,
                                                volume_step_size=10)
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

        self.clock.add_iterator(self.maker_market)
        self.maker_order_fill_logger: EventLogger = EventLogger()
        self.cancel_order_logger: EventLogger = EventLogger()
        self.maker_market.add_listener(MarketEvent.OrderFilled, self.maker_order_fill_logger)
        self.maker_market.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)

    def simulate_maker_market_trade(self, is_buy: bool, quantity: Decimal, price: Decimal):
        maker_trading_pair: str = self.maker_trading_pairs[0]
        order_book = self.maker_market.get_order_book(maker_trading_pair)
        trade_event = OrderBookTradeEvent(
            maker_trading_pair,
            self.clock.current_timestamp,
            TradeType.BUY if is_buy else TradeType.SELL,
            price,
            quantity
        )
        order_book.apply_trade(trade_event)

    def test_strategy_ping_pong_on_ask_fill(self):
        self.strategy: PureMarketMakingStrategyV2 = PureMarketMakingStrategyV2(
            [self.market_info],
            filter_delegate=self.filter_delegate,
            sizing_delegate=self.constant_sizing_delegate,
            pricing_delegate=self.constant_pricing_delegate,
            order_refresh_time=5,
            filled_order_delay=5,
            order_refresh_tolerance_pct=-1,
            ping_pong_enabled=True,
        )
        self.clock.add_iterator(self.strategy)

        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))

        self.simulate_maker_market_trade(True, Decimal(100), Decimal("101.1"))

        self.clock.backtest_til(
            self.start_timestamp + 2 * self.clock_tick_size
        )
        self.assertEqual(1, len(self.strategy.active_bids))
        self.assertEqual(0, len(self.strategy.active_asks))
        old_bid = self.strategy.active_bids[0][1]

        self.clock.backtest_til(
            self.start_timestamp + 7 * self.clock_tick_size
        )
        self.assertEqual(1, len(self.strategy.active_bids))
        self.assertEqual(0, len(self.strategy.active_asks))
        # After new order create cycle (after filled_order_delay), check if a new order is created
        self.assertTrue(old_bid.client_order_id != self.strategy.active_bids[0][1].client_order_id)

        self.simulate_maker_market_trade(False, Decimal(100), Decimal("98.9"))

        self.clock.backtest_til(
            self.start_timestamp + 15 * self.clock_tick_size
        )
        self.assertEqual(1, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))

    def test_strategy_ping_pong_on_bid_fill(self):
        self.strategy: PureMarketMakingStrategyV2 = PureMarketMakingStrategyV2(
            [self.market_info],
            filter_delegate=self.filter_delegate,
            sizing_delegate=self.constant_sizing_delegate,
            pricing_delegate=self.constant_pricing_delegate,
            order_refresh_time=5,
            filled_order_delay=5,
            order_refresh_tolerance_pct=-1,
            ping_pong_enabled=True,
        )
        self.clock.add_iterator(self.strategy)

        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))

        self.simulate_maker_market_trade(False, Decimal(100), Decimal("98.9"))

        self.clock.backtest_til(
            self.start_timestamp + 2 * self.clock_tick_size
        )
        self.assertEqual(0, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))
        old_ask = self.strategy.active_asks[0][1]

        self.clock.backtest_til(
            self.start_timestamp + 7 * self.clock_tick_size
        )
        self.assertEqual(0, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))

        # After new order create cycle (after filled_order_delay), check if a new order is created
        self.assertTrue(old_ask.client_order_id != self.strategy.active_asks[0][1].client_order_id)

        self.simulate_maker_market_trade(True, Decimal(100), Decimal("101.1"))

        self.clock.backtest_til(
            self.start_timestamp + 15 * self.clock_tick_size
        )
        self.assertEqual(1, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))

    def test_multiple_orders_ping_pong(self):
        logging_options: int = (PureMarketMakingStrategyV2.OPTION_LOG_ALL &
                                (~PureMarketMakingStrategyV2.OPTION_LOG_NULL_ORDER_SIZE))
        self.strategy: PureMarketMakingStrategyV2 = PureMarketMakingStrategyV2(
            [self.market_info],
            logging_options=logging_options,
            filter_delegate=self.filter_delegate,
            pricing_delegate=self.multiple_order_pricing_delegate,
            sizing_delegate=self.equal_sizing_delegate,
            order_refresh_time=5,
            order_refresh_tolerance_pct=-1,
            filled_order_delay=5,
            ping_pong_enabled=True,
        )
        self.clock.add_iterator(self.strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)

        self.assertEqual(5, len(self.strategy.active_bids))
        self.assertEqual(5, len(self.strategy.active_asks))

        self.simulate_maker_market_trade(True, Decimal(100), Decimal("102.50"))
        # After market trade happens, 2 of the asks orders are filled.
        self.assertEqual(5, len(self.strategy.active_bids))
        self.assertEqual(3, len(self.strategy.active_asks))
        self.clock.backtest_til(
            self.start_timestamp + 2 * self.clock_tick_size
        )
        # Not refreshing time yet, still same active orders
        self.assertEqual(5, len(self.strategy.active_bids))
        self.assertEqual(3, len(self.strategy.active_asks))
        old_bids = self.strategy.active_bids
        old_asks = self.strategy.active_asks
        self.clock.backtest_til(
            self.start_timestamp + 7 * self.clock_tick_size
        )
        # After order refresh, same numbers of orders but it's a new set.
        self.assertEqual(5, len(self.strategy.active_bids))
        self.assertEqual(3, len(self.strategy.active_asks))
        self.assertNotEqual([o[1].client_order_id for o in old_asks],
                            [o[1].client_order_id for o in self.strategy.active_asks])
        self.assertNotEqual([o[1].client_order_id for o in old_bids],
                            [o[1].client_order_id for o in self.strategy.active_bids])

        # Simulate sell trade, the first bid gets taken out
        self.simulate_maker_market_trade(False, Decimal(100), Decimal("98.9"))
        self.assertEqual(4, len(self.strategy.active_bids))
        self.assertEqual(3, len(self.strategy.active_asks))
        self.clock.backtest_til(
            self.start_timestamp + 13 * self.clock_tick_size
        )

        # After refresh, still the same numbers of orders
        self.assertEqual(4, len(self.strategy.active_bids))
        self.assertEqual(3, len(self.strategy.active_asks))

        # Another bid order is filled.
        self.simulate_maker_market_trade(False, Decimal(100), Decimal("97.9"))
        self.assertEqual(3, len(self.strategy.active_bids))
        self.assertEqual(3, len(self.strategy.active_asks))

        self.clock.backtest_til(
            self.start_timestamp + 20 * self.clock_tick_size
        )

        # After refresh, numbers of orders back to order_levels of 5
        self.assertEqual(5, len(self.strategy.active_bids))
        self.assertEqual(5, len(self.strategy.active_asks))
