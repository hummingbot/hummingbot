from unittest import TestCase

from hummingbot.connector.exchange.msamex.msamex_order_book_message import mSamexOrderBookMessage
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class mSamexOrderBookMessageTests(TestCase):

    def _snapshot_example(self):
        return {
            "bids": [
                ["0.000767", "4800.00"],
                ["0.000201", "100001275.79"]
            ],
            "asks": [
                ["0.007000", "100.00"],
                ["1.000000", "6997.00"]
            ],
            "market": "ethusdt",
            "timestamp": 1542337219120
        }

    def test_equality_based_on_type_and_timestamp(self):
        message = mSamexOrderBookMessage(message_type=OrderBookMessageType.SNAPSHOT,
                                             content={},
                                             timestamp=10000000)
        equal_message = mSamexOrderBookMessage(message_type=OrderBookMessageType.SNAPSHOT,
                                                   content={},
                                                   timestamp=10000000)
        message_with_different_type = mSamexOrderBookMessage(message_type=OrderBookMessageType.DIFF,
                                                                 content={},
                                                                 timestamp=10000000)
        message_with_different_timestamp = mSamexOrderBookMessage(message_type=OrderBookMessageType.SNAPSHOT,
                                                                      content={},
                                                                      timestamp=90000000)

        self.assertEqual(message, message)
        self.assertEqual(message, equal_message)
        self.assertNotEqual(message, message_with_different_type)
        self.assertNotEqual(message, message_with_different_timestamp)
        self.assertTrue(message < message_with_different_type)
        self.assertTrue(message < message_with_different_timestamp)

    def test_equal_messages_have_equal_hash(self):
        content = self._snapshot_example()
        message = mSamexOrderBookMessage(message_type=OrderBookMessageType.SNAPSHOT,
                                             content=content,
                                             timestamp=10000000)
        equal_message = mSamexOrderBookMessage(message_type=OrderBookMessageType.SNAPSHOT,
                                                   content=content,
                                                   timestamp=10000000)

        self.assertEqual(hash(message), hash(equal_message))

    def test_init_error(self):
        with self.assertRaises(ValueError) as context:
            _ = mSamexOrderBookMessage(OrderBookMessageType.SNAPSHOT, {})
        self.assertEqual('timestamp must not be None when initializing snapshot messages.', str(context.exception))

    def test_instance_creation(self):
        content = self._snapshot_example()
        message = mSamexOrderBookMessage(message_type=OrderBookMessageType.SNAPSHOT,
                                             content=content,
                                             timestamp=content["timestamp"])
        bids = message.bids

        self.assertEqual(2, len(bids))
        self.assertEqual(0.000767, bids[0].price)
        self.assertEqual(4800.00, bids[0].amount)
        self.assertEqual(1542337219120 * 1e3, bids[0].update_id)

        asks = message.asks
        self.assertEqual(2, len(asks))
        self.assertEqual(0.007, asks[0].price)
        self.assertEqual(100, asks[0].amount)
        self.assertEqual(1542337219120 * 1e3, asks[0].update_id)

        self.assertEqual(message.trading_pair, "ETH-USDT")
