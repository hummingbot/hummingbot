import time

from unittest import TestCase

from hummingbot.connector.exchange.ndax.ndax_order_book_message import NdaxOrderBookMessage, NdaxOrderBookEntry
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class NdaxOrderBookMessageTests(TestCase):

    def test_equality_based_on_type_and_timestamp(self):
        message = NdaxOrderBookMessage(message_type=OrderBookMessageType.SNAPSHOT,
                                       content={"data": []},
                                       timestamp=10000000)
        equal_message = NdaxOrderBookMessage(message_type=OrderBookMessageType.SNAPSHOT,
                                             content={"data": []},
                                             timestamp=10000000)
        message_with_different_type = NdaxOrderBookMessage(message_type=OrderBookMessageType.DIFF,
                                                           content={"data": []},
                                                           timestamp=10000000)
        message_with_different_timestamp = NdaxOrderBookMessage(message_type=OrderBookMessageType.SNAPSHOT,
                                                                content={"data": []},
                                                                timestamp=90000000)

        self.assertEqual(message, message)
        self.assertEqual(message, equal_message)
        self.assertNotEqual(message, message_with_different_type)
        self.assertNotEqual(message, message_with_different_timestamp)

    def test_equal_messages_have_equal_hash(self):
        message = NdaxOrderBookMessage(message_type=OrderBookMessageType.SNAPSHOT,
                                       content={"data": []},
                                       timestamp=10000000)
        equal_message = NdaxOrderBookMessage(message_type=OrderBookMessageType.SNAPSHOT,
                                             content={"data": []},
                                             timestamp=10000000)

        self.assertEqual(hash(message), hash(equal_message))

    def test_delete_buy_order_book_entry_always_has_zero_amount(self):
        entries = [NdaxOrderBookEntry(mdUpdateId=1,
                                      accountId=1,
                                      actionDateTime=1627935956059,
                                      actionType=2,
                                      lastTradePrice=42211.51,
                                      orderId=1,
                                      price=41508.19,
                                      productPairCode=5,
                                      quantity=1.5,
                                      side=0)]
        content = {"data": entries}
        message = NdaxOrderBookMessage(message_type=OrderBookMessageType.DIFF,
                                       content=content,
                                       timestamp=time.time())
        bids = message.bids

        self.assertEqual(1, len(bids))
        self.assertEqual(41508.19, bids[0].price)
        self.assertEqual(0.0, bids[0].amount)
        self.assertEqual(1, bids[0].update_id)

    def test_delete_sell_order_book_entry_always_has_zero_amount(self):
        entries = [NdaxOrderBookEntry(mdUpdateId=1,
                                      accountId=1,
                                      actionDateTime=1627935956059,
                                      actionType=2,
                                      lastTradePrice=42211.51,
                                      orderId=1,
                                      price=41508.19,
                                      productPairCode=5,
                                      quantity=1.5,
                                      side=1)]
        content = {"data": entries}
        message = NdaxOrderBookMessage(message_type=OrderBookMessageType.DIFF,
                                       content=content,
                                       timestamp=time.time())
        asks = message.asks

        self.assertEqual(1, len(asks))
        self.assertEqual(41508.19, asks[0].price)
        self.assertEqual(0.0, asks[0].amount)
        self.assertEqual(1, asks[0].update_id)
