from unittest import TestCase

from hummingbot.connector.exchange.blockchain_com.blockchain_com_order_book import BlockchainComOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class BlockchainComOrderBookTests(TestCase):

    def test_snapshot_message_from_exchange(self):
        msg = {
            "symbol": "BTC-USD",
            "bids": [
                {
                    "px": 30239.18,
                    "qty": 0.135,
                    "num": 1
                }
            ],
            "asks": [
                {
                    "px": 30258.64,
                    "qty": 1.32193656,
                    "num": 1
                }
            ]
        }
        snapshot_msg = BlockchainComOrderBook.snapshot_message_from_exchange(
            msg=msg,
            metadata={"symbol": msg["symbol"]}
        )
        self.assertEqual(snapshot_msg.trading_pair, msg["symbol"])
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_msg.type)
        self.assertEqual(1, len(snapshot_msg.bids))
        self.assertEqual(4.0, snapshot_msg.bids[0].price)
        self.assertEqual(431.0, snapshot_msg.bids[0].amount)
        self.assertEqual(1, snapshot_msg.bids[0].update_id)
        self.assertEqual(1, len(snapshot_msg.asks))
        self.assertEqual(4.000002, snapshot_msg.asks[0].price)
        self.assertEqual(12.0, snapshot_msg.asks[0].amount)
        self.assertEqual(1, snapshot_msg.asks[0].update_id)
