import unittest
from decimal import Decimal

from hummingbot.connector.exchange.backpack.backpack_order_book import BackpackOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class TestBackpackOrderBook(unittest.TestCase):
    """Test suite for Backpack order book message parsing."""

    def test_snapshot_message_from_exchange(self):
        """Test parsing order book snapshot from exchange format."""
        snapshot_data = {
            "asks": [
                ["43001.00", "1.5"],
                ["43002.00", "2.0"],
                ["43003.00", "0.5"],
            ],
            "bids": [
                ["43000.00", "1.0"],
                ["42999.00", "2.5"],
                ["42998.00", "3.0"],
            ],
            "lastUpdateId": 12345,
        }

        timestamp = 1234567890.123
        metadata = {"trading_pair": "BTC-USDC"}

        message = BackpackOrderBook.snapshot_message_from_exchange(
            msg=snapshot_data,
            timestamp=timestamp,
            metadata=metadata,
        )

        self.assertEqual(OrderBookMessageType.SNAPSHOT, message.type)
        self.assertEqual("BTC-USDC", message.trading_pair)
        self.assertEqual(timestamp, message.timestamp)

        # Verify asks from content dict
        asks = message.content["asks"]
        self.assertEqual(3, len(asks))
        self.assertEqual(43001.00, asks[0][0])  # price
        self.assertEqual(1.5, asks[0][1])  # quantity

        # Verify bids from content dict
        bids = message.content["bids"]
        self.assertEqual(3, len(bids))
        self.assertEqual(43000.00, bids[0][0])  # price
        self.assertEqual(1.0, bids[0][1])  # quantity

    def test_diff_message_from_exchange(self):
        """Test parsing order book diff update from exchange format."""
        diff_data = {
            "stream": "depth.BTC_USDC",
            "data": {
                "a": [
                    ["43001.00", "0.0"],  # Remove ask at this price
                    ["43005.00", "1.0"],  # Add new ask
                ],
                "b": [
                    ["42999.00", "3.0"],  # Update bid
                ],
                "T": 1234567890123000,  # Microseconds
            },
        }

        timestamp = 1234567890.123
        metadata = {"trading_pair": "BTC-USDC"}

        message = BackpackOrderBook.diff_message_from_exchange(
            msg=diff_data,
            timestamp=timestamp,
            metadata=metadata,
        )

        self.assertEqual(OrderBookMessageType.DIFF, message.type)
        self.assertEqual("BTC-USDC", message.trading_pair)

        # Verify asks from content dict
        asks = message.content["asks"]
        self.assertEqual(2, len(asks))
        # Removal (amount = 0)
        self.assertEqual(43001.00, asks[0][0])
        self.assertEqual(0.0, asks[0][1])
        # Addition
        self.assertEqual(43005.00, asks[1][0])
        self.assertEqual(1.0, asks[1][1])

        # Verify bids from content dict
        bids = message.content["bids"]
        self.assertEqual(1, len(bids))
        self.assertEqual(42999.00, bids[0][0])
        self.assertEqual(3.0, bids[0][1])

    def test_trade_message_from_exchange(self):
        """Test parsing trade message from exchange format."""
        trade_data = {
            "p": "43000.50",  # Price
            "q": "0.5",  # Quantity
            "m": True,  # Is buyer maker
            "T": 1234567890123000,  # Timestamp in microseconds
            "t": 98765,  # Trade ID
        }

        metadata = {"trading_pair": "BTC-USDC"}

        message = BackpackOrderBook.trade_message_from_exchange(
            msg=trade_data,
            metadata=metadata,
        )

        self.assertEqual(OrderBookMessageType.TRADE, message.type)
        self.assertEqual("BTC-USDC", message.trading_pair)
        self.assertEqual(43000.50, message.content["price"])
        self.assertEqual(0.5, message.content["amount"])

    def test_trade_message_with_alternative_format(self):
        """Test parsing trade with alternative field names."""
        trade_data = {
            "price": "43000.50",
            "quantity": "0.5",
            "isBuyerMaker": True,
            "timestamp": 1234567890123,  # Milliseconds
            "id": 98765,
        }

        metadata = {"trading_pair": "BTC-USDC"}

        message = BackpackOrderBook.trade_message_from_exchange(
            msg=trade_data,
            metadata=metadata,
        )

        self.assertEqual(OrderBookMessageType.TRADE, message.type)
        self.assertEqual(43000.50, message.content["price"])
        self.assertEqual(0.5, message.content["amount"])

    def test_snapshot_with_empty_sides(self):
        """Test snapshot handles empty order book sides."""
        snapshot_data = {
            "asks": [],
            "bids": [],
            "lastUpdateId": 12345,
        }

        timestamp = 1234567890.123
        metadata = {"trading_pair": "BTC-USDC"}

        message = BackpackOrderBook.snapshot_message_from_exchange(
            msg=snapshot_data,
            timestamp=timestamp,
            metadata=metadata,
        )

        self.assertEqual(0, len(message.content["asks"]))
        self.assertEqual(0, len(message.content["bids"]))

    def test_diff_with_nested_data(self):
        """Test diff message handles nested data structure."""
        diff_data = {
            "stream": "depth.BTC_USDC",
            "data": {
                "asks": [["43001.00", "1.0"]],
                "bids": [["42999.00", "2.0"]],
                "T": 1234567890123000,
            },
        }

        timestamp = 1234567890.123
        metadata = {"trading_pair": "BTC-USDC"}

        message = BackpackOrderBook.diff_message_from_exchange(
            msg=diff_data,
            timestamp=timestamp,
            metadata=metadata,
        )

        self.assertEqual(OrderBookMessageType.DIFF, message.type)
        self.assertEqual(1, len(message.content["asks"]))
        self.assertEqual(1, len(message.content["bids"]))

    def test_parse_orders_with_dict_entries(self):
        orders = [
            {"price": "100", "quantity": "1.5"},
            {"px": "101", "sz": "2"},
        ]
        parsed = BackpackOrderBook._parse_orders(orders)
        self.assertEqual([[100.0, 1.5], [101.0, 2.0]], parsed)


if __name__ == "__main__":
    unittest.main()
