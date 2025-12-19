#!/usr/bin/env python3
"""
Unit Tests for Coins.xyz Order Placement
"""

import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.exchange.coinsxyz.coinsxyz_order_placement import CoinsxyzOrderPlacement
from hummingbot.core.data_type.common import TradeType


class TestCoinsxyzOrderPlacement(unittest.TestCase):
    """Unit tests for CoinsxyzOrderPlacement."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_api_factory = MagicMock()
        self.order_placement = CoinsxyzOrderPlacement(api_factory=self.mock_api_factory)

    def test_init(self):
        """Test order placement initialization."""
        self.assertIsNotNone(self.order_placement._api_factory)

    async def test_place_limit_order(self):
        """Test limit order placement."""
        self.api_client.place_order = AsyncMock(return_value={
            "orderId": "12345",
            "transactTime": 1234567890000
        })

        result = await self.order_placement.place_limit_order(
            symbol="BTCUSDT",
            side=TradeType.BUY,
            quantity=Decimal("1.0"),
            price=Decimal("50000.0"),
            client_order_id="test_order_1"
        )

        self.assertEqual(result["orderId"], "12345")
        self.api_client.place_order.assert_called_once()

    async def test_place_market_order(self):
        """Test market order placement."""
        self.api_client.place_order = AsyncMock(return_value={
            "orderId": "12346",
            "transactTime": 1234567890000
        })

        result = await self.order_placement.place_market_order(
            symbol="BTCUSDT",
            side=TradeType.SELL,
            quantity=Decimal("0.5"),
            client_order_id="test_order_2"
        )

        self.assertEqual(result["orderId"], "12346")

    async def test_cancel_order(self):
        """Test order cancellation."""
        self.api_client.cancel_order = AsyncMock(return_value={
            "orderId": "12345",
            "status": "CANCELED"
        })

        result = await self.order_placement.cancel_order(
            symbol="BTCUSDT",
            order_id="12345"
        )

        self.assertEqual(result["status"], "CANCELED")

    def test_validate_order_params(self):
        """Test order parameter validation."""
        # Valid params
        valid_params = {
            "symbol": "BTCUSDT",
            "quantity": Decimal("1.0"),
            "price": Decimal("50000.0")
        }
        self.assertTrue(self.order_placement._validate_order_params(valid_params))

        # Invalid params
        invalid_params = {
            "symbol": "",
            "quantity": Decimal("0"),
            "price": Decimal("-1")
        }
        self.assertFalse(self.order_placement._validate_order_params(invalid_params))

    def test_format_order_request(self):
        """Test order request formatting."""
        params = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "LIMIT",
            "quantity": "1.0",
            "price": "50000.0"
        }

        formatted = self.order_placement._format_order_request(params)

        self.assertIn("symbol", formatted)
        self.assertEqual(formatted["symbol"], "BTCUSDT")


if __name__ == "__main__":
    unittest.main()
