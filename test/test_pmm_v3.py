#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

from typing import List
from decimal import Decimal
import logging; logging.basicConfig(level=logging.ERROR)
import pandas as pd
import unittest

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
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
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_row import OrderBookRow


# Update the orderbook so that the top bids and asks are lower than actual for a wider bid ask spread
# this basially removes the orderbook entries above top bid and below top ask
def simulate_order_book_widening(order_book: OrderBook, top_bid: float, top_ask: float):
    bid_diffs: List[OrderBookRow] = []
    ask_diffs: List[OrderBookRow] = []
    update_id: int = order_book.last_diff_uid + 1
    for row in order_book.bid_entries():
        if row.price > top_bid:
            bid_diffs.append(OrderBookRow(row.price, 0, update_id))
        else:
            break
    for row in order_book.ask_entries():
        if row.price < top_ask:
            ask_diffs.append(OrderBookRow(row.price, 0, update_id))
        else:
            break
    order_book.apply_diffs(bid_diffs, ask_diffs, update_id)


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
        self.order_fill_logger: EventLogger = EventLogger()
        self.cancel_order_logger: EventLogger = EventLogger()
        self.market.add_listener(MarketEvent.OrderFilled, self.order_fill_logger)
        self.market.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)

        self.one_level_strategy = PureMarketMakingStrategyV3(
            self.market_info,
            bid_spread=Decimal("0.01"),
            ask_spread=Decimal("0.01"),
            order_amount=Decimal("1"),
            order_refresh_time=5.0,
            filled_order_delay=5.0,
            order_refresh_tolerance_pct=-1
        )

        self.multi_levels_strategy = PureMarketMakingStrategyV3(
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
        strategy = self.one_level_strategy
        self.clock.add_iterator(strategy)

        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        buy_1 = strategy.active_buys[0]
        self.assertEqual(99, buy_1.price)
        self.assertEqual(1, buy_1.quantity)
        sell_1 = strategy.active_sells[0]
        self.assertEqual(101, sell_1.price)
        self.assertEqual(1, sell_1.quantity)

        # After order_refresh_time, a new set of orders is created
        self.clock.backtest_til(self.start_timestamp + 7)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        self.assertNotEqual(buy_1.client_order_id, strategy.active_buys[0].client_order_id)
        self.assertNotEqual(sell_1.client_order_id, strategy.active_sells[0].client_order_id)

        # Simulate buy order filled
        self.clock.backtest_til(self.start_timestamp + 8)
        self.simulate_maker_market_trade(False, 100, 98.9)
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))

        # After filled_ore
        self.clock.backtest_til(self.start_timestamp + 14)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))

    def test_basic_multiple_levels(self):
        strategy = self.multi_levels_strategy
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)

        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))
        buys = strategy.active_buys
        sells = strategy.active_sells
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
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))
        self.assertNotEqual(buys[0].client_order_id, strategy.active_buys[0].client_order_id)
        self.assertNotEqual(sells[0].client_order_id, strategy.active_sells[0].client_order_id)

        # Simulate buy order filled
        self.clock.backtest_til(self.start_timestamp + 8)
        self.simulate_maker_market_trade(False, 100, 97.9)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

        # After filled_ore
        self.clock.backtest_til(self.start_timestamp + 14)
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

    def test_apply_budget_constraint_to_proposal(self):
        strategy = self.multi_levels_strategy
        self.clock.add_iterator(strategy)
        self.market.set_balance("HBOT", Decimal("50"))
        self.market.set_balance("ETH", Decimal("0"))
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

        for order in strategy.active_sells:
            strategy.cancel_order(order.client_order_id)

        self.market.set_balance("HBOT", 0)
        self.market.set_balance("ETH", Decimal("5000"))
        self.clock.backtest_til(self.start_timestamp + 7)
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))

        for order in strategy.active_buys:
            strategy.cancel_order(order.client_order_id)

        self.market.set_balance("HBOT", Decimal("1.5"))
        self.market.set_balance("ETH", Decimal("160"))
        self.clock.backtest_til(self.start_timestamp + 20)
        self.assertEqual(2, len(strategy.active_buys))
        self.assertEqual(2, len(strategy.active_sells))
        self.assertEqual(Decimal("98"), strategy.active_buys[-1].price)
        self.assertEqual(Decimal("0.622448"), strategy.active_buys[-1].quantity)
        self.assertEqual(Decimal("102"), strategy.active_sells[-1].price)
        self.assertEqual(Decimal("0.5"), strategy.active_sells[-1].quantity)

    def test_market_become_wider(self):
        strategy = self.one_level_strategy
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertEqual(Decimal("99"), strategy.active_buys[0].price)
        self.assertEqual(Decimal("101"), strategy.active_sells[0].price)
        self.assertEqual(Decimal("1.0"), strategy.active_buys[0].quantity)
        self.assertEqual(Decimal("1.0"), strategy.active_sells[0].quantity)

        simulate_order_book_widening(self.book_data.order_book, 90, 110)

        self.clock.backtest_til(self.start_timestamp + 7)
        self.assertEqual(2, len(self.cancel_order_logger.event_log))
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))

        self.assertEqual(Decimal("99"), strategy.active_buys[0].price)
        self.assertEqual(Decimal("101"), strategy.active_sells[0].price)
        self.assertEqual(Decimal("1.0"), strategy.active_buys[0].quantity)
        self.assertEqual(Decimal("1.0"), strategy.active_sells[0].quantity)

    def test_market_became_narrower(self):
        strategy = self.one_level_strategy
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertEqual(Decimal("99"), strategy.active_buys[0].price)
        self.assertEqual(Decimal("101"), strategy.active_sells[0].price)
        self.assertEqual(Decimal("1.0"), strategy.active_buys[0].quantity)
        self.assertEqual(Decimal("1.0"), strategy.active_sells[0].quantity)

        self.book_data.order_book.apply_diffs([OrderBookRow(99.5, 30, 2)], [OrderBookRow(100.5, 30, 2)], 2)

        self.clock.backtest_til(self.start_timestamp + 7)
        self.assertEqual(2, len(self.cancel_order_logger.event_log))
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))

        self.assertEqual(Decimal("99"), strategy.active_buys[0].price)
        self.assertEqual(Decimal("101"), strategy.active_sells[0].price)
        self.assertEqual(Decimal("1.0"), strategy.active_buys[0].quantity)
        self.assertEqual(Decimal("1.0"), strategy.active_sells[0].quantity)

    def test_price_band_price_ceiling_breach(self):
        strategy = self.multi_levels_strategy
        strategy.price_ceiling = Decimal("105")

        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

        simulate_order_book_widening(self.book_data.order_book, self.mid_price, 115, )

        self.clock.backtest_til(self.start_timestamp + 7)
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

    def test_price_band_price_floor_breach(self):
        strategy = self.multi_levels_strategy
        strategy.price_floor = Decimal("95")

        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

        simulate_order_book_widening(self.book_data.order_book, 85, self.mid_price)

        self.clock.backtest_til(self.start_timestamp + 7)
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))

    def test_add_transaction_costs(self):
        strategy = self.multi_levels_strategy
        strategy.add_transaction_costs_to_orders = True
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))
        # Todo: currently hummingsim market doesn't store fee in a percentage value, so we cannot test further on this.

    def test_filled_order_delay(self):
        strategy = self.one_level_strategy
        strategy.filled_order_delay = 10.0
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))

        self.simulate_maker_market_trade(True, 100, Decimal("101.1"))
        # Ask is filled and due to delay is not replenished immediately
        self.clock.backtest_til(self.start_timestamp + 2)
        self.assertEqual(1, len(self.order_fill_logger.event_log))
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))

        # After order_refresh_time, buy order gets canceled
        self.clock.backtest_til(self.start_timestamp + 7)
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))

        # Orders are placed after replenish delay
        self.clock.backtest_til(self.start_timestamp + 12)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))

        # Prices are not adjusted according to filled price as per settings
        self.assertEqual(Decimal("99"), strategy.active_buys[0].price)
        self.assertEqual(Decimal("101"), strategy.active_sells[0].price)
        self.assertEqual(Decimal("1.0"), strategy.active_buys[0].quantity)
        self.assertEqual(Decimal("1.0"), strategy.active_sells[0].quantity)
        self.order_fill_logger.clear()

    def test_filled_order_delay_mulitiple_orders(self):
        strategy = self.multi_levels_strategy
        strategy.filled_order_delay = 10.0
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

        self.simulate_maker_market_trade(True, 100, Decimal("101.1"))

        # Ask is filled and due to delay is not replenished immediately
        self.clock.backtest_til(self.start_timestamp + 2)
        self.assertEqual(1, len(self.order_fill_logger.event_log))
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(2, len(strategy.active_sells))

        # After order_refresh_time, buy order gets canceled
        self.clock.backtest_til(self.start_timestamp + 7)
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))

        # Orders are placed after replenish delay
        self.clock.backtest_til(self.start_timestamp + 12)
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

        self.order_fill_logger.clear()

    def test_order_optimization(self):
        # Widening the order book, top bid is now 97.5 and top ask 102.5
        simulate_order_book_widening(self.book_data.order_book, 98, 102)
        strategy = self.one_level_strategy
        strategy.order_optimization_enabled = True
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        self.assertEqual(Decimal("97.5001"), strategy.active_buys[0].price)
        self.assertEqual(Decimal("102.499"), strategy.active_sells[0].price)

    def test_hanging_orders(self):
        strategy = self.one_level_strategy
        strategy.order_refresh_time = 4.0
        strategy.filled_order_delay = 8.0
        strategy.hanging_orders_enabled = True
        strategy.hanging_orders_cancel_pct = Decimal("0.05")
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))

        self.simulate_maker_market_trade(False, 100, 98.9)

        # Bid is filled and due to delay is not replenished immediately
        # Ask order is now hanging but is active
        self.clock.backtest_til(self.start_timestamp + 2)
        self.assertEqual(1, len(self.order_fill_logger.event_log))
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        self.assertEqual(1, len(strategy.hanging_order_ids))
        hanging_order_id = strategy.hanging_order_ids[0]

        # At order_refresh_time, hanging order remains.
        self.clock.backtest_til(self.start_timestamp + 5)
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))

        # At filled_order_delay, a new set of bid and ask orders (one each) is created
        self.clock.backtest_til(self.start_timestamp + 10)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(2, len(strategy.active_sells))

        self.assertIn(hanging_order_id, [order.client_order_id for order in strategy.active_sells])

        simulate_order_book_widening(self.book_data.order_book, 80, 100)
        # As book bids moving lower, the ask hanging order price spread is now more than the hanging_orders_cancel_pct
        # Hanging order is canceled and removed from the active list
        self.clock.backtest_til(self.start_timestamp + 11 * self.clock_tick_size)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        self.assertNotIn(strategy.active_sells[0].client_order_id, strategy.hanging_order_ids)

        self.order_fill_logger.clear()

    def test_hanging_orders_multiple_orders(self):
        strategy = self.multi_levels_strategy
        strategy.order_refresh_time = 4.0
        strategy.filled_order_delay = 8.0
        strategy.hanging_orders_enabled = True
        strategy.hanging_orders_cancel_pct = Decimal("0.05")
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

        self.simulate_maker_market_trade(False, 100, 98.9)

        # Bid is filled and due to delay is not replenished immediately
        # Ask order is now hanging but is active
        self.clock.backtest_til(self.start_timestamp + 2)
        self.assertEqual(1, len(self.order_fill_logger.event_log))
        self.assertEqual(2, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))
        self.assertEqual(3, len(strategy.hanging_order_ids))

        # At order_refresh_time, hanging order remains.
        self.clock.backtest_til(self.start_timestamp + 5)
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

        # At filled_order_delay, a new set of bid and ask orders (one each) is created
        self.clock.backtest_til(self.start_timestamp + 10)
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(6, len(strategy.active_sells))

        self.assertTrue(all(id in (order.client_order_id for order in strategy.active_sells)
                            for id in strategy.hanging_order_ids))

        simulate_order_book_widening(self.book_data.order_book, 80, 100)
        # As book bids moving lower, the ask hanging order price spread is now more than the hanging_orders_cancel_pct
        # Hanging order is canceled and removed from the active list
        self.clock.backtest_til(self.start_timestamp + 11 * self.clock_tick_size)
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))
        self.assertFalse(any(o.client_order_id in strategy.hanging_order_ids for o in strategy.active_sells))

        self.order_fill_logger.clear()

    def test_inventory_skew(self):
        strategy = self.one_level_strategy
        strategy.inventory_skew_enabled = True
        strategy.inventory_target_base_pct = Decimal("0.9")
        strategy.inventory_range_multiplier = Decimal("5.0")
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        first_bid_order = strategy.active_buys[0]
        first_ask_order = strategy.active_sells[0]
        self.assertEqual(Decimal("99"), first_bid_order.price)
        self.assertEqual(Decimal("101"), first_ask_order.price)
        self.assertEqual(Decimal("0.5"), first_bid_order.quantity)
        self.assertEqual(Decimal("1.5"), first_ask_order.quantity)

        self.simulate_maker_market_trade(True, 5.0, 101.1)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))

        self.clock.backtest_til(self.start_timestamp + 2)
        self.assertEqual(1, len(self.order_fill_logger.event_log))

        maker_fill = self.order_fill_logger.event_log[0]
        self.assertEqual(TradeType.SELL, maker_fill.trade_type)
        self.assertAlmostEqual(101, maker_fill.price)
        self.assertAlmostEqual(Decimal("1.5"), Decimal(str(maker_fill.amount)), places=4)

        self.clock.backtest_til(self.start_timestamp + 7)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        first_bid_order = strategy.active_buys[0]
        first_ask_order = strategy.active_sells[0]
        self.assertEqual(Decimal("99"), first_bid_order.price)
        self.assertEqual(Decimal("101"), first_ask_order.price)
        self.assertEqual(Decimal("0.651349"), first_bid_order.quantity)
        self.assertEqual(Decimal("1.34865"), first_ask_order.quantity)

    def test_inventory_skew_multiple_orders(self):
        strategy = self.multi_levels_strategy
        strategy.order_levels = 5
        strategy.order_level_amount = Decimal("0.5")
        strategy.inventory_skew_enabled = True
        strategy.inventory_target_base_pct = Decimal("0.9")
        strategy.inventory_range_multiplier = Decimal("0.5")
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertEqual(5, len(strategy.active_buys))
        self.assertEqual(5, len(strategy.active_sells))

        first_bid_order = strategy.active_buys[0]
        first_ask_order = strategy.active_sells[0]
        self.assertEqual(Decimal("99"), first_bid_order.price)
        self.assertEqual(Decimal("101"), first_ask_order.price)
        self.assertEqual(Decimal("0.5"), first_bid_order.quantity)
        self.assertEqual(Decimal("1.5"), first_ask_order.quantity)

        last_bid_order = strategy.active_buys[-1]
        last_ask_order = strategy.active_sells[-1]
        last_bid_price = Decimal(99 * (1 - 0.01) ** 4).quantize(Decimal("0.001"))
        last_ask_price = Decimal(101 * (1 + 0.01) ** 4).quantize(Decimal("0.001"))
        self.assertAlmostEqual(last_bid_price, last_bid_order.price, 3)
        self.assertAlmostEqual(last_ask_price, last_ask_order.price, 3)
        self.assertEqual(Decimal("1.5"), last_bid_order.quantity)
        self.assertEqual(Decimal("4.5"), last_ask_order.quantity)

        self.simulate_maker_market_trade(True, 5.0, 101.1)
        self.assertEqual(5, len(strategy.active_buys))
        self.assertEqual(4, len(strategy.active_sells))

        self.clock.backtest_til(self.start_timestamp + 3)
        self.assertEqual(1, len(self.order_fill_logger.event_log))

        maker_fill = self.order_fill_logger.event_log[0]
        self.assertEqual(TradeType.SELL, maker_fill.trade_type)
        self.assertAlmostEqual(101, maker_fill.price)
        self.assertAlmostEqual(Decimal("1.5"), Decimal(str(maker_fill.amount)), places=4)

        # The default filled_order_delay is 60, so gotta wait 60 + 2 here.
        self.clock.backtest_til(self.start_timestamp + 7 * self.clock_tick_size + 1)
        self.assertEqual(5, len(strategy.active_buys))
        self.assertEqual(5, len(strategy.active_sells))
        first_bid_order = strategy.active_buys[0]
        first_ask_order = strategy.active_sells[0]
        last_bid_order = strategy.active_buys[-1]
        last_ask_order = strategy.active_sells[-1]
        self.assertEqual(Decimal("99"), first_bid_order.price)
        self.assertEqual(Decimal("101"), first_ask_order.price)
        self.assertEqual(Decimal("0.651349"), first_bid_order.quantity)
        self.assertEqual(Decimal("1.34865"), first_ask_order.quantity)
        last_bid_price = Decimal(99 * (1 - 0.01) ** 4).quantize(Decimal("0.001"))
        last_ask_price = Decimal(101 * (1 + 0.01) ** 4).quantize(Decimal("0.001"))
        self.assertAlmostEqual(last_bid_price, last_bid_order.price, 3)
        self.assertAlmostEqual(last_ask_price, last_ask_order.price, 3)
        self.assertEqual(Decimal("1.95404"), last_bid_order.quantity)
        self.assertEqual(Decimal("4.04595"), last_ask_order.quantity)
