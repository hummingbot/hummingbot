from unittest import TestCase

from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_order_book import GrvtPerpetualOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class GrvtPerpetualOrderBookTests(TestCase):
    def test_snapshot_message_from_exchange(self):
        snapshot_message = GrvtPerpetualOrderBook.snapshot_message_from_exchange(
            msg={
                "event_time": "1700000000000000000",
                "bids": [{"price": "62000", "size": "1.2"}],
                "asks": [{"price": "62010", "size": "1.5"}],
            },
            timestamp=1700000000.0,
            metadata={"trading_pair": "BTC-USDT"},
        )

        self.assertEqual("BTC-USDT", snapshot_message.trading_pair)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual(1700000000.0, snapshot_message.timestamp)
        self.assertEqual([["62000", "1.2"]], snapshot_message.content["bids"])
        self.assertEqual([["62010", "1.5"]], snapshot_message.content["asks"])

    def test_snapshot_message_from_ws(self):
        snapshot_message = GrvtPerpetualOrderBook.snapshot_message_from_ws(
            msg={
                "stream": "v1.book.s",
                "feed": {
                    "event_time": "1700000000000000000",
                    "instrument": "BTC_USDT_Perp",
                    "bids": [{"price": "62000", "size": "1.2"}],
                    "asks": [{"price": "62010", "size": "1.5"}],
                },
            },
            metadata={"trading_pair": "BTC-USDT"},
        )

        self.assertEqual("BTC-USDT", snapshot_message.trading_pair)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual(1700000000.0, snapshot_message.timestamp)

    def test_diff_message_from_exchange(self):
        diff_message = GrvtPerpetualOrderBook.diff_message_from_exchange(
            msg={
                "stream": "v1.book.d",
                "feed": {
                    "event_time": "1700000000000000000",
                    "instrument": "BTC_USDT_Perp",
                    "bids": [{"price": "62000", "size": "1.2"}],
                    "asks": [{"price": "62010", "size": "1.5"}],
                },
            },
            metadata={"trading_pair": "BTC-USDT"},
        )

        self.assertEqual("BTC-USDT", diff_message.trading_pair)
        self.assertEqual(OrderBookMessageType.DIFF, diff_message.type)
        self.assertEqual([["62000", "1.2"]], diff_message.content["bids"])

    def test_trade_message_from_exchange(self):
        trade_message = GrvtPerpetualOrderBook.trade_message_from_exchange(
            msg={
                "stream": "v1.trade",
                "feed": {
                    "event_time": "1700000000000000000",
                    "instrument": "BTC_USDT_Perp",
                    "is_taker_buyer": True,
                    "trade_id": "t-1",
                    "price": "62000",
                    "size": "0.5",
                },
            },
            metadata={"trading_pair": "BTC-USDT"},
        )

        self.assertEqual("BTC-USDT", trade_message.trading_pair)
        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual("t-1", trade_message.trade_id)
        self.assertEqual(1700000000.0, trade_message.timestamp)
