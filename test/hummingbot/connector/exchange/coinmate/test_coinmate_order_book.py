from unittest import TestCase

from hummingbot.connector.exchange.coinmate.coinmate_order_book import CoinmateOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class CoinmateOrderBookTests(TestCase):

    def test_snapshot_message_from_exchange(self):
        snapshot_message = CoinmateOrderBook.snapshot_message_from_exchange(
            msg={
                "error": False,
                "errorMessage": None,
                "data": {
                    "bids": [
                        {"price": "49000.0", "amount": "0.5"},
                        {"price": "48900.0", "amount": "1.0"}
                    ],
                    "asks": [
                        {"price": "51000.0", "amount": "0.3"},
                        {"price": "51100.0", "amount": "0.8"}
                    ]
                }
            },
            timestamp=1640000000.0,
            metadata={"trading_pair": "BTC-EUR"}
        )

        self.assertEqual("BTC-EUR", snapshot_message.trading_pair)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual(1640000000.0, snapshot_message.timestamp)
        self.assertEqual(-1, snapshot_message.update_id)
        self.assertEqual(-1, snapshot_message.trade_id)
        self.assertEqual(2, len(snapshot_message.bids))
        self.assertEqual(49000.0, snapshot_message.bids[0].price)
        self.assertEqual(0.5, snapshot_message.bids[0].amount)
        self.assertEqual(48900.0, snapshot_message.bids[1].price)
        self.assertEqual(1.0, snapshot_message.bids[1].amount)
        self.assertEqual(2, len(snapshot_message.asks))
        self.assertEqual(51000.0, snapshot_message.asks[0].price)
        self.assertEqual(0.3, snapshot_message.asks[0].amount)
        self.assertEqual(51100.0, snapshot_message.asks[1].price)
        self.assertEqual(0.8, snapshot_message.asks[1].amount)

    def test_diff_message_from_exchange(self):
        diff_msg = CoinmateOrderBook.diff_message_from_exchange(
            msg={
                "event": "data",
                "channel": "order_book-BTC_EUR",
                "payload": {
                    "bids": [
                        {"price": "49500.0", "amount": "0.2"}
                    ],
                    "asks": [
                        {"price": "50500.0", "amount": "0.4"}
                    ]
                }
            },
            timestamp=1640000000.0,
            metadata={"trading_pair": "BTC-EUR"}
        )

        self.assertEqual("BTC-EUR", diff_msg.trading_pair)
        self.assertEqual(OrderBookMessageType.DIFF, diff_msg.type)
        self.assertEqual(1640000000.0, diff_msg.timestamp)
        self.assertEqual(-1, diff_msg.update_id)
        self.assertEqual(-1, diff_msg.first_update_id)
        self.assertEqual(-1, diff_msg.trade_id)
        self.assertEqual(1, len(diff_msg.bids))
        self.assertEqual(49500.0, diff_msg.bids[0].price)
        self.assertEqual(0.2, diff_msg.bids[0].amount)
        self.assertEqual(1, len(diff_msg.asks))
        self.assertEqual(50500.0, diff_msg.asks[0].price)
        self.assertEqual(0.4, diff_msg.asks[0].amount)

    def test_trade_message_from_exchange(self):
        trade_update = {
            "event": "data",
            "channel": "trades-BTC_EUR",
            "payload": {
                "date": 1234567890000,
                "price": "50000.0",
                "amount": "0.1",
                "type": "BUY",
                "buyOrderId": "12345",
                "sellOrderId": "67890"
            }
        }

        trade_message = CoinmateOrderBook.trade_message_from_exchange(
            msg=trade_update,
            metadata={"trading_pair": "BTC-EUR"}
        )

        self.assertEqual("BTC-EUR", trade_message.trading_pair)
        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual(1234567890.0, trade_message.timestamp)
        self.assertEqual(-1, trade_message.update_id)
        self.assertEqual(-1, trade_message.first_update_id)
        self.assertEqual("12345", trade_message.content["buyOrderId"])
        self.assertEqual("67890", trade_message.content["sellOrderId"])

    def test_snapshot_message_handles_empty_data(self):
        snapshot_message = CoinmateOrderBook.snapshot_message_from_exchange(
            msg={
                "error": False,
                "errorMessage": None,
                "data": {
                    "bids": [],
                    "asks": []
                }
            },
            timestamp=1640000000.0,
            metadata={"trading_pair": "BTC-EUR"}
        )

        self.assertEqual("BTC-EUR", snapshot_message.trading_pair)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual(0, len(snapshot_message.bids))
        self.assertEqual(0, len(snapshot_message.asks))

    def test_diff_message_handles_empty_updates(self):
        diff_msg = CoinmateOrderBook.diff_message_from_exchange(
            msg={
                "event": "data",
                "channel": "order_book-BTC_EUR",
                "payload": {
                    "bids": [],
                    "asks": []
                }
            },
            timestamp=1640000000.0,
            metadata={"trading_pair": "BTC-EUR"}
        )

        self.assertEqual("BTC-EUR", diff_msg.trading_pair)
        self.assertEqual(OrderBookMessageType.DIFF, diff_msg.type)
        self.assertEqual(0, len(diff_msg.bids))
        self.assertEqual(0, len(diff_msg.asks))
