from unittest import TestCase

from hummingbot.connector.exchange.tegro.tegro_order_book import TegroOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class TegroOrderBookTests(TestCase):

    def test_snapshot_message_from_exchange(self):
        snapshot_message = TegroOrderBook.snapshot_message_from_exchange(
            msg={
                "timestamp": 1708817206,
                "asks": [
                    {
                        "price": 6097.00,
                        "quantity": 1600,
                    },
                ],
                "bids": [
                    {
                        "price": 712,
                        "quantity": 5000,
                    },

                ]
            },
            timestamp=1640000000.0,
            metadata={"trading_pair": "KRYPTONITE-USDT"}
        )

        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual(1640000000, snapshot_message.timestamp)
        self.assertEqual(1708817206, snapshot_message.update_id)
        self.assertEqual(-1, snapshot_message.trade_id)
        self.assertEqual(1, len(snapshot_message.bids))
        self.assertEqual(712.0, snapshot_message.bids[0].price)
        self.assertEqual(5000.0, snapshot_message.bids[0].amount)
        self.assertEqual(1708817206, snapshot_message.bids[0].update_id)
        self.assertEqual(1, len(snapshot_message.asks))
        self.assertEqual(6097.0, snapshot_message.asks[0].price)
        self.assertEqual(1600, snapshot_message.asks[0].amount)
        self.assertEqual(1708817206, snapshot_message.asks[0].update_id)

    def test_diff_message_from_exchange(self):
        diff_msg = TegroOrderBook.diff_message_from_exchange(
            msg={
                "action": "order_book_diff",
                "data": {
                    "timestamp": 1708817206,
                    "symbol": "KRYPTONITE_USDT",
                    "bids": [
                        {
                            "price": 6097.00,
                            "quantity": 1600,
                        },
                    ],
                    "asks": [
                        {
                            "price": 712,
                            "quantity": 5000,
                        },
                    ]
                }},
            timestamp=1640000000000,
            metadata={"trading_pair": "KRYPTONITE-USDT"}
        )

        self.assertEqual(1708817206, diff_msg.update_id)
        self.assertEqual(1640000000.0, diff_msg.timestamp)
        self.assertEqual(-1, diff_msg.trade_id)
        self.assertEqual(1, len(diff_msg.bids))
        self.assertEqual(6097.00, diff_msg.bids[0].price)
        self.assertEqual(1600, diff_msg.bids[0].amount)
        self.assertEqual(1708817206, diff_msg.bids[0].update_id)
        self.assertEqual(1, len(diff_msg.asks))
        self.assertEqual(712, diff_msg.asks[0].price)
        self.assertEqual(5000, diff_msg.asks[0].amount)
        self.assertEqual(1708817206, diff_msg.asks[0].update_id)

    def test_trade_message_from_exchange(self):
        trade_update = {
            "action": "trade_updated",
            "data": {
                "amount": 573,
                "id": "68a22415-3f6b-4d27-8996-1cbf71d89e5f",
                "is_buyer_maker": True,
                "marketId": "11155420_0xcf9eb56c69ddd4f9cfdef880c828de7ab06b4614_0x7bda2a5ee22fe43bc1ab2bcba97f7f9504645c08",
                "price": 0.1,
                "state": "success",
                "symbol": "KRYPTONITE_USDT",
                "taker": "0x0a0cdc90cc16a0f3e67c296c8c0f7207cbdc0f4e",
                "timestamp": 1708817206,
                "txHash": "0x2f0d41ced1c7d21fe114235dfe363722f5f7026c21441f181ea39768a151c205",  # noqa: mock
            }
        }

        trade_message = TegroOrderBook.trade_message_from_exchange(
            msg=trade_update,
            metadata={"trading_pair": "KRYPTONITE-USDT"},
            timestamp=1661927587836
        )

        self.assertEqual("KRYPTONITE_USDT", trade_message.trading_pair)
        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual(1661927587.836, trade_message.timestamp)
        self.assertEqual(-1, trade_message.update_id)
        self.assertEqual(-1, trade_message.first_update_id)
        self.assertEqual("68a22415-3f6b-4d27-8996-1cbf71d89e5f", trade_message.trade_id)
