from unittest import TestCase

from hummingbot.connector.exchange.polkadex.polkadex_order_book import PolkadexOrderbook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class PolkadexOrderbookTests(TestCase):
    def test_snapshot_message_from_exchange(self):
        snapshot_message = PolkadexOrderbook.snapshot_message_from_exchange(
            msgs=[
                {
                    "price": "2",
                    "qty": "1.10",
                    "side": "Ask"
                },
                {
                    "price": "2.20",
                    "qty": "1",
                    "side": "Ask"
                },
                {
                    "price": "1",
                    "qty": "1",
                    "side": "Bid"
                }
            ],
            timestamp=1640000000.0,
            metadata={"trading_pair": "PDEX-100"}
        )

        self.assertEqual("PDEX-100", snapshot_message.trading_pair)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual(1640000000.0, snapshot_message.timestamp)
        self.assertEqual(-1, snapshot_message.update_id)
        self.assertEqual(-1, snapshot_message.trade_id)
        self.assertEqual(1, len(snapshot_message.bids))
        self.assertEqual(1.0, snapshot_message.bids[0].price)
        self.assertEqual(1.0, snapshot_message.bids[0].amount)
        self.assertEqual(-1, snapshot_message.bids[0].update_id)
        self.assertEqual(2, len(snapshot_message.asks))
        self.assertEqual(2.0, snapshot_message.asks[0].price)
        self.assertEqual(1.10, snapshot_message.asks[0].amount)
        self.assertEqual(-1, snapshot_message.asks[0].update_id)

    def test_diff_message_from_exchange(self):
        snapshot_message = PolkadexOrderbook.diff_message_from_exchange(
            msg={"m": "PDEX-100",
                 "seq": "1",
                 "puts": [{"price": "1", "qty": "1", "side": "Bid"},
                          {"price": "2", "qty": "1.10", "side": "Ask"},
                          {"price": "2.20", "qty": "1", "side": "Ask"}],
                 "dels": [{"price": "2.20", "qty": "0.00000000", "side": "Bid"}]
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

    def test_trade_message_from_exchange(self):
        trade_update = {"price": "10",
                        "quantity": "0.80",
                        "market": "PDEX-100",
                        "time": 1656918186316}

        trade_message = PolkadexOrderbook.trade_message_from_exchange(
            msg=trade_update,
            metadata={"trading_pair": "PDEX-100"}
        )

        self.assertEqual("PDEX-100", trade_message.trading_pair)
        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual(1656918186.316, trade_message.timestamp)
        self.assertEqual(-1, trade_message.update_id)
        self.assertEqual(-1, trade_message.first_update_id)
        # self.assertEqual(12345, trade_message.trade_id)
