import time
import unittest

from hummingbot.connector.exchange.blockchain_com.blockchain_com_order_book_message import BlockchainComOrderBookMessage
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.core.data_type.order_book_row import OrderBookRow


class BlockchainComOrderBookMessageTests(unittest.TestCase):

    def test_update_id(self):
        update_id = 1655136958.6535852

        msg = BlockchainComOrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={"update_id": update_id},
            timestamp=time.time(),
        )
        self.assertEqual(update_id, msg.update_id)

        msg = BlockchainComOrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={"update_id": update_id},
            timestamp=time.time(),
        )
        self.assertEqual(update_id, msg.update_id)

        msg = BlockchainComOrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content={"someKey": "someValue"},
            timestamp=time.time(),
        )
        self.assertEqual(-1, msg.update_id)

    def test_bids_and_asks(self):
        update_id = 1655136958.6535852
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

        msg = BlockchainComOrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": msg["symbol"],
                "update_id": update_id,
                "bids": msg["bids"],
                "asks": msg["asks"]
            },
            timestamp=time.time(),
        )
        asks = msg.asks
        self.assertEqual(1, len(asks))
        self.assertTrue(isinstance(asks[0], OrderBookRow))
        self.assertEqual(30258.64, asks[0].price)
        self.assertEqual(1, asks[0].amount)
        self.assertEqual(update_id, asks[0].update_id)

        bids = msg.bids
        self.assertEqual(1, len(bids))
        self.assertTrue(isinstance(bids[0], OrderBookRow))
        self.assertEqual(30239.18, bids[0].price)
        self.assertEqual(1, bids[0].amount)
        self.assertEqual(update_id, bids[0].update_id)
