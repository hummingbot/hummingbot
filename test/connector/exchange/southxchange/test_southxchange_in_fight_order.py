from hummingbot.core.event.events import TradeType
from unittest.case import TestCase
from hummingbot.connector.exchange.southxchange.southxchange_in_flight_order import SouthXchangeInFlightOrder


class TestSouthXchangeInFlightOrder(TestCase):

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
        api_response = {
            "Code": "dummyOrderId",
            "Type": "sell",
            "Amount": 123,
            "LimitPrice": 123,
            "ListingCurrency": "BTC2",
            "ReferenceCurrency": "USD2",
            "Status": "Executed",
            "DateAdded": "2021-07-29T15:26:42.120Z"
        }

        in_flight_order = SouthXchangeInFlightOrder.from_json(api_response)

        assert in_flight_order.exchange_order_id == api_response["Code"]
        assert in_flight_order.trade_type == TradeType.SELL
        assert in_flight_order.amount == api_response["Amount"]
        assert in_flight_order.trading_pair == "BTC2-USD2"
        assert in_flight_order.price == api_response["LimitPrice"]

    def test_southxchange_object_from_api_response_buy(self):
        api_response = {
            "Code": "dummyOrderId",
            "Type": "buy",
            "Amount": 123,
            "LimitPrice": 123,
            "ListingCurrency": "BTC2",
            "ReferenceCurrency": "USD2",
            "Status": "Executed",
            "DateAdded": "2021-07-29T15:26:42.120Z"
        }

        in_flight_order = SouthXchangeInFlightOrder.from_json(api_response)

        assert in_flight_order.exchange_order_id == api_response["Code"]
        assert in_flight_order.trade_type == TradeType.BUY
        assert in_flight_order.amount == api_response["Amount"]
        assert in_flight_order.trading_pair == "BTC2-USD2"
        assert in_flight_order.price == api_response["LimitPrice"]

    def test_in_flight_order_status_executed(self):
        api_response = {
            "Code": "dummyOrderId",
            "Type": "sell",
            "Amount": 123,
            "LimitPrice": 123,
            "ListingCurrency": "BTC2",
            "ReferenceCurrency": "USD2",
            "Status": "Executed",
            "DateAdded": "2021-07-29T15:26:42.120Z"
        }

        in_flight_order = SouthXchangeInFlightOrder.from_json(api_response)

        assert in_flight_order.is_done
        assert not in_flight_order.is_failure
        assert not in_flight_order.is_cancelled
