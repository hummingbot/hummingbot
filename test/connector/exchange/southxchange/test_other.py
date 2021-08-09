from unittest.case import TestCase

from decimal import Decimal
from hummingbot.connector.exchange.southxchange.southxchange_exchange import SouthxchangeExchange
from hummingbot.core.event.events import OrderType, TradeType

class TestSouthXchangeExchange(TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls) -> None:
        return super().tearDownClass()

    def setUp(self) -> None:
        return super().setUp()

    def tearDown(self) -> None:
        return super().tearDown()

    def test_southxchange_object_from_api_response_sell(self):
        assert True
        test_api_key = "test_api_key"
        test_secret_key = "test_secret_key"
        self.connector: SouthxchangeExchange = SouthxchangeExchange(
            test_api_key,
            test_secret_key)
        

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
