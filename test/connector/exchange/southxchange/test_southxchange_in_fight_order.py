from datetime import datetime
from dateutil import parser
from decimal import Decimal

from hummingbot.core.event.events import TradeType
from unittest.case import TestCase
from hummingbot.connector.exchange.southxchange.southxchange_in_flight_order import SouthXchangeInFlightOrder
from hummingbot.connector.exchange.southxchange.southxchange_utils import  time_to_num

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
            'client_order_id':'SX-HMBot-B-LTC2-USD2-1634561259964310',
            'exchange_order_id':'20001',
            'trading_pair':'LTC2-USD2',
            'order_type':'LIMIT_MAKER',
            'trade_type':'SELL',
            'price':'74.88000000',
            'amount':'0.00020000',
            'executed_amount_base':'0',
            'executed_amount_quote':'0',
            'fee_asset':None,
            'fee_paid':'0',
            'last_state':'executed',
        }

        in_flight_order = SouthXchangeInFlightOrder.from_json(api_response)

        assert in_flight_order.exchange_order_id == api_response["exchange_order_id"]
        assert in_flight_order.trade_type == TradeType.SELL
        assert in_flight_order.amount == Decimal(api_response["amount"])
        assert in_flight_order.trading_pair == api_response["trading_pair"]
        assert in_flight_order.price == Decimal(api_response["price"])

    def test_southxchange_object_from_api_response_buy(self):
        api_response = {
            'client_order_id':'SX-HMBot-B-LTC2-USD2-1634561259964310',
            'exchange_order_id':'20001',
            'trading_pair':'LTC2-USD2',
            'order_type':'LIMIT_MAKER',
            'trade_type':'BUY',
            'price':'74.88000000',
            'amount':'0.00020000',
            'executed_amount_base':'0',
            'executed_amount_quote':'0',
            'fee_asset':None,
            'fee_paid':'0',
            'last_state':'executed',
        }

        in_flight_order = SouthXchangeInFlightOrder.from_json(api_response)

        assert in_flight_order.exchange_order_id == api_response["exchange_order_id"]
        assert in_flight_order.trade_type == TradeType.BUY
        assert in_flight_order.amount == Decimal(api_response["amount"])
        assert in_flight_order.trading_pair == api_response["trading_pair"]
        assert in_flight_order.price == Decimal(api_response["price"])

    def test_in_flight_order_status_executed(self):
        api_response = {
            'client_order_id':'SX-HMBot-B-LTC2-USD2-1634561259964310',
            'exchange_order_id':'20001',
            'trading_pair':'LTC2-USD2',
            'order_type':'LIMIT_MAKER',
            'trade_type':'BUY',
            'price':'74.88000000',
            'amount':'0.00020000',
            'executed_amount_base':'0',
            'executed_amount_quote':'0',
            'fee_asset':None,
            'fee_paid':'0',
            'last_state':'executed',
        }

        in_flight_order = SouthXchangeInFlightOrder.from_json(api_response)

        assert in_flight_order.is_done
        assert not in_flight_order.is_failure
        assert not in_flight_order.is_cancelled

    def test_in_flight_order_status_canceled(self):
        api_response = {
            'client_order_id':'SX-HMBot-B-LTC2-USD2-1634561259964310',
            'exchange_order_id':'20001',
            'trading_pair':'LTC2-USD2',
            'order_type':'LIMIT_MAKER',
            'trade_type':'BUY',
            'price':'74.88000000',
            'amount':'0.00020000',
            'executed_amount_base':'0',
            'executed_amount_quote':'0',
            'fee_asset':None,
            'fee_paid':'0',
            'last_state':'cancelednotexecuted',
        }

        in_flight_order = SouthXchangeInFlightOrder.from_json(api_response)

        assert not in_flight_order.is_done
        assert not in_flight_order.is_failure
        assert in_flight_order.is_cancelled