from unittest import TestCase

from hummingbot.connector.exchange.hyperliquid.hyperliquid_order_book import HyperliquidOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class HyperliquidOrderBookTests(TestCase):

    def test_snapshot_message_from_exchange(self):
        snapshot_message = HyperliquidOrderBook.snapshot_message_from_exchange(
            msg={
                "coin": "COINALPHA/USDC", "levels": [
                    [
                        {'px': '2080.3', 'sz': '74.6923', 'n': 2}
                    ],
                    [
                        {'px': '2080.5', 'sz': '73.018', 'n': 2}
                    ]
                ],
                "time": 1700687397643
            },
            timestamp=1700687397643,
            metadata={"trading_pair": "COINALPHA-USDC"}
        )

        self.assertEqual("COINALPHA-USDC", snapshot_message.trading_pair)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual(1700687397643, snapshot_message.timestamp)
        self.assertEqual(1700687397643, snapshot_message.update_id)
        self.assertEqual(-1, snapshot_message.trade_id)
        self.assertEqual(1, len(snapshot_message.bids))
        self.assertEqual(2080.3, snapshot_message.bids[0].price)
        self.assertEqual(74.6923, snapshot_message.bids[0].amount)
        self.assertEqual(1700687397643, snapshot_message.bids[0].update_id)
        self.assertEqual(1, len(snapshot_message.asks))
        self.assertEqual(2080.5, snapshot_message.asks[0].price)
        self.assertEqual(73.018, snapshot_message.asks[0].amount)
        self.assertEqual(1700687397643, snapshot_message.asks[0].update_id)

    def test_diff_message_from_exchange(self):
        diff_msg = HyperliquidOrderBook.diff_message_from_exchange(
            msg= {
                'coin': 'COINALPHA/USDC', 'time': 1700687397642, 'levels': [
                    [{'px': '2080.3', 'sz': '74.6923', 'n': 2}, {'px': '2080.0', 'sz': '162.2829', 'n': 2},
                     {'px': '1825.5', 'sz': '0.0259', 'n': 1}, {'px': '1823.6', 'sz': '0.0259', 'n': 1}],
                    [{'px': '2080.5', 'sz': '73.018', 'n': 2}, {'px': '2080.6', 'sz': '74.6799', 'n': 2},
                     {'px': '2118.9', 'sz': '377.495', 'n': 1}, {'px': '2122.1', 'sz': '348.8644', 'n': 1}]
                ]
            },
            timestamp=11700687397642,
            metadata={"trading_pair": "COINALPHA-USDC"}
        )

        self.assertEqual("COINALPHA-USDC", diff_msg.trading_pair)
        self.assertEqual(OrderBookMessageType.DIFF, diff_msg.type)
        self.assertEqual(11700687397642.0, diff_msg.timestamp)
        self.assertEqual(1700687397642, diff_msg.update_id)
        self.assertEqual(1700687397642, diff_msg.first_update_id)
        self.assertEqual(-1, diff_msg.trade_id)
        # self.assertEqual(4, len(diff_msg.bids))
        # self.assertEqual(2080.3, diff_msg.bids[0].price)
        # self.assertEqual(74.6923, diff_msg.bids[0].amount)
        self.assertEqual(1700687397642, diff_msg.bids[0].update_id)
        # self.assertEqual(4, len(diff_msg.asks))
        # self.assertEqual(2080.5, diff_msg.asks[0].price)
        # self.assertEqual(73.018, diff_msg.asks[0].amount)
        self.assertEqual(1700687397642, diff_msg.asks[0].update_id)

    def test_trade_message_from_exchange(self):
        trade_update = {
            'coin': 'COINALPHA/USDC',
            'side': 'A',
            'px': '2009.0',
            'sz': '0.0079',
            'time': 1701156061468,
            'hash': '0x3e2bc327cc925903cebe0408315a98010b002fda921d23fd1468bbb5d573f902'}  # noqa: mock
        trade_message = HyperliquidOrderBook.trade_message_from_exchange(
            msg=trade_update,
            metadata={"trading_pair": "COINALPHA-USDC"}
        )

        self.assertEqual("COINALPHA-USDC", trade_message.trading_pair)
        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual(1701156061.468, trade_message.timestamp)
        self.assertEqual(-1, trade_message.update_id)
        self.assertEqual(-1, trade_message.first_update_id)
        self.assertEqual("0x3e2bc327cc925903cebe0408315a98010b002fda921d23fd1468bbb5d573f902", trade_message.trade_id)  # noqa: mock
