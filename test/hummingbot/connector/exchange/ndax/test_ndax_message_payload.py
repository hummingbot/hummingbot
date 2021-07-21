from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.exchange.ndax.ndax_message_payload import NdaxMessagePayload, NdaxUnknownMessagePayload


class NdaxMessagePayloadTest(TestCase):

    def test_instance_creation_with_unknown_endpoint(self):
        message = NdaxMessagePayload.new_instance(endpoint='InvalidEndpoint', payload={})

        self.assertEqual(NdaxUnknownMessagePayload, type(message))
        self.assertEqual('InvalidEndpoint', message.endpoint)
        self.assertEqual({}, message.payload)


class NdaxAccountPositionEventPayloadTest(TestCase):

    def test_instance_creation(self):
        payload = {"OMSId": 4,
                   "AccountId": 5,
                   "ProductSymbol": "BTC",
                   "ProductId": 1,
                   "Amount": 10499.1,
                   "Hold": 2.1,
                   "PendingDeposits": 10,
                   "PendingWithdraws": 20,
                   "TotalDayDeposits": 30,
                   "TotalDayWithdraws": 40}
        position_payload = NdaxMessagePayload.new_instance(endpoint='AccountPositionEvent', payload=payload)

        self.assertEqual(4, position_payload.oms_id)
        self.assertEqual(5, position_payload.account_id)
        self.assertEqual("BTC", position_payload.product_symbol)
        self.assertEqual(1, position_payload.product_id)
        self.assertEqual(Decimal(str(10499.1)), position_payload.amount)
        self.assertEqual(Decimal(str(2.1)), position_payload.on_hold)
        self.assertEqual(Decimal(str(10)), position_payload.pending_deposits)
        self.assertEqual(Decimal(str(20)), position_payload.pending_withdraws)
        self.assertEqual(Decimal(str(30)), position_payload.total_day_deposits)
        self.assertEqual(Decimal(str(40)), position_payload.total_day_withdraws)
