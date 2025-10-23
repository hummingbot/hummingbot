#!/usr/bin/env python3
"""
Unit Tests for Coins.xyz Exchange Connector
"""

import asyncio
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from hummingbot.connector.exchange.coinsxyz.coinsxyz_exchange import CoinsxyzExchange
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState


class TestCoinsxyzExchange(unittest.TestCase):
    """Unit tests for CoinsxyzExchange."""

    def setUp(self):
        """Set up test fixtures."""
        # Create event loop for tests
        self.ev_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.ev_loop)
        
        self.api_key = "test_api_key"
        self.secret_key = "test_secret_key"
        self.trading_pairs = ["BTC-USDT", "ETH-USDT"]

        self.exchange = CoinsxyzExchange(
            coinsxyz_api_key=self.api_key,
            coinsxyz_secret_key=self.secret_key,
            trading_pairs=self.trading_pairs,
            trading_required=True
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        if hasattr(self, 'ev_loop') and self.ev_loop:
            self.ev_loop.close()

    def test_init(self):
        """Test exchange initialization."""
        self.assertEqual(self.exchange.api_key, self.api_key)
        self.assertEqual(self.exchange.secret_key, self.secret_key)
        self.assertEqual(self.exchange._trading_pairs, self.trading_pairs)

    def test_name(self):
        """Test exchange name."""
        self.assertEqual(self.exchange.name, "coinsxyz")

    def test_display_name(self):
        """Test display name."""
        self.assertEqual(self.exchange.display_name, "coinsxyz")

    def test_supported_order_types(self):
        """Test supported order types."""
        order_types = self.exchange.supported_order_types()
        self.assertIn(OrderType.LIMIT, order_types)
        self.assertIn(OrderType.MARKET, order_types)

    @patch('hummingbot.connector.exchange.coinsxyz.coinsxyz_exchange.CoinsxyzExchange._api_post')
    async def test_place_order(self, mock_api_post):
        """Test order placement."""
        mock_api_post.return_value = {
            "orderId": "12345",
            "transactTime": 1234567890000
        }

        order_id = "test_order_1"
        trading_pair = "BTC-USDT"
        amount = Decimal("1.0")
        price = Decimal("50000.0")

        exchange_order_id, timestamp = await self.exchange._place_order(
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=price
        )

        self.assertEqual(exchange_order_id, "12345")
        self.assertIsInstance(timestamp, float)
        mock_api_post.assert_called_once()

    @patch('hummingbot.connector.exchange.coinsxyz.coinsxyz_exchange.CoinsxyzExchange._api_delete')
    async def test_place_cancel(self, mock_api_delete):
        """Test order cancellation."""
        mock_api_delete.return_value = {"status": "CANCELED"}

        tracked_order = MagicMock(spec=InFlightOrder)
        tracked_order.trading_pair = "BTC-USDT"
        tracked_order.client_order_id = "test_order_1"

        await self.exchange._place_cancel("test_order_1", tracked_order)

        mock_api_delete.assert_called_once()

    @patch('hummingbot.connector.exchange.coinsxyz.coinsxyz_exchange.CoinsxyzExchange._api_get')
    async def test_update_balances(self, mock_api_get):
        """Test balance updates."""
        mock_api_get.return_value = {
            "balances": [
                {"asset": "BTC", "free": "1.0", "locked": "0.5"},
                {"asset": "USDT", "free": "10000.0", "locked": "1000.0"}
            ]
        }

        await self.exchange._update_balances()

        self.assertIn("BTC", self.exchange._account_balances)
        self.assertIn("USDT", self.exchange._account_balances)
        self.assertEqual(self.exchange._account_balances["BTC"], Decimal("1.5"))
        self.assertEqual(self.exchange._account_available_balances["BTC"], Decimal("1.0"))

    @patch('hummingbot.connector.exchange.coinsxyz.coinsxyz_exchange.CoinsxyzExchange._api_get')
    async def test_request_order_status(self, mock_api_get):
        """Test order status request."""
        mock_api_get.return_value = {
            "orderId": "12345",
            "status": "FILLED",
            "updateTime": 1234567890000
        }

        tracked_order = MagicMock(spec=InFlightOrder)
        tracked_order.trading_pair = "BTC-USDT"
        tracked_order.client_order_id = "test_order_1"

        order_update = await self.exchange._request_order_status(tracked_order)

        self.assertEqual(order_update.exchange_order_id, "12345")
        self.assertEqual(order_update.new_state, OrderState.FILLED)

    def test_validate_balance_update(self):
        """Test balance update validation."""
        valid_data = {
            "balances": [{"asset": "BTC", "free": "1.0", "locked": "0.5"}],
            "timestamp": 1234567890
        }
        self.assertTrue(self.exchange._validate_balance_update(valid_data))

        invalid_data = {"invalid": "data"}
        self.assertFalse(self.exchange._validate_balance_update(invalid_data))

    def test_validate_order_update(self):
        """Test order update validation."""
        valid_data = {
            "order_id": "12345",
            "status": "FILLED",
            "timestamp": 1234567890
        }
        self.assertTrue(self.exchange._validate_order_update(valid_data))

        invalid_data = {"order_id": "12345"}
        self.assertFalse(self.exchange._validate_order_update(invalid_data))

    def test_validate_trade_update(self):
        """Test trade update validation."""
        valid_data = {
            "trade_id": "67890",
            "order_id": "12345",
            "quantity": "1.0",
            "price": "50000.0",
            "timestamp": 1234567890
        }
        self.assertTrue(self.exchange._validate_trade_update(valid_data))

        invalid_data = {"trade_id": "67890"}
        self.assertFalse(self.exchange._validate_trade_update(invalid_data))


if __name__ == "__main__":
    unittest.main()
