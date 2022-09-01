import asyncio
import time
import unittest
from decimal import Decimal
from typing import List, Union

import pandas as pd

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.test_support.mock_paper_exchange import MockPaperExchange
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.market_order import MarketOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.order_tracker import OrderTracker
from hummingbot.strategy.pure_market_making_app.pure_market_making_order_tracker_app import (
    PureMarketMakingOrderTrackerAugmentedPurePython,
)


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


class PMMOTAPPUnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    clock_tick_size = 10

    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.get_event_loop()
        cls.trading_pair = "COINALPHA-HBOT"

        cls.limit_orders: List[LimitOrder] = [
            LimitOrder(client_order_id=f"LIMIT//-{i}-{int(time.time() * 1e6)}",
                       trading_pair=cls.trading_pair,
                       is_buy=True if i % 2 == 0 else False,
                       base_currency=cls.trading_pair.split("-")[0],
                       quote_currency=cls.trading_pair.split("-")[1],
                       price=Decimal(f"{100 - i}") if i % 2 == 0 else Decimal(f"{100 + i}"),
                       quantity=Decimal(f"{10 * (i + 1)}"),
                       creation_timestamp=int(time.time() * 1e6)
                       )
            for i in range(20)
        ]
        cls.market_orders: List[MarketOrder] = [
            MarketOrder(order_id=f"MARKET//-{i}-{int(time.time() * 1e3)}",
                        trading_pair=cls.trading_pair,
                        is_buy=True if i % 2 == 0 else False,
                        base_asset=cls.trading_pair.split("-")[0],
                        quote_asset=cls.trading_pair.split("-")[1],
                        amount=float(f"{10 * (i + 1)}"),
                        timestamp=time.time()
                        )
            for i in range(20)
        ]

        cls.market: MockPaperExchange = MockPaperExchange(
            client_config_map=ClientConfigAdapter(ClientConfigMap())
        )
        cls.market_info: MarketTradingPairTuple = MarketTradingPairTuple(
            cls.market, cls.trading_pair, *cls.trading_pair.split("-")
        )

    def setUp(self):
        self.pmm_ot = PureMarketMakingOrderTrackerAugmentedPurePython()
        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)
        self.clock.add_iterator(self.pmm_ot)
        self.clock.backtest_til(self.start_timestamp)

    @staticmethod
    def simulate_place_order(order_tracker: PureMarketMakingOrderTrackerAugmentedPurePython, order: Union[LimitOrder, MarketOrder],
                             market_info: MarketTradingPairTuple):
        """
        Simulates an order being succesfully placed.
        """
        if isinstance(order, LimitOrder):
            order_tracker.add_create_order_pending(order.client_order_id)
            order_tracker.start_tracking_limit_order(market_pair=market_info,
                                                     order_id=order.client_order_id,
                                                     is_buy=order.is_buy,
                                                     price=order.price,
                                                     quantity=order.quantity
                                                     )
        else:
            order_tracker.add_create_order_pending(order.order_id)
            order_tracker.start_tracking_market_order(market_pair=market_info,
                                                      order_id=order.order_id,
                                                      is_buy=order.is_buy,
                                                      quantity=order.amount
                                                      )

    @staticmethod
    def simulate_order_created(order_tracker: PureMarketMakingOrderTrackerAugmentedPurePython, order: Union[LimitOrder, MarketOrder]):
        order_id = order.client_order_id if isinstance(order, LimitOrder) else order.order_id
        order_tracker.remove_create_order_pending(order_id)

    @staticmethod
    def simulate_stop_tracking_order(order_tracker: PureMarketMakingOrderTrackerAugmentedPurePython, order: Union[LimitOrder, MarketOrder],
                                     market_info: MarketTradingPairTuple):
        """
        Simulates an order being cancelled or filled completely.
        """
        if isinstance(order, LimitOrder):
            order_tracker.stop_tracking_limit_order(market_pair=market_info,
                                                    order_id=order.client_order_id,
                                                    )
        else:
            order_tracker.stop_tracking_market_order(market_pair=market_info,
                                                     order_id=order.order_id
                                                     )

    @staticmethod
    def simulate_cancel_order(order_tracker: PureMarketMakingOrderTrackerAugmentedPurePython, order: Union[LimitOrder, MarketOrder]):
        """
        Simulates order being cancelled.
        """
        order_id = order.client_order_id if isinstance(order, LimitOrder) else order.order_id
        if order_id:
            order_tracker.check_and_track_cancel(order_id)

    def test_initialization(self):
        self.assertTrue(isinstance(self.pmm_ot, OrderTracker))
        self.assertTrue(hasattr(self.pmm_ot, 'SHADOW_MAKER_ORDER_KEEP_ALIVE_DURATION'))
        self.assertEqual(60.0 * 3, self.pmm_ot.SHADOW_MAKER_ORDER_KEEP_ALIVE_DURATION)

    def test_active_limit_orders(self):
        # Check initial output
        self.assertTrue(len(self.pmm_ot.active_limit_orders) == 0)

        # Simulate orders being placed and tracked
        for order in self.limit_orders:
            self.simulate_place_order(self.pmm_ot, order, self.market_info)
            self.simulate_order_created(self.pmm_ot, order)

        self.assertTrue(len(self.pmm_ot.active_limit_orders) == len(self.limit_orders))

        # Simulates order cancellation request being sent to exchange
        order_to_cancel = self.limit_orders[0]
        self.simulate_cancel_order(self.pmm_ot, order_to_cancel)

        # Unlike OrderTracker, the in_flight_cancels are not filtered out, but are in fact in the set
        self.assertEqual(len(self.limit_orders), len(self.pmm_ot.active_limit_orders))
        self.assertEqual(1, len(self.pmm_ot.in_flight_cancels))

    def test_shadow_limit_orders(self):
        # Check initial output
        self.assertTrue(len(self.pmm_ot.shadow_limit_orders) == 0)

        # Simulate orders being placed and tracked
        for order in self.limit_orders:
            self.simulate_place_order(self.pmm_ot, order, self.market_info)
            self.simulate_order_created(self.pmm_ot, order)

        self.assertTrue(len(self.pmm_ot.shadow_limit_orders) == len(self.limit_orders))

        # Simulates order cancellation request being sent to exchange
        order_to_cancel = self.limit_orders[0]
        self.simulate_cancel_order(self.pmm_ot, order_to_cancel)

        # Unlike OrderTracker, the in_flight_cancels are not filtered out, but are in fact in the set
        self.assertEqual(len(self.limit_orders), len(self.pmm_ot.shadow_limit_orders))
        self.assertEqual(1, len(self.pmm_ot.in_flight_cancels))

    def test_market_pair_to_active_orders(self):
        # Check initial output
        self.assertTrue(len(self.pmm_ot.market_pair_to_active_orders) == 0)

        # Simulate orders being placed and tracked
        for order in self.limit_orders:
            self.simulate_place_order(self.pmm_ot, order, self.market_info)
            self.simulate_order_created(self.pmm_ot, order)

        self.assertTrue(
            len(self.pmm_ot.market_pair_to_active_orders[self.market_info]) == len(self.limit_orders))
