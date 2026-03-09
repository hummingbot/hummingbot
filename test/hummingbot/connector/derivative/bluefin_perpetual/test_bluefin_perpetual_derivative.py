import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_derivative import BluefinPerpetualDerivative
from hummingbot.core.data_type.common import OrderType, PositionMode, TradeType


# Valid BIP-39 test mnemonic (12 words)
TEST_MNEMONIC = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"


class BluefinPerpetualDerivativeTests(IsolatedAsyncioWrapperTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.trading_pair = "BTC-USD"

    def setUp(self) -> None:
        super().setUp()

        with patch("hummingbot.connector.derivative.bluefin_perpetual.data_sources.bluefin_data_source.BluefinDataSource"):
            self.connector = BluefinPerpetualDerivative(
                bluefin_perpetual_wallet_mnemonic=TEST_MNEMONIC,
                trading_pairs=[self.trading_pair],
                trading_required=False,
            )

    def test_supported_order_types_includes_limit_maker(self):
        """Test that LIMIT_MAKER is in supported order types."""
        supported = self.connector.supported_order_types()

        self.assertIn(OrderType.LIMIT, supported)
        self.assertIn(OrderType.MARKET, supported)
        self.assertIn(OrderType.LIMIT_MAKER, supported)

    def test_supported_position_modes_oneway_only(self):
        """Test that only ONEWAY position mode is supported."""
        supported = self.connector.supported_position_modes()

        self.assertEqual([PositionMode.ONEWAY], supported)

    def test_get_collateral_token_returns_usdc(self):
        """Test that collateral token is USDC for all pairs."""
        buy_collateral = self.connector.get_buy_collateral_token(self.trading_pair)
        sell_collateral = self.connector.get_sell_collateral_token(self.trading_pair)

        self.assertEqual("USDC", buy_collateral)
        self.assertEqual("USDC", sell_collateral)

    @patch("hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_derivative.Order")
    @patch("hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_derivative.BluefinOrderType")
    async def test_place_order_limit_maker_sets_post_only(self, mock_order_type, mock_order):
        """Test that LIMIT_MAKER orders set post_only flag."""
        # Setup mocks
        mock_order_type.LIMIT = "LIMIT"
        mock_order_instance = MagicMock()
        mock_order.return_value = mock_order_instance

        # Mock data source
        self.connector._data_source = MagicMock()
        self.connector._data_source.to_e9 = lambda x: int(Decimal(str(x)) * Decimal("1e9"))
        self.connector._data_source.place_order = AsyncMock(
            return_value=MagicMock(order_hash="test_hash_123")
        )

        # Mock quantize methods
        self.connector.quantize_order_price = MagicMock(return_value=Decimal("50000"))
        self.connector.quantize_order_amount = MagicMock(return_value=Decimal("1"))

        # Place LIMIT_MAKER order
        order_id = "test_order_123"
        trading_pair = self.trading_pair
        amount = Decimal("1")
        price = Decimal("50000")

        result = await self.connector._place_order(
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT_MAKER,
            price=price,
        )

        # Verify order was created with post_only=True
        mock_order.assert_called_once()
        call_kwargs = mock_order.call_args.kwargs
        self.assertTrue(call_kwargs.get("post_only"), "LIMIT_MAKER order should have post_only=True")

        # Verify result
        self.assertEqual("test_hash_123", result[0])

    @patch("hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_derivative.Order")
    @patch("hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_derivative.BluefinOrderType")
    async def test_place_order_limit_does_not_set_post_only(self, mock_order_type, mock_order):
        """Test that regular LIMIT orders do not set post_only flag."""
        # Setup mocks
        mock_order_type.LIMIT = "LIMIT"
        mock_order_instance = MagicMock()
        mock_order.return_value = mock_order_instance

        # Mock data source
        self.connector._data_source = MagicMock()
        self.connector._data_source.to_e9 = lambda x: int(Decimal(str(x)) * Decimal("1e9"))
        self.connector._data_source.place_order = AsyncMock(
            return_value=MagicMock(order_hash="test_hash_456")
        )

        # Mock quantize methods
        self.connector.quantize_order_price = MagicMock(return_value=Decimal("50000"))
        self.connector.quantize_order_amount = MagicMock(return_value=Decimal("1"))

        # Place regular LIMIT order
        order_id = "test_order_456"
        trading_pair = self.trading_pair
        amount = Decimal("1")
        price = Decimal("50000")

        result = await self.connector._place_order(
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=price,
        )

        # Verify order was created with post_only=False
        mock_order.assert_called_once()
        call_kwargs = mock_order.call_args.kwargs
        self.assertFalse(call_kwargs.get("post_only"), "Regular LIMIT order should have post_only=False")

        # Verify result
        self.assertEqual("test_hash_456", result[0])

    @patch("hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_derivative.asyncio.sleep", new_callable=AsyncMock)
    async def test_place_order_retries_on_failure(self, mock_sleep):
        """Test that place_order retries on transient failures."""
        # Mock data source that fails twice then succeeds
        self.connector._data_source = MagicMock()
        self.connector._data_source.to_e9 = lambda x: int(Decimal(str(x)) * Decimal("1e9"))
        self.connector._data_source.place_order = AsyncMock(
            side_effect=[
                Exception("Network error"),
                Exception("Temporary failure"),
                MagicMock(order_hash="success_hash"),
            ]
        )

        # Mock quantize methods
        self.connector.quantize_order_price = MagicMock(return_value=Decimal("50000"))
        self.connector.quantize_order_amount = MagicMock(return_value=Decimal("1"))

        # Place order
        with patch("hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_derivative.Order"):
            with patch("hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_derivative.BluefinOrderType"):
                result = await self.connector._place_order(
                    order_id="test_retry",
                    trading_pair=self.trading_pair,
                    amount=Decimal("1"),
                    trade_type=TradeType.BUY,
                    order_type=OrderType.LIMIT,
                    price=Decimal("50000"),
                )

        # Verify it retried and eventually succeeded
        self.assertEqual(3, self.connector._data_source.place_order.await_count)
        self.assertEqual("success_hash", result[0])

        # Verify sleep was called for retries (2 retries = 2 sleeps)
        self.assertEqual(2, mock_sleep.await_count)
