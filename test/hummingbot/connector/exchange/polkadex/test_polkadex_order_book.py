from unittest import TestCase

from hummingbot.connector.exchange.polkadex.polkadex_order_book import PolkadexOrderbook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class PolkadexOrderbookUnitTests(TestCase):
    def test_snapshot_message_from_exchange(self):
        msg = [{'p': '10000000000000', 'q': '20000000000000', 's': 'Ask'},
               {'p': '13000000000000', 'q': '3000000000000', 's': 'Ask'},
               {'p': '6000000000000', 'q': '10000000000000', 's': 'Ask'},
               {'p': '7380000000000', 'q': '60000000000000', 's': 'Ask'},
               {'p': '7440000000000', 'q': '65000000000000', 's': 'Ask'},
               {'p': '7480000000000', 'q': '55000000000000', 's': 'Ask'},
               {'p': '7600000000000', 'q': '88000000000000', 's': 'Ask'},
               {'p': '7800000000000', 'q': '57000000000000', 's': 'Ask'},
               {'p': '8000000000000', 'q': '56696428571429', 's': 'Ask'},
               {'p': '8300000000000', 'q': '105000000000000', 's': 'Ask'},
               {'p': '8500000000000', 'q': '95000000000000', 's': 'Ask'},
               {'p': '1000000000000', 'q': '7000000000000', 's': 'Bid'},
               {'p': '200000000000', 'q': '5000000000000', 's': 'Bid'}]
        snapshot_message = PolkadexOrderbook.snapshot_message_from_exchange(msg, timestamp=1.0,
                                                                            metadata={"trading_pair": "PDEX-BTC"})

    def test_diff_message_from_exchange(self):
        snapshot_message = PolkadexOrderbook.diff_message_from_exchange(msg={'side': 'Ask', 'price': '11.11', 'qty': '10.1', 'id': 263, 'market': 'PDEX-1'})

    def test_trade_message_from_exchange(self):
        snapshot_message = PolkadexOrderbook.trade_message_from_exchange(
            msg={"m": "PDEX-1", "p": 1000000000000, "q": 1000000000000, "tid": 20, "t": 1661927828000})

    def test_trade_message_from_exchange_containing_metadata(self):
        snapshot_message = PolkadexOrderbook.trade_message_from_exchange(
            msg={"m": "PDEX-1", "p": 1000000000000, "q": 1000000000000, "tid": 20, "t": 1661927828000},
            metadata={"market": "PDEX-1"})

    def test_diff_message_from_exchange_containing_metadata(self):
        resp = {'side': 'Ask', 'price': '11.11', 'qty': '10.1', 'id': 263, 'market': 'PDEX-1'}
        snapshot_message = PolkadexOrderbook.diff_message_from_exchange(msg=resp, metadata={"market": "PDEX-1"})

    def test_diff_message_from_exchange_containing_asks(self):
        resp = {'side': 'Ask', 'price': '11.11', 'qty': '10.1', 'id': 263, 'market': 'PDEX-1'}
        snapshot_message = PolkadexOrderbook.diff_message_from_exchange(msg=resp, metadata={"market": "PDEX-1"})
        # self.assertEqual(1,0)

    def test_diff_message_from_exchange_containing_qty_0(self):
        resp = {'side': 'Ask', 'price': '0', 'qty': '0', 'id': 263, 'market': 'PDEX-1'}
        snapshot_message = PolkadexOrderbook.diff_message_from_exchange(msg=resp, metadata={"market": "PDEX-1"})

    def test_diff_message_from_exchange_containing_no_side(self):
        resp = {'side': '', 'price': '0', 'qty': '0', 'id': 263, 'market': 'PDEX-1'}
        snapshot_message = PolkadexOrderbook.diff_message_from_exchange(msg=resp, metadata={"market": "PDEX-1"})

    def test_diff_message_from_exchange_containing_bids(self):
        resp = {'side': 'Bid', 'price': '11.11', 'qty': '10.1', 'id': 263, 'market': 'PDEX-1'}
        snapshot_message = PolkadexOrderbook.diff_message_from_exchange(msg=resp, metadata={"market": "PDEX-1"})
        # self.assertEqual(1,0)

    """ def test_diff_message_from_exchange_containing_asks_and_bids_2(self):
        resp = {
            "data": {
                "websocket_streams": {
                    "data": "[{\"side\":\"As\",\"price\":2000000000000,\"qty\":1000000000000,\"seq\":3}]",
                    "name": "PDEX-1-ob-inc"
                }
            }
        }
        snapshot_message = PolkadexOrderbook.diff_message_from_exchange(msg=resp["data"], metadata={"market": "PDEX-1"})
        # self.assertEqual(1,0) """