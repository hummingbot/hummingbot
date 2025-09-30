from unittest import TestCase

from hummingbot.connector.exchange.coinmate.coinmate_order_book import CoinmateOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class CoinmateOrderBookTests(TestCase):

    def test_snapshot_message_from_exchange(self):
        snapshot_message = CoinmateOrderBook.snapshot_message_from_exchange(
            msg={
                "bids": [
                    {"price": "49000.0", "amount": "0.5"},
                    {"price": "48900.0", "amount": "1.0"}
                ],
                "asks": [
                    {"price": "51000.0", "amount": "0.3"},
                    {"price": "51100.0", "amount": "0.8"}
                ]
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

    def test_trade_message_from_exchange(self):
        trade_update = {
            "date": 1234567890000,
            "price": "50000.0",
            "amount": "0.1",
            "type": "BUY",
            "buyOrderId": "12345",
            "sellOrderId": "67890"
        }

        trade_message = CoinmateOrderBook.trade_message_from_exchange(
            msg=trade_update,
            timestamp=1234567890.0,
            metadata={"trading_pair": "BTC-EUR"}
        )

        self.assertEqual("BTC-EUR", trade_message.trading_pair)
        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual(1234567890.0, trade_message.timestamp)
        self.assertEqual(-1, trade_message.update_id)
        self.assertEqual(-1, trade_message.first_update_id)

    def test_snapshot_message_handles_empty_data(self):
        """Test that empty order book (no bids/asks) is handled correctly"""
        snapshot_message = CoinmateOrderBook.snapshot_message_from_exchange(
            msg={
                "bids": [],
                "asks": []
            },
            timestamp=1640000000.0,
            metadata={"trading_pair": "BTC-EUR"}
        )

        self.assertEqual("BTC-EUR", snapshot_message.trading_pair)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual(0, len(snapshot_message.bids))
        self.assertEqual(0, len(snapshot_message.asks))
