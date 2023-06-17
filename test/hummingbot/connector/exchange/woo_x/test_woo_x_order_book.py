from unittest import TestCase

from hummingbot.connector.exchange.woo_x.woo_x_order_book import WooXOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class WooXOrderBookTests(TestCase):

    def test_snapshot_message_from_exchange(self):
        snapshot_message = WooXOrderBook.snapshot_message_from_exchange(
            msg={
                "success": True,
                "asks": [
                    {
                        "price": 10669.4,
                        "quantity": 1.56263218
                    },
                ],
                "bids": [
                    {
                        "price": 10669.3,
                        "quantity": 0.88159988
                    },
                ],
                "timestamp": 1564710591905
            },
            timestamp=1564710591905,
            metadata={"trading_pair": "COINALPHA-HBOT"}
        )

        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual(1564710591905, snapshot_message.timestamp)
        self.assertEqual(1564710591905, snapshot_message.update_id)
        self.assertEqual(-1, snapshot_message.trade_id)
        self.assertEqual(1, len(snapshot_message.bids))
        self.assertEqual(10669.3, snapshot_message.bids[0].price)
        self.assertEqual(0.88159988, snapshot_message.bids[0].amount)
        self.assertEqual(1564710591905, snapshot_message.bids[0].update_id)
        self.assertEqual(1, len(snapshot_message.asks))
        self.assertEqual(10669.4, snapshot_message.asks[0].price)
        self.assertEqual(1.56263218, snapshot_message.asks[0].amount)
        self.assertEqual(1564710591905, snapshot_message.asks[0].update_id)

    def test_diff_message_from_exchange(self):
        diff_msg = WooXOrderBook.diff_message_from_exchange(
            msg={
                "topic": "SPOT_BTC_USDT@orderbookupdate",
                "ts": 1618826337580,
                "data": {
                    "symbol": "SPOT_BTC_USDT",
                    "prevTs": 1618826337380,
                    "asks": [
                        [
                            56749.15,
                            3.92864
                        ],
                    ],
                    "bids": [
                        [
                            56745.2,
                            1.03895025
                        ],
                    ]
                }
            },
            metadata={"trading_pair": "BTC-USDT"}
        )

        self.assertEqual(1618826337580, diff_msg.timestamp)
        self.assertEqual(1618826337580, diff_msg.update_id)
        self.assertEqual(1618826337580, diff_msg.first_update_id)
        self.assertEqual(-1, diff_msg.trade_id)
        self.assertEqual(1, len(diff_msg.bids))
        self.assertEqual(56745.2, diff_msg.bids[0].price)
        self.assertEqual(1.03895025, diff_msg.bids[0].amount)
        self.assertEqual(1618826337580, diff_msg.bids[0].update_id)
        self.assertEqual(1, len(diff_msg.asks))
        self.assertEqual(56749.15, diff_msg.asks[0].price)
        self.assertEqual(3.92864, diff_msg.asks[0].amount)
        self.assertEqual(1618826337580, diff_msg.asks[0].update_id)

    def test_trade_message_from_exchange(self):
        trade_update = {
            "topic": "SPOT_ADA_USDT@trade",
            "ts": 1618820361552,
            "data": {
                "symbol": "SPOT_ADA_USDT",
                "price": 1.27988,
                "size": 300,
                "side": "BUY",
                "source": 0
            }
        }

        trade_message = WooXOrderBook.trade_message_from_exchange(
            msg=trade_update,
            metadata={"trading_pair": "ADA-USDT"}
        )

        self.assertEqual("ADA-USDT", trade_message.trading_pair)
        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual(1618820361.552, trade_message.timestamp)
        self.assertEqual(-1, trade_message.update_id)
        self.assertEqual(-1, trade_message.first_update_id)
        self.assertEqual(1618820361552, trade_message.trade_id)
