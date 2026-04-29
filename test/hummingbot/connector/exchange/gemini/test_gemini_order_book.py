import unittest
from hummingbot.connector.exchange.gemini.gemini_order_book import GeminiOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class TestGeminiOrderBook(unittest.TestCase):

    def test_snapshot_message_from_exchange(self):
        msg = {
            "bids": [["50000.00", "1.5"], ["49999.00", "2.0"]],
            "asks": [["50001.00", "0.8"], ["50002.00", "1.2"]],
        }
        timestamp = 1640000000.0
        metadata = {"trading_pair": "BTC-USD"}

        result = GeminiOrderBook.snapshot_message_from_exchange(msg, timestamp, metadata)

        self.assertEqual(OrderBookMessageType.SNAPSHOT, result.type)
        self.assertEqual("BTC-USD", result.trading_pair)
        self.assertEqual(int(timestamp * 1000), result.update_id)
        self.assertEqual(timestamp, result.timestamp)
        self.assertEqual(2, len(result.bids))
        self.assertEqual(2, len(result.asks))

    def test_snapshot_message_from_exchange_without_metadata(self):
        msg = {
            "trading_pair": "ETH-USD",
            "bids": [["3000.00", "10"]],
            "asks": [["3001.00", "5"]],
        }
        timestamp = 1640000001.0

        result = GeminiOrderBook.snapshot_message_from_exchange(msg, timestamp)

        self.assertEqual("ETH-USD", result.trading_pair)

    def test_diff_message_from_exchange(self):
        msg = {
            "bids": [["50000.00", "1.5"]],
            "asks": [["50001.00", "0"]],
        }
        timestamp = 1640000002.0
        metadata = {"trading_pair": "BTC-USD"}

        result = GeminiOrderBook.diff_message_from_exchange(msg, timestamp, metadata)

        self.assertEqual(OrderBookMessageType.DIFF, result.type)
        self.assertEqual("BTC-USD", result.trading_pair)
        self.assertEqual(int(timestamp * 1000), result.update_id)
        self.assertEqual(int(timestamp * 1000), result.first_update_id)
        self.assertEqual(1, len(result.bids))
        self.assertEqual(1, len(result.asks))

    def test_diff_message_from_exchange_with_no_timestamp(self):
        msg = {
            "bids": [],
            "asks": [["3001.00", "5"]],
        }
        metadata = {"trading_pair": "ETH-USD"}

        result = GeminiOrderBook.diff_message_from_exchange(msg, metadata=metadata)

        self.assertEqual(OrderBookMessageType.DIFF, result.type)
        self.assertGreater(result.timestamp, 0)

    def test_diff_message_empty_bids_and_asks(self):
        msg = {}
        metadata = {"trading_pair": "BTC-USD"}
        timestamp = 1640000003.0

        result = GeminiOrderBook.diff_message_from_exchange(msg, timestamp, metadata)

        self.assertEqual([], result.bids)
        self.assertEqual([], result.asks)

    def test_trade_message_from_exchange(self):
        msg = {
            "trade": {
                "type": "trade",
                "side": "buy",
                "price": "50000.00",
                "quantity": "0.5",
                "tid": 123456,
                "timestamp": 1640000004000,
            }
        }
        metadata = {"trading_pair": "BTC-USD"}

        result = GeminiOrderBook.trade_message_from_exchange(msg, metadata)

        self.assertEqual(OrderBookMessageType.TRADE, result.type)
        self.assertEqual("BTC-USD", result.trading_pair)
        self.assertEqual(123456, result.trade_id)
        self.assertEqual("50000.00", result.content["price"])
        self.assertEqual("0.5", result.content["amount"])
        self.assertAlmostEqual(1640000004.0, result.timestamp, places=1)
        self.assertEqual(1640000004000, result.content["update_id"])

    def test_trade_message_sell_type(self):
        msg = {
            "trade": {
                "type": "trade",
                "side": "sell",
                "price": "49000.00",
                "quantity": "1.0",
                "tid": 789,
                "timestamp": 1640000005000,
            }
        }
        metadata = {"trading_pair": "BTC-USD"}

        result = GeminiOrderBook.trade_message_from_exchange(msg, metadata)

        self.assertEqual(OrderBookMessageType.TRADE, result.type)
        from hummingbot.core.data_type.common import TradeType
        self.assertEqual(float(TradeType.SELL.value), result.content["trade_type"])

    def test_trade_message_buy_type(self):
        msg = {
            "trade": {
                "type": "trade",
                "side": "buy",
                "price": "51000.00",
                "quantity": "2.0",
                "tid": 999,
                "timestamp": 1640000006000,
            }
        }
        metadata = {"trading_pair": "BTC-USD"}

        result = GeminiOrderBook.trade_message_from_exchange(msg, metadata)

        from hummingbot.core.data_type.common import TradeType
        self.assertEqual(float(TradeType.BUY.value), result.content["trade_type"])

    def test_trade_message_with_missing_timestamp_uses_fallback(self):
        msg = {
            "trade": {
                "type": "trade",
                "side": "buy",
                "price": "50000.00",
                "quantity": "0.1",
                "tid": 111,
            }
        }
        metadata = {"trading_pair": "BTC-USD"}

        result = GeminiOrderBook.trade_message_from_exchange(msg, metadata)

        # Should use time.time() as fallback
        self.assertGreater(result.timestamp, 0)
