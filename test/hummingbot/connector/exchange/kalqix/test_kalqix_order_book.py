from unittest import TestCase

from hummingbot.connector.exchange.kalqix.kalqix_order_book import KalqixOrderBook
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class KalqixOrderBookTests(TestCase):

    def test_snapshot_message_from_exchange(self):
        snapshot_message = KalqixOrderBook.snapshot_message_from_exchange(
            msg={
                "BUY": [
                    {"price_formatted": "4.0", "quantity_formatted": "431.0"},
                ],
                "SELL": [
                    {"price_formatted": "4.000002", "quantity_formatted": "12.0"},
                ],
            },
            timestamp=1640000000.0,
            metadata={"trading_pair": "COINALPHA-HBOT"},
        )

        self.assertEqual("COINALPHA-HBOT", snapshot_message.trading_pair)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual(1640000000.0, snapshot_message.timestamp)
        # No server-side sequence number; synthesized from ms-precision timestamp.
        self.assertEqual(int(1640000000.0 * 1e3), snapshot_message.update_id)
        self.assertEqual(-1, snapshot_message.trade_id)
        self.assertEqual(1, len(snapshot_message.bids))
        self.assertEqual(4.0, snapshot_message.bids[0].price)
        self.assertEqual(431.0, snapshot_message.bids[0].amount)
        self.assertEqual(1, len(snapshot_message.asks))
        self.assertEqual(4.000002, snapshot_message.asks[0].price)
        self.assertEqual(12.0, snapshot_message.asks[0].amount)

    def test_snapshot_message_handles_empty_sides(self):
        snapshot_message = KalqixOrderBook.snapshot_message_from_exchange(
            msg={"BUY": None, "SELL": []},
            timestamp=1640000000.0,
            metadata={"trading_pair": "COINALPHA-HBOT"},
        )
        self.assertEqual(0, len(snapshot_message.bids))
        self.assertEqual(0, len(snapshot_message.asks))

    def test_trade_message_from_exchange_maker_buy_is_taker_sell(self):
        timestamp_microseconds = 1640000000000000
        trade_message = KalqixOrderBook.trade_message_from_exchange(
            msg={
                "trade_id": "abc-123",
                "price_formatted": "0.001",
                "quantity_formatted": "100",
                "timestamp": timestamp_microseconds,
                "maker_side": "BUY",
            },
            metadata={"trading_pair": "COINALPHA-HBOT"},
        )

        self.assertEqual("COINALPHA-HBOT", trade_message.trading_pair)
        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual(timestamp_microseconds * 1e-6, trade_message.timestamp)
        # The microsecond timestamp is carried as the message content update_id
        # (a TRADE OrderBookMessage exposes -1 for the .update_id property).
        self.assertEqual(timestamp_microseconds, trade_message.content["update_id"])
        self.assertEqual("abc-123", trade_message.trade_id)
        # maker was a buyer -> taker sold -> trade direction is SELL
        self.assertEqual(float(TradeType.SELL.value), trade_message.content["trade_type"])
        self.assertEqual("0.001", trade_message.content["price"])
        self.assertEqual("100", trade_message.content["amount"])

    def test_trade_message_from_exchange_maker_sell_is_taker_buy(self):
        trade_message = KalqixOrderBook.trade_message_from_exchange(
            msg={
                "trade_id": "abc-124",
                "price_formatted": "0.001",
                "quantity_formatted": "100",
                "timestamp": 1640000000000001,
                "maker_side": "SELL",
            },
            metadata={"trading_pair": "COINALPHA-HBOT"},
        )
        self.assertEqual(float(TradeType.BUY.value), trade_message.content["trade_type"])

    def test_diff_message_from_exchange_not_supported(self):
        with self.assertRaises(NotImplementedError):
            KalqixOrderBook.diff_message_from_exchange(
                msg={},
                timestamp=1640000000.0,
                metadata={"trading_pair": "COINALPHA-HBOT"},
            )
