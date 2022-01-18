from unittest import TestCase

from hummingbot.connector.exchange.mexc.mexc_order_book_message import MexcOrderBookMessage
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class MexcOrderBookMessageTests(TestCase):

    @property
    def get_content(self):
        return {
            "trading_pair": "MX-USDT",
            "update_id": 1637654307737,
            "bids": [{"price": "2.7548", "quantity": "28.18"}],
            "asks": [{"price": "2.7348", "quantity": "18.18"}]
        }

    def test_equality_based_on_type_and_timestamp(self):
        message = MexcOrderBookMessage(message_type=OrderBookMessageType.SNAPSHOT,
                                       content={"data": []},
                                       timestamp=10000000)
        equal_message = MexcOrderBookMessage(message_type=OrderBookMessageType.SNAPSHOT,
                                             content={"data": []},
                                             timestamp=10000000)
        message_with_different_type = MexcOrderBookMessage(message_type=OrderBookMessageType.DIFF,
                                                           content={"data": []},
                                                           timestamp=10000000)
        message_with_different_timestamp = MexcOrderBookMessage(message_type=OrderBookMessageType.SNAPSHOT,
                                                                content={"data": []},
                                                                timestamp=90000000)

        self.assertEqual(message, message)
        self.assertEqual(message, equal_message)
        self.assertNotEqual(message, message_with_different_type)
        self.assertNotEqual(message, message_with_different_timestamp)

    def test_equal_messages_have_equal_hash(self):
        message = MexcOrderBookMessage(message_type=OrderBookMessageType.SNAPSHOT,
                                       content={"data": []},
                                       timestamp=10000000)
        equal_message = MexcOrderBookMessage(message_type=OrderBookMessageType.SNAPSHOT,
                                             content={"data": []},
                                             timestamp=10000000)

        self.assertEqual(hash(message), hash(equal_message))

    def test_delete_buy_order_book_entry_always_has_zero_amount(self):
        message = MexcOrderBookMessage(message_type=OrderBookMessageType.DIFF,
                                       content=self.get_content,
                                       timestamp=1637654307737)
        bids = message.bids

        self.assertEqual(1, len(bids))
        self.assertEqual(2.7548, bids[0].price)
        self.assertEqual(28.18, bids[0].amount)
        self.assertEqual(1637654307737000, bids[0].update_id)

    def test_delete_sell_order_book_entry_always_has_zero_amount(self):
        message = MexcOrderBookMessage(message_type=OrderBookMessageType.DIFF,
                                       content=self.get_content,
                                       timestamp=1637654307737)
        asks = message.asks

        self.assertEqual(1, len(asks))
        self.assertEqual(2.7348, asks[0].price)
        self.assertEqual(18.18, asks[0].amount)
        self.assertEqual(1637654307737000, asks[0].update_id)
