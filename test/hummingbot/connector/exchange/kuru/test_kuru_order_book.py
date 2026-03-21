from unittest import TestCase

from hummingbot.connector.exchange.kuru.kuru_order_book import KuruOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class TestKuruOrderBook(TestCase):

    def _base_snapshot_msg(self):
        return {
            "trading_pair": "MON-USDC",
            "update_id": 42,
            "bids": [[1.5, 100.0], [1.4, 200.0]],
            "asks": [[1.6, 50.0], [1.7, 80.0]],
        }

    def _base_trade_msg(self):
        return {
            "trading_pair": "MON-USDC",
            "trade_type": 1.0,
            "trade_id": "trade-001",
            "price": 1.55,
            "amount": 10.0,
            "timestamp": 1700000000.0,
        }

    # ------------------------------------------------------------------
    # snapshot_message_from_exchange
    # ------------------------------------------------------------------

    def test_snapshot_message_from_exchange_without_metadata(self):
        msg = self._base_snapshot_msg()
        result = KuruOrderBook.snapshot_message_from_exchange(msg, timestamp=1234567890.0)

        self.assertEqual(OrderBookMessageType.SNAPSHOT, result.type)
        self.assertEqual(1234567890.0, result.timestamp)
        self.assertEqual("MON-USDC", result.content["trading_pair"])
        self.assertEqual(42, result.content["update_id"])
        self.assertEqual([[1.5, 100.0], [1.4, 200.0]], result.content["bids"])
        self.assertEqual([[1.6, 50.0], [1.7, 80.0]], result.content["asks"])

    def test_snapshot_message_from_exchange_with_metadata_merges_into_msg(self):
        msg = self._base_snapshot_msg()
        # metadata overrides update_id and adds a custom key
        metadata = {"update_id": 99, "extra_key": "extra_value"}
        result = KuruOrderBook.snapshot_message_from_exchange(msg, timestamp=9999.0, metadata=metadata)

        self.assertEqual(OrderBookMessageType.SNAPSHOT, result.type)
        self.assertEqual(9999.0, result.timestamp)
        # update_id should be overridden by metadata
        self.assertEqual(99, result.content["update_id"])
        self.assertEqual("MON-USDC", result.content["trading_pair"])

    # ------------------------------------------------------------------
    # trade_message_from_exchange
    # ------------------------------------------------------------------

    def test_trade_message_from_exchange_without_metadata(self):
        msg = self._base_trade_msg()
        result = KuruOrderBook.trade_message_from_exchange(msg)

        self.assertEqual(OrderBookMessageType.TRADE, result.type)
        self.assertEqual(1700000000.0, result.timestamp)
        self.assertEqual("MON-USDC", result.content["trading_pair"])
        self.assertEqual(1.0, result.content["trade_type"])
        self.assertEqual("trade-001", result.content["trade_id"])
        self.assertEqual(1.55, result.content["price"])
        self.assertEqual(10.0, result.content["amount"])

    def test_trade_message_from_exchange_with_metadata_merges_into_msg(self):
        msg = self._base_trade_msg()
        # metadata overrides trading_pair
        metadata = {"trading_pair": "ETH-USDC", "trade_id": "trade-002"}
        result = KuruOrderBook.trade_message_from_exchange(msg, metadata=metadata)

        self.assertEqual(OrderBookMessageType.TRADE, result.type)
        # trading_pair should be overridden by metadata
        self.assertEqual("ETH-USDC", result.content["trading_pair"])
        self.assertEqual("trade-002", result.content["trade_id"])
        # timestamp comes from the (now mutated) msg
        self.assertEqual(1700000000.0, result.timestamp)
