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
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.order_tracker import OrderTracker


class OrderTrackerUnitTests(unittest.TestCase):
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
            LimitOrder(client_order_id=f"LIMIT//-{i}-{int(time.time()*1e6)}",
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
            MarketOrder(order_id=f"MARKET//-{i}-{int(time.time()*1e3)}",
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
        self.order_tracker: OrderTracker = OrderTracker()
        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)
        self.clock.add_iterator(self.order_tracker)
        self.clock.backtest_til(self.start_timestamp)

    @staticmethod
    def simulate_place_order(order_tracker: OrderTracker, order: Union[LimitOrder, MarketOrder], market_info: MarketTradingPairTuple):
        """
        Simulates an order being successfully placed.
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
    def simulate_order_created(order_tracker: OrderTracker, order: Union[LimitOrder, MarketOrder]):
        order_id = order.client_order_id if isinstance(order, LimitOrder) else order.order_id
        order_tracker.remove_create_order_pending(order_id)

    @staticmethod
    def simulate_stop_tracking_order(order_tracker: OrderTracker, order: Union[LimitOrder, MarketOrder], market_info: MarketTradingPairTuple):
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
    def simulate_cancel_order(order_tracker: OrderTracker, order: Union[LimitOrder, MarketOrder]):
        """
        Simulates order being cancelled.
        """
        order_id = order.client_order_id if isinstance(order, LimitOrder) else order.order_id
        if order_id:
            order_tracker.check_and_track_cancel(order_id)

    def test_active_limit_orders(self):
        # Check initial output
        self.assertTrue(len(self.order_tracker.active_limit_orders) == 0)

        # Simulate orders being placed and tracked
        for order in self.limit_orders:
            self.simulate_place_order(self.order_tracker, order, self.market_info)
            self.simulate_order_created(self.order_tracker, order)

        self.assertTrue(len(self.order_tracker.active_limit_orders) == len(self.limit_orders))

        # Simulates order cancellation request being sent to exchange
        order_to_cancel = self.limit_orders[0]
        self.simulate_cancel_order(self.order_tracker, order_to_cancel)

        self.assertTrue(len(self.order_tracker.active_limit_orders) == len(self.limit_orders) - 1)

    def test_shadow_limit_orders(self):
        # Check initial output
        self.assertTrue(len(self.order_tracker.shadow_limit_orders) == 0)

        # Simulate orders being placed and tracked
        for order in self.limit_orders:
            self.simulate_place_order(self.order_tracker, order, self.market_info)
            self.simulate_order_created(self.order_tracker, order)

        self.assertTrue(len(self.order_tracker.shadow_limit_orders) == len(self.limit_orders))

        # Simulates order cancellation request being sent to exchange
        order_to_cancel = self.limit_orders[0]
        self.simulate_cancel_order(self.order_tracker, order_to_cancel)

        self.assertTrue(len(self.order_tracker.shadow_limit_orders) == len(self.limit_orders) - 1)

    def test_market_pair_to_active_orders(self):
        # Check initial output
        self.assertTrue(len(self.order_tracker.market_pair_to_active_orders) == 0)

        # Simulate orders being placed and tracked
        for order in self.limit_orders:
            self.simulate_place_order(self.order_tracker, order, self.market_info)
            self.simulate_order_created(self.order_tracker, order)

        self.assertTrue(len(self.order_tracker.market_pair_to_active_orders[self.market_info]) == len(self.limit_orders))

    def test_active_bids(self):
        # Check initial output
        self.assertTrue(len(self.order_tracker.active_bids) == 0)

        # Simulate orders being placed and tracked
        for order in self.limit_orders:
            self.simulate_place_order(self.order_tracker, order, self.market_info)
            self.simulate_order_created(self.order_tracker, order)

        self.assertTrue(len(self.order_tracker.active_bids) == len(self.limit_orders) / 2)

    def test_active_asks(self):
        # Check initial output
        self.assertTrue(len(self.order_tracker.active_asks) == 0)

        # Simulate orders being placed and tracked
        for order in self.limit_orders:
            self.simulate_place_order(self.order_tracker, order, self.market_info)
            self.simulate_order_created(self.order_tracker, order)

        self.assertTrue(len(self.order_tracker.active_asks) == len(self.limit_orders) / 2)

    def test_tracked_limit_orders(self):
        # Check initial output
        self.assertTrue(len(self.order_tracker.tracked_limit_orders) == 0)

        # Simulate orders being placed and tracked
        for order in self.limit_orders:
            self.simulate_place_order(self.order_tracker, order, self.market_info)
            self.simulate_order_created(self.order_tracker, order)

        self.assertTrue(len(self.order_tracker.tracked_limit_orders) == len(self.limit_orders))

        # Simulates order cancellation request being sent to exchange
        order_to_cancel = self.limit_orders[0]
        self.simulate_cancel_order(self.order_tracker, order_to_cancel)

        # Note: This includes all orders(open, cancelled, filled, partially filled).
        # Hence it should not differ from initial list of orders
        self.assertTrue(len(self.order_tracker.tracked_limit_orders) == len(self.limit_orders))

    def test_tracked_limit_orders_data_frame(self):
        # Check initial output
        self.assertTrue(len(self.order_tracker.tracked_limit_orders_data_frame) == 0)

        # Simulate orders being placed and tracked
        for order in self.limit_orders:
            self.simulate_place_order(self.order_tracker, order, self.market_info)
            self.simulate_order_created(self.order_tracker, order)

        self.assertTrue(len(self.order_tracker.tracked_limit_orders_data_frame) == len(self.limit_orders))

        # Simulates order cancellation request being sent to exchange
        order_to_cancel = self.limit_orders[0]
        self.simulate_cancel_order(self.order_tracker, order_to_cancel)

        # Note: This includes all orders(open, cancelled, filled, partially filled).
        # Hence it should not differ from initial list of orders
        self.assertTrue(len(self.order_tracker.tracked_limit_orders_data_frame) == len(self.limit_orders))

    def test_tracked_market_orders(self):
        # Check initial output
        self.assertTrue(len(self.order_tracker.tracked_market_orders) == 0)

        # Simulate orders being placed and tracked
        for order in self.market_orders:
            self.simulate_place_order(self.order_tracker, order, self.market_info)
            self.simulate_order_created(self.order_tracker, order)

        self.assertTrue(len(self.order_tracker.tracked_market_orders) == len(self.market_orders))

        # Simulates order cancellation request being sent to exchange
        order_to_cancel = self.market_orders[0]
        self.simulate_cancel_order(self.order_tracker, order_to_cancel)

        # Note: This includes all orders(open, cancelled, filled, partially filled).
        # Hence it should not differ from initial list of orders
        self.assertTrue(len(self.order_tracker.tracked_market_orders) == len(self.market_orders))

    def test_tracked_market_order_data_frame(self):
        # Check initial output
        self.assertTrue(len(self.order_tracker.tracked_market_orders_data_frame) == 0)

        # Simulate orders being placed and tracked
        for order in self.market_orders:
            self.simulate_place_order(self.order_tracker, order, self.market_info)
            self.simulate_order_created(self.order_tracker, order)

        self.assertTrue(len(self.order_tracker.tracked_market_orders_data_frame) == len(self.market_orders))

        # Simulates order cancellation request being sent to exchange
        order_to_cancel = self.market_orders[0]
        self.simulate_cancel_order(self.order_tracker, order_to_cancel)

        # Note: This includes all orders(open, cancelled, filled, partially filled).
        # Hence it should not differ from initial list of orders
        self.assertTrue(len(self.order_tracker.tracked_market_orders_data_frame) == len(self.market_orders))

    def test_in_flight_cancels(self):
        # Check initial output
        self.assertTrue(len(self.order_tracker.in_flight_cancels) == 0)

        # Simulate orders being placed and tracked
        for order in self.limit_orders:
            self.simulate_place_order(self.order_tracker, order, self.market_info)
            self.simulate_order_created(self.order_tracker, order)

        # Simulates order cancellation request being sent to exchange
        order_to_cancel = self.limit_orders[0]
        self.simulate_cancel_order(self.order_tracker, order_to_cancel)

        self.assertTrue(len(self.order_tracker.in_flight_cancels) == 1)

    def test_in_flight_pending_created(self):
        # Check initial output
        self.assertTrue(len(self.order_tracker.in_flight_pending_created) == 0)

        # Simulate orders being placed and tracked
        for order in self.limit_orders:
            self.simulate_place_order(self.order_tracker, order, self.market_info)

        self.assertTrue(len(self.order_tracker.in_flight_pending_created) == len(self.limit_orders))

        for order in self.limit_orders:
            self.simulate_order_created(self.order_tracker, order)

        self.assertTrue(len(self.order_tracker.in_flight_pending_created) == 0)

    def test_get_limit_orders(self):
        # Check initial output
        self.assertTrue(len(list(self.order_tracker.get_limit_orders().values())) == 0)

        # Simulate orders being placed and tracked
        for order in self.limit_orders:
            self.simulate_place_order(self.order_tracker, order, self.market_info)

        self.assertTrue(len(self.order_tracker.get_limit_orders()[self.market_info].keys()) == len(self.limit_orders))

    def test_get_market_orders(self):
        # Check initial output
        self.assertTrue(len(list(self.order_tracker.get_market_orders().values())) == 0)

        # Simulate orders being placed and tracked
        for order in self.market_orders:
            self.simulate_place_order(self.order_tracker, order, self.market_info)

        self.assertTrue(len(self.order_tracker.get_market_orders()[self.market_info].keys()) == len(self.market_orders))

    def test_get_shadow_limit_orders(self):
        # Check initial output
        self.assertTrue(self.market_info not in self.order_tracker.get_shadow_limit_orders())

        # Simulates order being placed and tracked
        order: LimitOrder = self.limit_orders[0]
        self.simulate_place_order(self.order_tracker, order, self.market_info)

        # Compare order details and output
        other_order = self.order_tracker.get_shadow_limit_orders()[self.market_info][order.client_order_id]
        self.assertEqual(order.trading_pair, other_order.trading_pair)
        self.assertEqual(order.price, other_order.price)
        self.assertEqual(order.quantity, other_order.quantity)
        self.assertEqual(order.is_buy, other_order.is_buy)

        # Simulate order being cancelled
        self.simulate_cancel_order(self.order_tracker, order)
        self.simulate_stop_tracking_order(self.order_tracker, order, self.market_info)

        # Check that order is not yet removed from shadow_limit_orders
        other_order = self.order_tracker.get_shadow_limit_orders()[self.market_info][order.client_order_id]
        self.assertEqual(order.trading_pair, other_order.trading_pair)
        self.assertEqual(order.price, other_order.price)
        self.assertEqual(order.quantity, other_order.quantity)
        self.assertEqual(order.is_buy, other_order.is_buy)

        # Simulates current_timestamp > SHADOW_MAKER_ORDER_KEEP_ALIVE_DURATION
        self.clock.backtest_til(self.start_timestamp + OrderTracker.SHADOW_MAKER_ORDER_KEEP_ALIVE_DURATION + 1)
        self.order_tracker.check_and_cleanup_shadow_records()

        # Check that check_and_cleanup_shadow_records clears shadow_limit_orders
        self.assertTrue(self.market_info not in self.order_tracker.get_shadow_limit_orders())

    def test_has_in_flight_cancel(self):
        # Check initial output
        self.assertFalse(self.order_tracker.has_in_flight_cancel("ORDER_ID_DO_NOT_EXIST"))

        # Simulates order being placed and tracked
        order: LimitOrder = self.limit_orders[0]
        self.simulate_place_order(self.order_tracker, order, self.market_info)
        self.simulate_order_created(self.order_tracker, order)

        # Order not yet cancelled.
        self.assertFalse(self.order_tracker.has_in_flight_cancel(order.client_order_id))

        # Simulate order being cancelled
        self.simulate_cancel_order(self.order_tracker, order)

        # Order inflight cancel timestamp has not yet expired
        self.assertTrue(self.order_tracker.has_in_flight_cancel(order.client_order_id))

        # Simulate in-flight cancel has expired
        self.clock.backtest_til(self.start_timestamp + OrderTracker.CANCEL_EXPIRY_DURATION + 1)

        self.assertFalse(self.order_tracker.has_in_flight_cancel(order.client_order_id))

        # Simulates order being placed and tracked
        order: LimitOrder = self.limit_orders[0]
        self.simulate_place_order(self.order_tracker, order, self.market_info)
        self.simulate_order_created(self.order_tracker, order)

        # Simulate order being cancelled and no longer tracked
        self.simulate_cancel_order(self.order_tracker, order)
        self.simulate_stop_tracking_order(self.order_tracker, order, self.market_info)

        # Check that once the order is no longer tracker, it will no longer have a pending cancel
        self.assertFalse(self.order_tracker.has_in_flight_cancel(order.client_order_id))

    def test_get_market_pair_from_order_id(self):
        # Initial validation
        order: LimitOrder = self.limit_orders[0]

        self.assertNotEqual(self.market_info, self.order_tracker.get_market_pair_from_order_id(order.client_order_id))

        # Simulate order being placed and tracked
        self.simulate_place_order(self.order_tracker, order, self.market_info)

        self.assertEqual(self.market_info, self.order_tracker.get_market_pair_from_order_id(order.client_order_id))

    def test_get_shadow_market_pair_from_order_id(self):
        # Simulate order being placed and tracked
        order: LimitOrder = self.limit_orders[0]
        self.assertNotEqual(self.market_info, self.order_tracker.get_shadow_market_pair_from_order_id(order.client_order_id))

        self.simulate_place_order(self.order_tracker, order, self.market_info)

        self.assertEqual(self.market_info, self.order_tracker.get_shadow_market_pair_from_order_id(order.client_order_id))

    def test_get_limit_order(self):
        # Initial validation
        order: LimitOrder = self.limit_orders[0]

        # Order not yet placed
        self.assertNotEqual(order, self.order_tracker.get_limit_order(self.market_info, order.client_order_id))

        # Simulate order being placed and tracked
        self.simulate_place_order(self.order_tracker, order, self.market_info)

        # Unrecognized Order
        self.assertNotEqual(order, self.order_tracker.get_limit_order(self.market_info, "UNRECOGNIZED_ORDER"))

        # Matching Order
        other_order = self.order_tracker.get_limit_order(self.market_info, order.client_order_id)
        self.assertEqual(order.trading_pair, other_order.trading_pair)
        self.assertEqual(order.price, other_order.price)
        self.assertEqual(order.quantity, other_order.quantity)
        self.assertEqual(order.is_buy, other_order.is_buy)

    def test_get_market_order(self):
        # Initial validation
        order: MarketOrder = MarketOrder(order_id=f"MARKET//-{self.clock.current_timestamp}",
                                         trading_pair=self.trading_pair,
                                         is_buy=True,
                                         base_asset=self.trading_pair.split("-")[0],
                                         quote_asset=self.trading_pair.split("-")[1],
                                         amount=float(10),
                                         timestamp=self.clock.current_timestamp
                                         )

        # Order not yet placed
        self.assertNotEqual(order, self.order_tracker.get_market_order(self.market_info, order.order_id))

        # Simulate order being placed and tracked
        self.simulate_place_order(self.order_tracker, order, self.market_info)

        # Unrecognized Order
        self.assertNotEqual(order, self.order_tracker.get_market_order(self.market_info, "UNRECOGNIZED_ORDER"))

        # Matching Order
        self.assertEqual(str(order), str(self.order_tracker.get_market_order(self.market_info, order.order_id)))

    def test_get_shadow_limit_order(self):
        # Initial validation
        order: LimitOrder = self.limit_orders[0]

        # Order not yet placed
        self.assertNotEqual(order, self.order_tracker.get_shadow_limit_order(order.client_order_id))

        # Simulate order being placed and tracked
        self.simulate_place_order(self.order_tracker, order, self.market_info)

        # Unrecognized Order
        self.assertNotEqual(order, self.order_tracker.get_shadow_limit_order("UNRECOGNIZED_ORDER"))

        # Matching Order
        shadow_order = self.order_tracker.get_shadow_limit_order(order.client_order_id)
        self.assertEqual(order.trading_pair, shadow_order.trading_pair)
        self.assertEqual(order.price, shadow_order.price)
        self.assertEqual(order.quantity, shadow_order.quantity)
        self.assertEqual(order.is_buy, shadow_order.is_buy)

        # Simulate order cancel
        self.simulate_cancel_order(self.order_tracker, order)

        self.assertNotEqual(order, self.order_tracker.get_shadow_limit_order(order.client_order_id))

    def test_check_and_cleanup_shadow_records(self):
        order: LimitOrder = self.limit_orders[0]

        # Simulate order being placed and tracked
        self.simulate_place_order(self.order_tracker, order, self.market_info)

        # Check for shadow_tracked_limit_order
        self.assertTrue(len(self.order_tracker.shadow_limit_orders) == 1)

        # Simulate order cancel and stop tracking order
        self.simulate_cancel_order(self.order_tracker, order)
        self.simulate_stop_tracking_order(self.order_tracker, order, self.market_info)

        # Check for shadow_tracked_limit_order
        self.assertTrue(len(self.order_tracker.shadow_limit_orders) == 1)

        # Simulates current_timestamp > SHADOW_MAKER_ORDER_KEEP_ALIVE_DURATION
        self.clock.backtest_til(self.start_timestamp + OrderTracker.SHADOW_MAKER_ORDER_KEEP_ALIVE_DURATION + 1)
        self.order_tracker.check_and_cleanup_shadow_records()

        # Check that check_and_cleanup_shadow_records clears shadow_limit_orders
        self.assertTrue(len(self.order_tracker.shadow_limit_orders) == 0)
