from unittest import TestCase

from hummingbot.connector.exchange.xt.xt_order_book import XtOrderBook
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class XtOrderBookTests(TestCase):
    def test_snapshot_preserves_exchange_sequence_and_timestamp(self):
        raw = {"result": {"lastUpdateId": "123", "bids": [["4", "10"]], "asks": [["5", "20"]]}}
        message = XtOrderBook.snapshot_message_from_exchange(raw, 0, {"trading_pair": "COINALPHA-HBOT"})
        self.assertEqual(OrderBookMessageType.SNAPSHOT, message.type)
        self.assertEqual("COINALPHA-HBOT", message.trading_pair)
        self.assertEqual(123, message.update_id)
        self.assertEqual(0, message.timestamp)
        self.assertEqual((4, 10, 123), tuple(message.bids[0]))
        self.assertEqual((5, 20, 123), tuple(message.asks[0]))
        self.assertNotIn("trading_pair", raw["result"])

    def test_snapshot_requires_exchange_sequence(self):
        with self.assertRaises(KeyError):
            XtOrderBook.snapshot_message_from_exchange({"result": {"timestamp": 123}}, metadata={"trading_pair": "ETH-USDT"})

    def test_diff_preserves_update_range_and_zero_quantity(self):
        raw = {"data": {"fi": "124", "i": "127", "b": [["4", "0"]], "a": [["5", "3"]]}}
        message = XtOrderBook.diff_message_from_exchange(raw, 0, {"trading_pair": "ETH-USDT"})
        self.assertEqual(OrderBookMessageType.DIFF, message.type)
        self.assertEqual("ETH-USDT", message.trading_pair)
        self.assertEqual(124, message.first_update_id)
        self.assertEqual(127, message.update_id)
        self.assertEqual(0, message.timestamp)
        self.assertEqual((4, 0, 127), tuple(message.bids[0]))
        self.assertNotIn("trading_pair", raw["data"])

    def test_diff_applies_absolute_quantities_through_native_order_book(self):
        snapshot = XtOrderBook.snapshot_message_from_exchange(
            {"lastUpdateId": 123, "bids": [["4", "10"]], "asks": [["5", "20"]]}, 1,
            {"trading_pair": "COINALPHA-HBOT"})
        diff = XtOrderBook.diff_message_from_exchange(
            {"data": {"fi": 124, "i": 127, "b": [["4", "0"], ["3", "2"]], "a": [["5", "3"]]}}, 2,
            {"trading_pair": "COINALPHA-HBOT"})
        book = OrderBook()
        book.apply_snapshot(snapshot.bids, snapshot.asks, snapshot.update_id)
        book.apply_diffs(diff.bids, diff.asks, diff.update_id)
        self.assertEqual([(3, 2, 127)], [tuple(row) for row in book.bid_entries()])
        self.assertEqual([(5, 3, 127)], [tuple(row) for row in book.ask_entries()])

    def test_trade_uses_exchange_time_id_and_taker_side(self):
        for maker, side in [(True, TradeType.SELL), (False, TradeType.BUY)]:
            with self.subTest(maker=maker):
                message = XtOrderBook.trade_message_from_exchange(
                    {"data": {"i": "789", "t": 1640001112223, "p": "4", "q": "10", "b": maker}},
                    {"trading_pair": "COINALPHA-HBOT"})
                self.assertEqual(OrderBookMessageType.TRADE, message.type)
                self.assertEqual(1640001112.223, message.timestamp)
                self.assertEqual("789", message.trade_id)
                self.assertEqual(float(side.value), message.content["trade_type"])
                self.assertEqual("4", message.content["price"])
                self.assertEqual("10", message.content["amount"])
