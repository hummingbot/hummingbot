import unittest
from decimal import Decimal

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', '..'))

from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.core.data_type.in_flight_order import OrderState


class TestArchitectPerpetualConstants(unittest.TestCase):

    def test_exchange_name(self):
        self.assertEqual(CONSTANTS.EXCHANGE_NAME, "architect_perpetual")

    def test_broker_id(self):
        self.assertEqual(CONSTANTS.BROKER_ID, "HBOT")

    def test_max_order_id_len(self):
        self.assertEqual(CONSTANTS.MAX_ORDER_ID_LEN, 36)

    def test_market_order_slippage(self):
        self.assertEqual(CONSTANTS.MARKET_ORDER_SLIPPAGE, 0.05)

    def test_domains(self):
        self.assertEqual(CONSTANTS.DOMAIN, "architect_perpetual")
        self.assertEqual(CONSTANTS.TESTNET_DOMAIN, "architect_perpetual_testnet")

    def test_endpoints(self):
        self.assertEqual(CONSTANTS.PERPETUAL_ENDPOINT, "https://app.architect.co")
        self.assertEqual(CONSTANTS.TESTNET_ENDPOINT, "https://sandbox.architect.co")

    def test_order_states(self):
        self.assertEqual(CONSTANTS.ORDER_STATE["open"], OrderState.OPEN)
        self.assertEqual(CONSTANTS.ORDER_STATE["pending"], OrderState.PENDING_CREATE)
        self.assertEqual(CONSTANTS.ORDER_STATE["filled"], OrderState.FILLED)
        self.assertEqual(CONSTANTS.ORDER_STATE["canceled"], OrderState.CANCELED)
        self.assertEqual(CONSTANTS.ORDER_STATE["rejected"], OrderState.FAILED)

    def test_rate_limits_exist(self):
        self.assertIsNotNone(CONSTANTS.RATE_LIMITS)
        self.assertGreater(len(CONSTANTS.RATE_LIMITS), 0)

    def test_max_request(self):
        self.assertEqual(CONSTANTS.MAX_REQUEST, 1200)

    def test_heartbeat_interval(self):
        self.assertEqual(CONSTANTS.HEARTBEAT_TIME_INTERVAL, 30.0)

    def test_funding_rate_interval(self):
        self.assertEqual(CONSTANTS.FUNDING_RATE_UPDATE_INTERNAL_SECOND, 60)


if __name__ == "__main__":
    unittest.main()
