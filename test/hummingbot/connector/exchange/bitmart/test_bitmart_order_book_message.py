from unittest import TestCase

from hummingbot.connector.exchange.bitmart.bitmart_order_book_message import BitmartOrderBookMessage
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class BitmartOrderBookMessageTests(TestCase):

    def _snapshot_rest_example(self):
        return {
            "timestamp": 1527777538000,
            "buys": [
                {
                    "amount": "4800.00",
                    "total": "4800.00",
                    "price": "0.000767",
                    "count": "1"
                },
                {
                    "amount": "99996475.79",
                    "total": "100001275.79",
                    "price": "0.000201",
                    "count": "1"
                },
            ],
            "sells": [
                {
                    "amount": "100.00",
                    "total": "100.00",
                    "price": "0.007000",
                    "count": "1"
                },
                {
                    "amount": "6997.00",
                    "total": "7097.00",
                    "price": "1.000000",
                    "count": "1"
                },
            ]
        }

    def _snapshot_ws_example(self):
        return {
            "asks": [
                [
                    "161.96",
                    "7.37567"
                ]
            ],
            "bids": [
                [
                    "161.94",
                    "4.552355"
                ]
            ],
            "symbol": "ETH_USDT",
            "ms_t": 1542337219120
        }

    def test_equality_based_on_type_and_timestamp(self):
        message = BitmartOrderBookMessage(message_type=OrderBookMessageType.SNAPSHOT,
                                          content={},
                                          timestamp=10000000)
        equal_message = BitmartOrderBookMessage(message_type=OrderBookMessageType.SNAPSHOT,
                                                content={},
                                                timestamp=10000000)
        message_with_different_type = BitmartOrderBookMessage(message_type=OrderBookMessageType.DIFF,
                                                              content={},
                                                              timestamp=10000000)
        message_with_different_timestamp = BitmartOrderBookMessage(message_type=OrderBookMessageType.SNAPSHOT,
                                                                   content={},
                                                                   timestamp=90000000)

        self.assertEqual(message, message)
        self.assertEqual(message, equal_message)
        self.assertNotEqual(message, message_with_different_type)
        self.assertNotEqual(message, message_with_different_timestamp)
        self.assertTrue(message < message_with_different_type)
        self.assertTrue(message < message_with_different_timestamp)

    def test_equal_messages_have_equal_hash(self):
        content = self._snapshot_rest_example()
        message = BitmartOrderBookMessage(message_type=OrderBookMessageType.SNAPSHOT,
                                          content=content,
                                          timestamp=10000000)
        equal_message = BitmartOrderBookMessage(message_type=OrderBookMessageType.SNAPSHOT,
                                                content=content,
                                                timestamp=10000000)

        self.assertEqual(hash(message), hash(equal_message))

    def test_init_error(self):
        with self.assertRaises(ValueError) as context:
            _ = BitmartOrderBookMessage(OrderBookMessageType.SNAPSHOT, {})
        self.assertEqual('timestamp must not be None when initializing snapshot messages.', str(context.exception))

    def test_instance_creation(self):
        content = self._snapshot_rest_example()
        message = BitmartOrderBookMessage(message_type=OrderBookMessageType.SNAPSHOT,
                                          content=content,
                                          timestamp=content["timestamp"])
        bids = message.bids

        self.assertEqual(2, len(bids))
        self.assertEqual(0.000767, bids[0].price)
        self.assertEqual(4800.00, bids[0].amount)
        self.assertEqual(1527777538000, bids[0].update_id)

        asks = message.asks
        self.assertEqual(2, len(asks))
        self.assertEqual(0.007, asks[0].price)
        self.assertEqual(100, asks[0].amount)
        self.assertEqual(1527777538000, asks[0].update_id)

        content = self._snapshot_ws_example()
        message = BitmartOrderBookMessage(message_type=OrderBookMessageType.SNAPSHOT,
                                          content=content,
                                          timestamp=content["ms_t"])
        bids = message.bids

        self.assertEqual(1, len(bids))
        self.assertEqual(161.94, bids[0].price)
        self.assertEqual(4.552355, bids[0].amount)
        self.assertEqual(1542337219120, bids[0].update_id)

        asks = message.asks
        self.assertEqual(1, len(asks))
        self.assertEqual(161.96, asks[0].price)
        self.assertEqual(7.37567, asks[0].amount)
        self.assertEqual(1542337219120, asks[0].update_id)

        self.assertEqual(message.trading_pair, "ETH_USDT")
