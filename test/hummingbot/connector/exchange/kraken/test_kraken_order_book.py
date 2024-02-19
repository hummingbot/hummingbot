from unittest import TestCase

from hummingbot.connector.exchange.kraken.kraken_order_book import KrakenOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class KrakenOrderBookTests(TestCase):

    def test_snapshot_message_from_exchange(self):
        snapshot_message = KrakenOrderBook.snapshot_message_from_exchange(
            msg={
                "latest_update": 1,
                "bids": [
                    ["4.00000000", "431.00000000"]
                ],
                "asks": [
                    ["4.00000200", "12.00000000"]
                ]
            },
            timestamp=1640000000.0,
            metadata={"trading_pair": "COINALPHA-HBOT"}
        )

        self.assertEqual("COINALPHA-HBOT", snapshot_message.trading_pair)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual(1640000000.0, snapshot_message.timestamp)
        self.assertEqual(1, snapshot_message.update_id)
        self.assertEqual(-1, snapshot_message.trade_id)
        self.assertEqual(1, len(snapshot_message.bids))
        self.assertEqual(4.0, snapshot_message.bids[0].price)
        self.assertEqual(431.0, snapshot_message.bids[0].amount)
        self.assertEqual(1, snapshot_message.bids[0].update_id)
        self.assertEqual(1, len(snapshot_message.asks))
        self.assertEqual(4.000002, snapshot_message.asks[0].price)
        self.assertEqual(12.0, snapshot_message.asks[0].amount)
        self.assertEqual(1, snapshot_message.asks[0].update_id)

    def test_diff_message_from_exchange(self):
        diff_msg = KrakenOrderBook.diff_message_from_exchange(
            msg={
                "trading_pair": "COINALPHA-HBOT",
                "asks": [
                    [
                        "5541.30000",
                        "2.50700000",
                        "1534614248.123678"
                    ],
                ],
                "bids": [
                    [
                        "5541.20000",
                        "1.52900000",
                        "1534614248.765567"
                    ],
                ],
                "update_id": 3407459756
            },
            timestamp=1640000000,
        )

        self.assertEqual("COINALPHA-HBOT", diff_msg.trading_pair)
        self.assertEqual(1640000000.0, diff_msg.timestamp)
        self.assertEqual(3407459756, diff_msg.update_id)
        self.assertEqual(OrderBookMessageType.DIFF, diff_msg.type)
        self.assertEqual(-1, diff_msg.trade_id)
        self.assertEqual(1, len(diff_msg.bids))
        self.assertEqual(5541.2, diff_msg.bids[0].price)
        self.assertEqual(1.529, diff_msg.bids[0].amount)
        self.assertEqual(1, len(diff_msg.asks))
        self.assertEqual(5541.3, diff_msg.asks[0].price)
        self.assertEqual(2.507, diff_msg.asks[0].amount)

    def test_trade_message_from_exchange(self):
        trade_update = {
            "pair": "COINALPHA-HBOT",
            "trade": [
                "5541.20000",
                "0.15850568",
                "1534614057.321597",
                "s",
                "l",
                ""
            ]
        }

        trade_message = KrakenOrderBook.trade_message_from_exchange(
            msg=trade_update,
            metadata={"trading_pair": "COINALPHA-HBOT"},
        )

        self.assertEqual("COINALPHA-HBOT", trade_message.trading_pair)
        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual(1534614057.321597, trade_message.timestamp)
        self.assertEqual(-1, trade_message.update_id)
        self.assertEqual(1534614057.321597, trade_message.trade_id)
