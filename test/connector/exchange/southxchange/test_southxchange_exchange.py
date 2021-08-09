from unittest.case import TestCase

from decimal import Decimal
from hummingbot.core.event.events import OrderType, TradeType
from hummingbot.connector.exchange.southxchange.southxchange_exchange import SouthxchangeExchange

class TestSouthXchangeExchange(TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls) -> None:
        return super().tearDownClass()

    def setUp(self) -> None:
        test_api_key = "test_api_key"
        test_secret_key = "test_secret_key"
        self.connector: SouthxchangeExchange = SouthxchangeExchange(
            test_api_key,
            test_secret_key)
        return None

    def tearDown(self) -> None:
        return super().tearDown()

    def test_test(self):
        self.connector.start_tracking_order(
            "1",
            "1",
            "BTC2-USD2",
            TradeType.BUY,
            Decimal("1"),
            Decimal("1"),
            OrderType.MARKET
        )
        self.assertTrue(self.connector.in_flight_orders.__len__() != 0)
        self.connector._execute_cancel("BTC2-USD2", "1")
        self.assertTrue(self.connector.in_flight_orders.__len__() == 0)
