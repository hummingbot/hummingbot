from unittest import TestCase

from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_order_book import (
    CoinbaseAdvancedTradeOrderBook,
)
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class CoinbaseAdvancedTradeOrderBookTests(TestCase):

    def test_snapshot_message_from_exchange(self):
        snapshot_message = CoinbaseAdvancedTradeOrderBook.snapshot_message_from_exchange(
            msg=
            {
                "pricebook": {
                    "product_id": "BTC-USD",
                    "bids": [
                        {
                            "price": "4.00000000",
                            "size": "431.00000000"
                        }
                    ],
                    "asks": [
                        {
                            "price": "4.00000200",
                            "size": "12.00000000"
                        }
                    ],
                    "time": "2023-07-11T22:34:09+02:00"
                }
            },
            timestamp=1728378636,
            metadata={"trading_pair": "COINALPHA-HBOT"}
        )

        self.assertEqual("COINALPHA-HBOT", snapshot_message.trading_pair)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual(1728378636, snapshot_message.timestamp)
        self.assertEqual(1689107649, snapshot_message.update_id)
        self.assertEqual(-1, snapshot_message.trade_id)
        self.assertEqual(1, len(snapshot_message.bids))
        self.assertEqual(4.0, snapshot_message.bids[0].price)
        self.assertEqual(431.0, snapshot_message.bids[0].amount)
        self.assertEqual(1689107649, snapshot_message.bids[0].update_id)
        self.assertEqual(1, len(snapshot_message.asks))
        self.assertEqual(4.000002, snapshot_message.asks[0].price)
        self.assertEqual(12.0, snapshot_message.asks[0].amount)
        self.assertEqual(1689107649, snapshot_message.asks[0].update_id)

    def test_diff_message_from_exchange(self):
        diff_msg = CoinbaseAdvancedTradeOrderBook.diff_message_from_exchange(
            msg=
            {
                'channel': 'l2_data',
                'client_id': '',
                'timestamp': '2024-10-08T09:10:36.04370306Z',
                'sequence_num': 9,
                'events': [
                    {
                        'type': 'update',
                        'product_id': 'COINALPHA-HBOT',
                        'updates': [
                            {
                                'side': 'bid',
                                'event_time': '2024-10-08T09:10:34.970831Z',
                                'price_level': '0.0024',
                                'new_quantity': '10'
                            },
                            {
                                'side': 'ask',
                                'event_time': '2024-10-08T09:10:34.970831Z',
                                'price_level': '0.0026',
                                'new_quantity': '100'
                            }
                        ]
                    }
                ]
            },
            timestamp=1728378636,
            metadata={"trading_pair": "COINALPHA-HBOT"}
        )

        self.assertEqual("COINALPHA-HBOT", diff_msg.trading_pair)
        self.assertEqual(OrderBookMessageType.DIFF, diff_msg.type)
        self.assertEqual(1728378636, diff_msg.timestamp)
        self.assertEqual(1728378636, diff_msg.update_id)
        self.assertEqual(1728378636, diff_msg.first_update_id)
        self.assertEqual(-1, diff_msg.trade_id)
        self.assertEqual(1, len(diff_msg.bids))
        self.assertEqual(0.0024, diff_msg.bids[0].price)
        self.assertEqual(10.0, diff_msg.bids[0].amount)
        self.assertEqual(1728378636, diff_msg.bids[0].update_id)
        self.assertEqual(1, len(diff_msg.asks))
        self.assertEqual(0.0026, diff_msg.asks[0].price)
        self.assertEqual(100.0, diff_msg.asks[0].amount)
        self.assertEqual(1728378636, diff_msg.asks[0].update_id)

    def test_trade_message_from_exchange(self):
        trade_update = {
            "channel": "market_trades",
            "client_id": "",
            "timestamp": "2023-02-09T20:19:35.39625135Z",
            "sequence_num": 0,
            "events": [
                {
                    "type": "update",
                    "trades": [
                        {
                            "trade_id": "12345",
                            "product_id": "COINALPHA-HBOT",
                            "price": "1260.01",
                            "size": "0.3",
                            "side": "BUY",
                            "time": "2019-08-14T20:42:27.265Z",
                        }
                    ]
                }
            ]
        }

        trade_message = CoinbaseAdvancedTradeOrderBook.trade_message_from_exchange(
            msg=trade_update,
            metadata={"trading_pair": "COINALPHA-HBOT"}
        )

        self.assertEqual("COINALPHA-HBOT", trade_message.trading_pair)
        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual(1675973975.396251, trade_message.timestamp)
        self.assertEqual(-1, trade_message.update_id)
        self.assertEqual(-1, trade_message.first_update_id)
        self.assertEqual(12345, trade_message.trade_id)
