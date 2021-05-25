#!/usr/bin/env python
import unittest


class OrderTrackerUnitTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # TODO: Create a dummy OrderTracker
        pass

    @staticmethod
    def simulate_start_tracking_order():
        """
        Simulates an order being succesfully placed.
        """
        pass

    @staticmethod
    def simulate_stop_tracking_order():
        """
        Simulates an order being cancelled or filled completely.
        """
        pass

    def test_active_limit_orders(self):
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
