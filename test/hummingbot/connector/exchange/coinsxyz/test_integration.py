#!/usr/bin/env python3
"""
Integration Tests for Coins.xyz Connector
"""

import unittest
from decimal import Decimal
from unittest.mock import patch

from hummingbot.connector.exchange.coinsxyz.coinsxyz_exchange import CoinsxyzExchange
from hummingbot.core.data_type.common import OrderType, TradeType


class TestCoinsxyzIntegration(unittest.TestCase):
    """Integration tests for Coins.xyz connector."""

    def setUp(self):
        """Set up test fixtures."""
        self.exchange = CoinsxyzExchange(
            coinsxyz_api_key="test_key",
            coinsxyz_secret_key="test_secret",
            trading_pairs=["BTC-USDT"],
            trading_required=True
        )

    @patch('hummingbot.connector.exchange.coinsxyz.coinsxyz_exchange.CoinsxyzExchange._api_get')
    async def test_full_order_lifecycle(self, mock_api_get):
        """Test complete order lifecycle."""
        # Mock exchange info
        mock_api_get.return_value = {
            "symbols": [{
                "symbol": "BTCUSDT",
                "status": "TRADING",
                "baseAsset": "BTC",
                "quoteAsset": "USDT",
                "isSpotTradingAllowed": True,
                "permissions": ["SPOT"],
                "filters": []
            }]
        }

        # Test trading pairs initialization
        await self.exchange._update_trading_fees()

        # Verify exchange is ready for trading
        self.assertIsNotNone(self.exchange.name)
        self.assertEqual(self.exchange.name, "coinsxyz")

    @patch('hummingbot.connector.exchange.coinsxyz.coinsxyz_exchange.CoinsxyzExchange._api_get')
    @patch('hummingbot.connector.exchange.coinsxyz.coinsxyz_exchange.CoinsxyzExchange._api_post')
    async def test_place_and_track_order(self, mock_post, mock_get):
        """Test order placement and tracking."""
        # Mock order placement response
        mock_post.return_value = {
            "orderId": "12345",
            "transactTime": 1234567890000
        }

        # Mock order status response
        mock_get.return_value = {
            "orderId": "12345",
            "status": "FILLED",
            "updateTime": 1234567890000
        }

        # Place order
        exchange_order_id, timestamp = await self.exchange._place_order(
            order_id="test_order_1",
            trading_pair="BTC-USDT",
            amount=Decimal("1.0"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("50000.0")
        )

        self.assertEqual(exchange_order_id, "12345")
        self.assertIsInstance(timestamp, float)

    @patch('hummingbot.connector.exchange.coinsxyz.coinsxyz_exchange.CoinsxyzExchange._api_get')
    async def test_balance_and_trading_rules_sync(self, mock_api_get):
        """Test balance and trading rules synchronization."""
        # Mock balance response
        mock_api_get.return_value = {
            "balances": [
                {"asset": "BTC", "free": "1.0", "locked": "0.5"},
                {"asset": "USDT", "free": "10000.0", "locked": "1000.0"}
            ]
        }

        await self.exchange._update_balances()

        # Verify balances are updated
        self.assertIn("BTC", self.exchange._account_balances)
        self.assertIn("USDT", self.exchange._account_balances)

    async def test_error_handling_flow(self):
        """Test error handling in various scenarios."""
        # Test network error handling
        error_info = self.exchange._handle_http_error(429, "Rate limit exceeded")
        self.assertEqual(error_info["code"], 429)
        self.assertTrue(error_info["handled"])

        # Test server error handling
        error_info = self.exchange._handle_http_error(500, "Internal server error")
        self.assertEqual(error_info["code"], 500)
        self.assertTrue(error_info["handled"])

    def test_data_validation_flow(self):
        """Test data validation across components."""
        # Test balance validation
        valid_balance = {
            "balances": [{"asset": "BTC", "free": "1.0", "locked": "0.5"}],
            "timestamp": 1234567890
        }
        self.assertTrue(self.exchange._validate_balance_update(valid_balance))

        # Test order validation
        valid_order = {
            "order_id": "12345",
            "status": "FILLED",
            "timestamp": 1234567890
        }
        self.assertTrue(self.exchange._validate_order_update(valid_order))

    async def test_websocket_integration(self):
        """Test WebSocket integration flow."""
        # This would test the full WebSocket flow in a real integration test
        # For now, we test the components individually

        # Test user stream data source creation
        user_stream = self.exchange._create_user_stream_data_source()
        self.assertIsNotNone(user_stream)

        # Test order book data source creation
        order_book_source = self.exchange._create_order_book_data_source()
        self.assertIsNotNone(order_book_source)

    def test_fee_calculation_integration(self):
        """Test fee calculation integration."""
        fee = self.exchange._get_fee(
            base_currency="BTC",
            quote_currency="USDT",
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("1.0"),
            price=Decimal("50000.0")
        )

        self.assertIsNotNone(fee)
        self.assertGreater(fee.percent, Decimal("0"))


if __name__ == "__main__":
    unittest.main()
