#!/usr/bin/env python
import unittest

from decimal import Decimal
from typing import (
    List,
    Union,
)

from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.market_order import MarketOrder
from hummingbot.strategy.order_tracker import OrderTracker
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

from hummingsim.backtest.backtest_market import BacktestMarket


class OrderTrackerUnitTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.trading_pair = "COINALPHA-HBOT"

        cls.limit_orders: List[LimitOrder] = [
            LimitOrder(client_order_id=f"order-{i}",
                       trading_pair=cls.trading_pair,
                       is_buy=True if i % 2 == 0 else False,
                       base_currency=cls.trading_pair.split("-")[0],
                       quote_currency=cls.trading_pair.split("-")[1],
                       price=Decimal(f"{100 - i}") if i % 2 == 0 else Decimal(f"{100 + i}"),
                       quantity=Decimal(f"{10 * (i + 1)}")
                       )
            for i in range(20)
        ]
        cls.market_orders: List[MarketOrder] = [
            MarketOrder(order_id=f"order-{i}",
                        trading_pair=cls.trading_pair,
                        is_buy=True if i % 2 == 0 else False,
                        base_asset=cls.trading_pair.split("-")[0],
                        quote_asset=cls.trading_pair.split("-")[1],
                        amount=Decimal(f"{10 * (i + 1)}"),
                        timestamp=0
                        )
            for i in range(20)
        ]

        cls.market: BacktestMarket = BacktestMarket()
        cls.market_info: MarketTradingPairTuple = MarketTradingPairTuple(
            cls.market, cls.trading_pair, *cls.trading_pair.split("-")
        )

    def setUp(self):
        self.order_tracker: OrderTracker = OrderTracker()

    @staticmethod
    def simulate_start_tracking_order(order_tracker: OrderTracker, order: Union[LimitOrder, MarketOrder], market_info: MarketTradingPairTuple):
        """
        Simulates an order being succesfully placed.
        """
        if isinstance(order, LimitOrder):
            order_tracker.start_tracking_limit_order(market_info=market_info,
                                                     order=order
                                                     )
        else:
            order_tracker.start_tracking_market_order(market_info=market_info,
                                                      order=order
                                                      )

    @staticmethod
    def simulate_stop_tracking_order(order_tracker: OrderTracker):
        """
        Simulates an order being cancelled or filled completely.
        """
        pass

    @staticmethod
    def simulate_add_create_order_pending(order_tracker: OrderTracker):
        """
        Simulates an order creation request being issued.
        """
        pass

    @staticmethod
    def simulate_remove_create_order_pending(order_tracker: OrderTracker):
        """
        Simulates an order cancellation request being issued.
        """
        pass

    def test_active_limit_orders(self):
        # Check initial active limit orders
        self.assertTrue(len(self.order_tracker.active_limit_orders) == 0)

        # Simulate orders being tracked
        for order in self.limit_orders:
            self.simulate_start_tracking_order(self.order_tracker, order, self.market_info)

        pass

    def test_shadow_limit_orders(self):
        pass

    def test_market_pair_to_active_orders(self):
        pass

    def test_active_bids(self):
        pass

    def test_active_asks(self):
        pass

    def test_tracked_limit_orders(self):
        pass

    def test_tracked_limit_orders_data_frame(self):
        pass

    def test_tracked_market_orders(self):
        pass

    def test_tracked_market_order_data_frame(self):
        pass

    def test_in_flight_cancels(self):
        pass

    def test_in_flight_pending_created(self):
        pass

    def test_get_limit_orders(self):
        pass

    def test_get_market_orders(self):
        pass

    def test_get_market_pair_from_order_id(self):
        pass

    def test_get_shadow_market_pair_from_order_id(self):
        pass

    def test_get_limit_order(self):
        pass

    def test_get_market_order(self):
        pass

    def test_get_shadow_limit_order(self):
        pass
