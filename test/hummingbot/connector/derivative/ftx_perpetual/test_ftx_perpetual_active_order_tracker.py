import asyncio
import time
import unittest
from decimal import Decimal

from hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_active_order_tracker import (
    FtxPerpetualActiveOrderTracker,
)
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class FtxPerpetualActiveOrderTrackerUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.active_order_tracker = FtxPerpetualActiveOrderTracker()
        cls.trading_pair = "COINALPHA-USD"

    def setUp(self) -> None:
        super().setUp()

    def test_convert_snapshot_message(self):
        timestamp = time.time()
        bids = [[1, 2], [2, 3]]
        asks = [[3, 4], [4, 5]]
        msg = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": self.trading_pair,
            "update_id": timestamp,
            "bids": bids,
            "asks": asks
        })
        bids_row, asks_row = self.active_order_tracker.convert_snapshot_message_to_order_book_row(msg)
        self.assertEqual(bids_row[0].price, Decimal('1.0'))
        self.assertEqual(asks_row[1].amount, Decimal('5.0'))

    def test_convert_diff_message(self):
        timestamp = time.time()
        bids = [[1, 2], [2, 3]]
        asks = [[3, 4], [4, 5]]
        msg = OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": self.trading_pair,
            "update_id": timestamp,
            "bids": bids,
            "asks": asks
        })
        bids_row, asks_row = self.active_order_tracker.convert_diff_message_to_order_book_row(msg)
        self.assertEqual(bids_row[0].price, Decimal('1.0'))
        self.assertEqual(asks_row[1].amount, Decimal('5.0'))
