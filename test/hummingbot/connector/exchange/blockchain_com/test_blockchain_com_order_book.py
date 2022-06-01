from unittest import TestCase
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessageType,
)
from hummingbot.connector.exchange.blockchain_com.blockchain_com_order_book import BlockchainComOrderBook

class BlockchainComOrderBookTests(TestCase):

    def test_snapshot_message_from_exchange(self):
        msg= {
            "symbol": "BTC-USD",
    "bids": [
    {
      "px": 30239.18,
      "qty": 0.135,
      "num": 1
    },
    ],
  "asks": [
    {
      "px": 30258.64,
      "qty": 1.32193656,
      "num": 1
    },
  ]
        }
        snapshot_msg = BlockchainComOrderBook.snapshot_message_from_exchange(
            msg=msg,
            metadata=msg["symbol"]
        )

