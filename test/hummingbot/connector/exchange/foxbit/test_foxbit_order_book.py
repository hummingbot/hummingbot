from unittest import TestCase

from hummingbot.connector.exchange.foxbit.foxbit_order_book import FoxbitOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class FoxbitOrderBookTests(TestCase):

    def test_snapshot_message_from_exchange(self):
        snapshot_message = FoxbitOrderBook.snapshot_message_from_exchange(
            msg={
                "instrumentId": "COINALPHA-HBOT",
                "sequence_id": 1,
                "timestamp": 2,
                "bids": [["0.0024", "10"]],
                "asks": [["0.0026", "100"]]
            },
            timestamp=1640000000.0,
            metadata={"trading_pair": "COINALPHA-HBOT"}
        )

        self.assertEqual("COINALPHA-HBOT", snapshot_message.trading_pair)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual(1640000000.0, snapshot_message.timestamp)
        self.assertEqual(1, snapshot_message.update_id)
        self.assertEqual(-1, snapshot_message.first_update_id)
        self.assertEqual(-1, snapshot_message.trade_id)
        self.assertEqual(1, len(snapshot_message.bids))
        self.assertEqual(0.0024, snapshot_message.bids[0].price)
        self.assertEqual(10.0, snapshot_message.bids[0].amount)
        self.assertEqual(1, len(snapshot_message.asks))
        self.assertEqual(0.0026, snapshot_message.asks[0].price)
        self.assertEqual(100.0, snapshot_message.asks[0].amount)

    def test_diff_message_from_exchange(self):
        diff_msg = FoxbitOrderBook.diff_message_from_exchange(
            msg=[2, 0, 1660844469114, 1, 145901, 0, 145890, 1, 10.1, 0],
            timestamp=1640000000.0,
            metadata={"trading_pair": "COINALPHA-HBOT", "first_update_id": 1}
        )

        self.assertEqual("COINALPHA-HBOT", diff_msg.trading_pair)
        self.assertEqual(OrderBookMessageType.DIFF, diff_msg.type)
        self.assertEqual(1660844469114.0, diff_msg.timestamp)
        self.assertEqual(2, diff_msg.update_id)
        self.assertEqual(1, diff_msg.first_update_id)
        self.assertEqual(-1, diff_msg.trade_id)
        self.assertEqual(1, len(diff_msg.bids))
        self.assertEqual(145890.0, diff_msg.bids[0].price)
        self.assertEqual(10.1, diff_msg.bids[0].amount)

    def test_trade_message_from_exchange(self):
        trade_update = [194,
                        4,
                        "0.1",
                        "8432.0",
                        787704,
                        792085,
                        1661952966311,
                        0,
                        0,
                        False,
                        0]

        trade_message = FoxbitOrderBook.trade_message_from_exchange(
            msg=trade_update,
            metadata={"trading_pair": "COINALPHA-HBOT"}
        )

        self.assertEqual("COINALPHA-HBOT", trade_message.trading_pair)
        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual(1661952966.311, trade_message.timestamp)
        self.assertEqual(-1, trade_message.update_id)
        self.assertEqual(-1, trade_message.first_update_id)
        self.assertEqual(194, trade_message.trade_id)
