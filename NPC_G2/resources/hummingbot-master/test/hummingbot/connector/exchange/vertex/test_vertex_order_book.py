from unittest import TestCase

from hummingbot.connector.exchange.vertex.vertex_order_book import VertexOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class VertexOrderBookTests(TestCase):
    def test_snapshot_message_from_exchange(self):
        snapshot_message = VertexOrderBook.snapshot_message_from_exchange_rest(
            msg={
                "data": {
                    "timestamp": 1640000000.0,
                    "bids": [["4000000000000000000", "431000000000000000000"]],
                    "asks": [["4000002000000000000", "12000000000000000000"]],
                }
            },
            timestamp=1640000000.0,
            metadata={"trading_pair": "COINALPHA-HBOT"},
        )
        self.assertEqual("COINALPHA-HBOT", snapshot_message.trading_pair)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual(1640000000.0, snapshot_message.timestamp)
        self.assertEqual(1640000000, snapshot_message.update_id)
        self.assertEqual(1, len(snapshot_message.bids))
        self.assertEqual(4.0, snapshot_message.bids[0].price)
        self.assertEqual(431.0, snapshot_message.bids[0].amount)
        self.assertEqual(1, len(snapshot_message.asks))
        self.assertEqual(4.000002, snapshot_message.asks[0].price)
        self.assertEqual(12.0, snapshot_message.asks[0].amount)

    def test_diff_message_from_exchange(self):
        diff_msg = VertexOrderBook.diff_message_from_exchange(
            msg={
                "last_max_timestamp": 1640000000000000000.0,
                "product_id": 1,
                "bids": [["4000000000000000000", "431000000000000000000"]],
                "asks": [["4000002000000000000", "12000000000000000000"]],
            },
            timestamp=1640000000000000000.0,
            metadata={"trading_pair": "COINALPHA-HBOT"},
        )

        self.assertEqual("COINALPHA-HBOT", diff_msg.trading_pair)
        self.assertEqual(OrderBookMessageType.DIFF, diff_msg.type)
        self.assertEqual(1640000000.0, diff_msg.timestamp)
        self.assertEqual(1640000000000000000, diff_msg.update_id)
        self.assertEqual(1640000000000000000, diff_msg.first_update_id)
        self.assertEqual(-1, diff_msg.trade_id)
        self.assertEqual(1, len(diff_msg.bids))
        self.assertEqual(4.0, diff_msg.bids[0].price)
        self.assertEqual(431, diff_msg.bids[0].amount)
        self.assertEqual(1640000000000000000, diff_msg.bids[0].update_id)
        self.assertEqual(1, len(diff_msg.asks))
        self.assertEqual(4.000002, diff_msg.asks[0].price)
        self.assertEqual(12.0, diff_msg.asks[0].amount)
        self.assertEqual(1640000000000000000, diff_msg.asks[0].update_id)

    def test_trade_message_from_exchange(self):
        trade_update = {
            "product_id": 2,
            "is_taker_buyer": False,
            "timestamp": 1640000000000000000.0,
            "price": "1000000000000000",
            "taker_qty": "100000000000000000000",
        }

        trade_message = VertexOrderBook.trade_message_from_exchange(
            msg=trade_update, metadata={"trading_pair": "COINALPHA-HBOT"}
        )

        self.assertEqual("COINALPHA-HBOT", trade_message.trading_pair)
        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual(1640000000, trade_message.timestamp)
        self.assertEqual(-1, trade_message.update_id)
        self.assertEqual(-1, trade_message.first_update_id)
        self.assertEqual(1640000000000000000, trade_message.trade_id)
