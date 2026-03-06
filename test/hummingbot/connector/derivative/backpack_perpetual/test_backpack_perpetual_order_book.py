from unittest import TestCase

from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_order_book import BackpackPerpetualOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class BackpackPerpetualOrderBookTests(TestCase):

    def test_snapshot_message_from_exchange(self):
        snapshot_message = BackpackPerpetualOrderBook.snapshot_message_from_exchange(
            msg={
                "lastUpdateId": 1,
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
        diff_msg = BackpackPerpetualOrderBook.diff_message_from_exchange(
            msg={
                "stream": "depth.COINALPHA_HBOT",
                "data": {
                    "e": "depth",
                    "E": 123456789,
                    "s": "COINALPHA_HBOT",
                    "U": 1,
                    "u": 2,
                    "b": [
                        [
                            "0.0024",
                            "10"
                        ]
                    ],
                    "a": [
                        [
                            "0.0026",
                            "100"
                        ]
                    ]
                }
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
            "stream": "trade.COINALPHA_HBOT",
            "data": {
                "e": "trade",
                "E": 1234567890123,
                "s": "COINALPHA_HBOT",
                "t": 12345,
                "p": "0.001",
                "q": "100",
                "b": 88,
                "a": 50,
                "T": 123456785,
                "m": True,
                "M": True
            }
        }

        trade_message = BackpackPerpetualOrderBook.trade_message_from_exchange(
            msg=trade_update,
            metadata={"trading_pair": "COINALPHA-HBOT"}
        )

        self.assertEqual("COINALPHA-HBOT", trade_message.trading_pair)
        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual(1234567890.123, trade_message.timestamp)
        self.assertEqual(-1, trade_message.update_id)
        self.assertEqual(-1, trade_message.first_update_id)
        self.assertEqual(12345, trade_message.trade_id)

    def test_diff_message_with_empty_bids_and_asks(self):
        """Test diff message handling when bids and asks are empty"""
        diff_msg = BackpackPerpetualOrderBook.diff_message_from_exchange(
            msg={
                "stream": "depth.SOL_USDC",
                "data": {
                    "e": "depth",
                    "E": 1768426666739979,
                    "s": "SOL_USDC",
                    "U": 3396117473,
                    "u": 3396117473,
                    "b": [],
                    "a": []
                }
            },
            timestamp=1640000000.0,
            metadata={"trading_pair": "SOL-USDC"}
        )

        self.assertEqual("SOL-USDC", diff_msg.trading_pair)
        self.assertEqual(OrderBookMessageType.DIFF, diff_msg.type)
        self.assertEqual(0, len(diff_msg.bids))
        self.assertEqual(0, len(diff_msg.asks))

    def test_diff_message_with_multiple_price_levels(self):
        """Test diff message with multiple bid and ask levels"""
        diff_msg = BackpackPerpetualOrderBook.diff_message_from_exchange(
            msg={
                "stream": "depth.BTC_USDC",
                "data": {
                    "e": "depth",
                    "E": 1768426666739979,
                    "s": "BTC_USDC",
                    "U": 100,
                    "u": 105,
                    "b": [
                        ["50000.00", "1.5"],
                        ["49999.99", "2.0"],
                        ["49999.98", "0.5"]
                    ],
                    "a": [
                        ["50001.00", "1.0"],
                        ["50002.00", "2.5"]
                    ]
                }
            },
            timestamp=1640000000.0,
            metadata={"trading_pair": "BTC-USDC"}
        )

        self.assertEqual(3, len(diff_msg.bids))
        self.assertEqual(2, len(diff_msg.asks))
        self.assertEqual(50000.00, diff_msg.bids[0].price)
        self.assertEqual(1.5, diff_msg.bids[0].amount)

    def test_snapshot_message_with_empty_order_book(self):
        """Test snapshot message when order book is empty"""
        snapshot_message = BackpackPerpetualOrderBook.snapshot_message_from_exchange(
            msg={
                "lastUpdateId": 12345,
                "bids": [],
                "asks": []
            },
            timestamp=1640000000.0,
            metadata={"trading_pair": "ETH-USDC"}
        )

        self.assertEqual("ETH-USDC", snapshot_message.trading_pair)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual(0, len(snapshot_message.bids))
        self.assertEqual(0, len(snapshot_message.asks))
        self.assertEqual(12345, snapshot_message.update_id)

    def test_trade_message_sell_side(self):
        """Test trade message for sell side (maker=True)"""
        trade_update = {
            "stream": "trade.SOL_USDC",
            "data": {
                "e": "trade",
                "E": 1234567890123,
                "s": "SOL_USDC",
                "t": 99999,
                "p": "150.50",
                "q": "25.5",
                "b": 100,
                "a": 200,
                "T": 123456785,
                "m": True,
                "M": True
            }
        }

        trade_message = BackpackPerpetualOrderBook.trade_message_from_exchange(
            msg=trade_update,
            metadata={"trading_pair": "SOL-USDC"}
        )

        self.assertEqual("SOL-USDC", trade_message.trading_pair)
        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual(99999, trade_message.trade_id)

    def test_trade_message_buy_side(self):
        """Test trade message for buy side (maker=False)"""
        trade_update = {
            "stream": "trade.ETH_USDC",
            "data": {
                "e": "trade",
                "E": 9876543210123,
                "s": "ETH_USDC",
                "t": 11111,
                "p": "2500.00",
                "q": "0.5",
                "b": 300,
                "a": 400,
                "T": 987654321,
                "m": False,
                "M": False
            }
        }

        trade_message = BackpackPerpetualOrderBook.trade_message_from_exchange(
            msg=trade_update,
            metadata={"trading_pair": "ETH-USDC"}
        )

        self.assertEqual("ETH-USDC", trade_message.trading_pair)
        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual(11111, trade_message.trade_id)

    def test_snapshot_with_multiple_price_levels(self):
        """Test snapshot with realistic order book depth"""
        snapshot_message = BackpackPerpetualOrderBook.snapshot_message_from_exchange(
            msg={
                "lastUpdateId": 999999,
                "bids": [
                    ["100.00", "10.0"],
                    ["99.99", "20.0"],
                    ["99.98", "30.0"],
                    ["99.97", "15.0"],
                    ["99.96", "5.0"]
                ],
                "asks": [
                    ["100.01", "12.0"],
                    ["100.02", "18.0"],
                    ["100.03", "25.0"]
                ]
            },
            timestamp=1640000000.0,
            metadata={"trading_pair": "BTC-USDC"}
        )

        self.assertEqual(5, len(snapshot_message.bids))
        self.assertEqual(3, len(snapshot_message.asks))
        self.assertEqual(100.00, snapshot_message.bids[0].price)
        self.assertEqual(10.0, snapshot_message.bids[0].amount)
        self.assertEqual(100.01, snapshot_message.asks[0].price)
