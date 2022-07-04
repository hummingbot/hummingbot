import asyncio
import time
import unittest

from hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_order_book import FtxPerpetualOrderBook


class FtxPerpetualOrderBookUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.order_book = FtxPerpetualOrderBook()

    def setUp(self) -> None:
        super().setUp()

    def test_trade_message_from_exchange(self):
        msg = {
            "time": "2021-12-25T01:00:00.123456+00:00",
            "market": "COINALPHA-PERP",
            "side": "sell",
            "id": "1",
            "price": 100,
            "size": 13.22
        }
        message = self.order_book.trade_message_from_exchange(msg)
        self.assertEqual(message.content['trading_pair'], "COINALPHA-USD")

    def test_restful_snapshot_message(self):
        msg = {
            "trading_pair": "COINALPHA-USD",
            "result": {
                "bids": [[10, 1]],
                "asks": [[20, 2]]
            }
        }
        message = self.order_book.restful_snapshot_message_from_exchange(msg, time.time())
        self.assertEqual(message.content['trading_pair'], "COINALPHA-USD")
