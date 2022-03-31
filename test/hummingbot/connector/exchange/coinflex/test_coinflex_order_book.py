from unittest import TestCase

from hummingbot.connector.exchange.coinflex.coinflex_order_book import CoinflexOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class CoinflexOrderBookTests(TestCase):

    def test_snapshot_message_from_exchange(self):
        snapshot_message = CoinflexOrderBook.snapshot_message_from_exchange(
            msg={
                "marketCode": "COINALPHA-HBOT",
                "timestamp": 1,
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
        diff_msg = CoinflexOrderBook.diff_message_from_exchange(
            msg={
                "table": "depth",
                "data": [
                    {
                        "instrumentId": "COINALPHA-HBOT",
                        "seqNum": 1,
                        "timestamp": 2,
                        "bids": [
                            [
                                "0.0024",
                                "10"
                            ]
                        ],
                        "asks": [
                            [
                                "0.0026",
                                "100"
                            ]
                        ]
                    }
                ]
            },
            timestamp=1640000000.0,
            metadata={"trading_pair": "COINALPHA-HBOT"}
        )

        self.assertEqual("COINALPHA-HBOT", diff_msg.trading_pair)
        self.assertEqual(OrderBookMessageType.DIFF, diff_msg.type)
        self.assertEqual(1640000000.0, diff_msg.timestamp)
        self.assertEqual(2, diff_msg.update_id)
        self.assertEqual(1, diff_msg.first_update_id)
        self.assertEqual(-1, diff_msg.trade_id)
        self.assertEqual(1, len(diff_msg.bids))
        self.assertEqual(0.0024, diff_msg.bids[0].price)
        self.assertEqual(10.0, diff_msg.bids[0].amount)
        self.assertEqual(2, diff_msg.bids[0].update_id)
        self.assertEqual(1, len(diff_msg.asks))
        self.assertEqual(0.0026, diff_msg.asks[0].price)
        self.assertEqual(100.0, diff_msg.asks[0].amount)
        self.assertEqual(2, diff_msg.asks[0].update_id)

    def test_trade_message_from_exchange(self):
        trade_update = {
            "timestamp": 1234567890123,
            "marketCode": "COINALPHA-HBOT",
            "tradeId": 12345,
            "side": "SELL",
            "price": "0.001",
            "quantity": "100",
        }

        trade_message = CoinflexOrderBook.trade_message_from_exchange(
            msg=trade_update,
            metadata={"trading_pair": "COINALPHA-HBOT"}
        )

        self.assertEqual("COINALPHA-HBOT", trade_message.trading_pair)
        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual(1234567890.123, trade_message.timestamp)
        self.assertEqual(-1, trade_message.update_id)
        self.assertEqual(-1, trade_message.first_update_id)
        self.assertEqual(12345, trade_message.trade_id)
