from unittest import TestCase

from hummingbot.connector.exchange.gemini.gemini_order_book import GeminiOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class GeminiOrderBookTests(TestCase):

    def test_snapshot_message_from_exchange(self):
        msg = {
            "bids": [["50000.00", "1.5"], ["49999.00", "2.0"]],
            "asks": [["50001.00", "1.0"], ["50002.00", "3.0"]],
        }
        snapshot = GeminiOrderBook.snapshot_message_from_exchange(
            msg, timestamp=1234567890.0, metadata={"trading_pair": "BTC-USD"}
        )
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot.type)
        self.assertEqual("BTC-USD", snapshot.content["trading_pair"])
        self.assertEqual(2, len(snapshot.content["bids"]))
        self.assertEqual(2, len(snapshot.content["asks"]))

    def test_diff_message_from_exchange(self):
        msg = {
            "e": "depthUpdate",
            "E": 1234567890000,
            "s": "BTCUSD",
            "U": 100,
            "u": 200,
            "b": [["50000.00", "1.5"]],
            "a": [["50001.00", "0"]],
        }
        diff = GeminiOrderBook.diff_message_from_exchange(
            msg, timestamp=1234567890.0, metadata={"trading_pair": "BTC-USD"}
        )
        self.assertEqual(OrderBookMessageType.DIFF, diff.type)
        self.assertEqual("BTC-USD", diff.content["trading_pair"])
        self.assertEqual(100, diff.content["first_update_id"])
        self.assertEqual(200, diff.content["update_id"])

    def test_trade_message_from_exchange(self):
        msg = {
            "e": "trade",
            "E": 1234567890000,
            "s": "BTCUSD",
            "t": 12345,
            "p": "50000.00",
            "q": "0.5",
            "m": True,  # maker side
        }
        trade = GeminiOrderBook.trade_message_from_exchange(
            msg, metadata={"trading_pair": "BTC-USD"}
        )
        self.assertEqual(OrderBookMessageType.TRADE, trade.type)
        self.assertEqual("BTC-USD", trade.content["trading_pair"])
        self.assertEqual(12345, trade.content["trade_id"])
        self.assertEqual("50000.00", trade.content["price"])
        self.assertEqual("0.5", trade.content["amount"])
