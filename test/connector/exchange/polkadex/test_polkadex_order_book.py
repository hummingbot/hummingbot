from unittest import TestCase

from hummingbot.connector.exchange.polkadex.polkadex_order_book import PolkadexOrderbook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class PolkadexOrderbookTests(TestCase):

    def test_diff_message_from_exchange(self):
        snapshot_message = PolkadexOrderbook.diff_message_from_exchange(
            msg={"m":"PDEX-100",
        "seq":"1",
        "puts": [{"price":"1","qty":"1","side":"Bid"},
                 {"price":"2","qty":"1.10","side":"Ask"},
                 {"price":"2.20","qty":"1","side":"Ask"}],
        "dels":[{"price":"2.20","qty":"0.00000000","side":"Bid"}]
        },
            timestamp=1640000000.0,
            metadata={"trading_pair": "PDEX-100"}
        )

        self.assertEqual("PDEX-100", snapshot_message.trading_pair)
        self.assertEqual(OrderBookMessageType.DIFF, snapshot_message.type)
        self.assertEqual(1640000000.0, snapshot_message.timestamp)
        self.assertEqual(1, snapshot_message.update_id)
        self.assertEqual(-1, snapshot_message.trade_id)
        self.assertEqual(2, len(snapshot_message.bids))
        self.assertEqual(1.0, snapshot_message.bids[0].price)
        self.assertEqual(1.0, snapshot_message.bids[0].amount)
        self.assertEqual(1, snapshot_message.bids[0].update_id)
        self.assertEqual(2, len(snapshot_message.asks))
        self.assertEqual(2.0, snapshot_message.asks[0].price)
        self.assertEqual(1.10, snapshot_message.asks[0].amount)
        self.assertEqual(1, snapshot_message.asks[0].update_id)
