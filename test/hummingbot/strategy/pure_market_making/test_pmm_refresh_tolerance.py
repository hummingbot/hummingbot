#!/usr/bin/env python
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from decimal import Decimal
import logging; logging.basicConfig(level=logging.ERROR)
import pandas as pd
import unittest
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
    OrderBookTradeEvent,
    TradeType
)
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.strategy.pure_market_making.pure_market_making import PureMarketMakingStrategy
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from test.mock.mock_paper_exchange import MockPaperExchange


class PMMRefreshToleranceUnitTest(unittest.TestCase):
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
        self.market: MockPaperExchange = MockPaperExchange()
        self.mid_price = 100
        self.bid_spread = 0.01
        self.ask_spread = 0.01
        self.order_refresh_time = 30
        self.market.set_balanced_order_book(trading_pair=self.trading_pair,
                                            mid_price=self.mid_price,
                                            min_price=1,
                                            max_price=200,
                                            price_step_size=1,
                                            volume_step_size=10)
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
        self.maker_order_fill_logger: EventLogger = EventLogger()
        self.cancel_order_logger: EventLogger = EventLogger()
        self.market.add_listener(MarketEvent.OrderFilled, self.maker_order_fill_logger)
        self.market.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)

        self.one_level_strategy: PureMarketMakingStrategy = PureMarketMakingStrategy()
        self.one_level_strategy.init_params(
            self.market_info,
            bid_spread=Decimal("0.01"),
            ask_spread=Decimal("0.01"),
            order_amount=Decimal("1"),
            order_refresh_time=4,
            filled_order_delay=8,
            hanging_orders_enabled=True,
            hanging_orders_cancel_pct=0.05,
            order_refresh_tolerance_pct=0
        )
        self.multi_levels_strategy: PureMarketMakingStrategy = PureMarketMakingStrategy()
        self.multi_levels_strategy.init_params(
            self.market_info,
            bid_spread=Decimal("0.01"),
            ask_spread=Decimal("0.01"),
            order_amount=Decimal("1"),
            order_levels=5,
            order_level_spread=Decimal("0.01"),
            order_refresh_time=4,
            filled_order_delay=8,
            order_refresh_tolerance_pct=0
        )
        self.hanging_order_multiple_strategy = PureMarketMakingStrategy()
        self.hanging_order_multiple_strategy.init_params(
            self.market_info,
            bid_spread=Decimal("0.01"),
            ask_spread=Decimal("0.01"),
            order_amount=Decimal("1"),
            order_levels=5,
            order_level_spread=Decimal("0.01"),
            order_refresh_time=4,
            filled_order_delay=8,
            order_refresh_tolerance_pct=0,
            hanging_orders_enabled=True
        )

    def test_active_orders_are_cancelled_when_mid_price_moves(self):
        strategy = self.one_level_strategy
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        old_bid = strategy.active_buys[0]
        old_ask = strategy.active_sells[0]
        # Not the order refresh time yet, orders should remain the same
        self.clock.backtest_til(self.start_timestamp + 3 * self.clock_tick_size)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        self.assertEqual(old_bid.client_order_id, strategy.active_buys[0].client_order_id)
        self.assertEqual(old_ask.client_order_id, strategy.active_sells[0].client_order_id)
        self.market.order_books[self.trading_pair].apply_diffs([OrderBookRow(99.5, 30, 2)],
                                                               [OrderBookRow(100.1, 30, 2)], 2)
        self.clock.backtest_til(self.start_timestamp + 6 * self.clock_tick_size)
        new_bid = strategy.active_buys[0]
        new_ask = strategy.active_sells[0]
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        self.assertNotEqual(old_ask, new_ask)
        self.assertNotEqual(old_bid, new_bid)

    def test_active_orders_are_kept_when_within_tolerance(self):
        strategy = self.one_level_strategy
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        old_bid = strategy.active_buys[0]
        old_ask = strategy.active_sells[0]
        self.clock.backtest_til(self.start_timestamp + 6 * self.clock_tick_size)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        new_bid = strategy.active_buys[0]
        new_ask = strategy.active_sells[0]
        self.assertEqual(old_ask, new_ask)
        self.assertEqual(old_bid, new_bid)
        self.clock.backtest_til(self.start_timestamp + 10 * self.clock_tick_size)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        new_bid = strategy.active_buys[0]
        new_ask = strategy.active_sells[0]
        self.assertEqual(old_ask, new_ask)
        self.assertEqual(old_bid, new_bid)

    def test_multi_levels_active_orders_are_cancelled_when_mid_price_moves(self):
        strategy = self.multi_levels_strategy
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(5, len(strategy.active_buys))
        self.assertEqual(5, len(strategy.active_sells))
        old_buys = strategy.active_buys
        old_sells = strategy.active_sells
        self.market.order_books[self.trading_pair].apply_diffs([OrderBookRow(99.5, 30, 2)],
                                                               [OrderBookRow(100.1, 30, 2)], 2)
        self.clock.backtest_til(self.start_timestamp + 6 * self.clock_tick_size)
        new_buys = strategy.active_buys
        new_sells = strategy.active_sells
        self.assertEqual(5, len(strategy.active_buys))
        self.assertEqual(5, len(strategy.active_sells))
        self.assertNotEqual([o.client_order_id for o in old_sells], [o.client_order_id for o in new_sells])
        self.assertNotEqual([o.client_order_id for o in old_buys], [o.client_order_id for o in new_buys])

    def test_multiple_active_orders_are_kept_when_within_tolerance(self):
        strategy = self.multi_levels_strategy
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(5, len(strategy.active_buys))
        self.assertEqual(5, len(strategy.active_sells))
        old_buys = strategy.active_buys
        old_sells = strategy.active_sells
        self.clock.backtest_til(self.start_timestamp + 6 * self.clock_tick_size)
        self.assertEqual(5, len(strategy.active_buys))
        self.assertEqual(5, len(strategy.active_sells))
        new_buys = strategy.active_buys
        new_sells = strategy.active_sells
        self.assertEqual([o.client_order_id for o in old_sells], [o.client_order_id for o in new_sells])
        self.assertEqual([o.client_order_id for o in old_buys], [o.client_order_id for o in new_buys])
        self.clock.backtest_til(self.start_timestamp + 10 * self.clock_tick_size)
        self.assertEqual(5, len(strategy.active_buys))
        self.assertEqual(5, len(strategy.active_sells))
        new_buys = strategy.active_buys
        new_sells = strategy.active_sells
        self.assertEqual([o.client_order_id for o in old_sells], [o.client_order_id for o in new_sells])
        self.assertEqual([o.client_order_id for o in old_buys], [o.client_order_id for o in new_buys])

    def test_hanging_orders_multiple_orders_with_refresh_tolerance(self):
        strategy = self.hanging_order_multiple_strategy
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(5, len(strategy.active_buys))
        self.assertEqual(5, len(strategy.active_sells))

        self.simulate_maker_market_trade(True, Decimal("100"), Decimal("101.1"))

        # Before refresh_time hanging orders are not yet created
        self.clock.backtest_til(self.start_timestamp + strategy.order_refresh_time / 2)
        self.assertEqual(1, len(self.maker_order_fill_logger.event_log))
        self.assertEqual(5, len(strategy.active_buys))
        self.assertEqual(4, len(strategy.active_sells))
        self.assertEqual(0, len(strategy.hanging_order_ids))

        # At order_refresh_time (4 seconds), hanging order are created
        # Ask is filled and due to delay is not replenished immediately
        # Bid orders are now hanging and active
        self.clock.backtest_til(self.start_timestamp + strategy.order_refresh_time + 1)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))
        self.assertEqual(1, len(strategy.hanging_order_ids))

        # At filled_order_delay (8 seconds), new sets of bid and ask orders are created
        self.clock.backtest_til(self.start_timestamp + strategy.order_refresh_time + strategy.filled_order_delay + 1)
        self.assertEqual(6, len(strategy.active_buys))
        self.assertEqual(5, len(strategy.active_sells))
        self.assertEqual(1, len(strategy.hanging_order_ids))

        # Check all hanging order ids are indeed in active bids list
        self.assertTrue(all(h in [order.client_order_id for order in strategy.active_buys]
                            for h in strategy.hanging_order_ids))

        old_buys = [o for o in strategy.active_buys if o.client_order_id not in strategy.hanging_order_ids]
        old_sells = [o for o in strategy.active_sells if o.client_order_id not in strategy.hanging_order_ids]

        self.clock.backtest_til(self.start_timestamp + strategy.order_refresh_time + strategy.filled_order_delay + 1)
        self.assertEqual(6, len(strategy.active_buys))
        self.assertEqual(5, len(strategy.active_sells))

        new_buys = [o for o in strategy.active_buys if o.client_order_id not in strategy.hanging_order_ids]
        new_sells = [o for o in strategy.active_sells if o.client_order_id not in strategy.hanging_order_ids]
        self.assertEqual([o.client_order_id for o in old_sells], [o.client_order_id for o in new_sells])
        self.assertEqual([o.client_order_id for o in old_buys], [o.client_order_id for o in new_buys])
