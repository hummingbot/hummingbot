import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.gateway.common_types import ConnectorType
from hummingbot.connector.gateway.gateway_lp import (
    AMMPoolInfo,
    AMMPositionInfo,
    CLMMPoolInfo,
    CLMMPositionInfo,
    GatewayLp,
)
from hummingbot.core.data_type.common import TradeType


class GatewayLpTest(unittest.TestCase):
    def setUp(self):
        self.client_config_map = MagicMock()
        self.connector = GatewayLp(
            connector_name="uniswap/amm",
            chain="ethereum",
            network="mainnet",
            address="0xwallet123",
            trading_pairs=["ETH-USDC"]
        )
        self.connector._gateway_instance = MagicMock()

    @patch('hummingbot.connector.gateway.gateway_lp.get_connector_type')
    async def test_get_pool_info_amm(self, mock_connector_type):
        """Test getting AMM pool info"""
        mock_connector_type.return_value = ConnectorType.AMM

        mock_response = {
            "address": "0xpool123",
            "baseTokenAddress": "0xeth",
            "quoteTokenAddress": "0xusdc",
            "price": 1500.0,
            "feePct": 0.3,
            "baseTokenAmount": 1000.0,
            "quoteTokenAmount": 1500000.0
        }

        self.connector._get_gateway_instance().pool_info = AsyncMock(return_value=mock_response)

        pool_info = await self.connector.get_pool_info("ETH-USDC")

        self.assertIsInstance(pool_info, AMMPoolInfo)
        self.assertEqual(pool_info.address, "0xpool123")
        self.assertEqual(pool_info.price, 1500.0)
        self.assertEqual(pool_info.fee_pct, 0.3)

    @patch('hummingbot.connector.gateway.gateway_lp.get_connector_type')
    async def test_get_pool_info_clmm(self, mock_connector_type):
        """Test getting CLMM pool info"""
        mock_connector_type.return_value = ConnectorType.CLMM

        mock_response = {
            "address": "0xpool123",
            "baseTokenAddress": "0xeth",
            "quoteTokenAddress": "0xusdc",
            "binStep": 10,
            "feePct": 0.05,
            "price": 1500.0,
            "baseTokenAmount": 1000.0,
            "quoteTokenAmount": 1500000.0,
            "activeBinId": 1000
        }

        self.connector._get_gateway_instance().pool_info = AsyncMock(return_value=mock_response)

        pool_info = await self.connector.get_pool_info("ETH-USDC")

        self.assertIsInstance(pool_info, CLMMPoolInfo)
        self.assertEqual(pool_info.bin_step, 10)
        self.assertEqual(pool_info.active_bin_id, 1000)

    @patch('hummingbot.connector.gateway.gateway_lp.get_connector_type')
    async def test_get_user_positions_amm(self, mock_connector_type):
        """Test getting user positions for AMM"""
        mock_connector_type.return_value = ConnectorType.AMM

        # Test without pool address - should return empty list
        positions = await self.connector.get_user_positions()
        self.assertEqual(len(positions), 0)

        # Test with pool address
        pool_response = {
            "baseToken": "ETH",
            "quoteToken": "USDC"
        }

        position_response = {
            "poolAddress": "0xpool1",
            "walletAddress": "0xwallet123",
            "baseTokenAddress": "0xeth",
            "quoteTokenAddress": "0xusdc",
            "lpTokenAmount": 100.0,
            "baseTokenAmount": 10.0,
            "quoteTokenAmount": 15000.0,
            "price": 1500.0
        }

        self.connector._get_gateway_instance().pool_info = AsyncMock(return_value=pool_response)
        self.connector._get_gateway_instance().amm_position_info = AsyncMock(return_value=position_response)

        positions = await self.connector.get_user_positions(pool_address="0xpool1")

        self.assertEqual(len(positions), 1)
        self.assertIsInstance(positions[0], AMMPositionInfo)
        self.assertEqual(positions[0].lp_token_amount, 100.0)
        self.assertEqual(positions[0].base_token, "ETH")
        self.assertEqual(positions[0].quote_token, "USDC")

    @patch('hummingbot.connector.gateway.gateway_lp.get_connector_type')
    async def test_get_user_positions_clmm(self, mock_connector_type):
        """Test getting user positions for CLMM"""
        mock_connector_type.return_value = ConnectorType.CLMM

        mock_response = {
            "positions": [
                {
                    "address": "0xpos123",
                    "poolAddress": "0xpool1",
                    "baseTokenAddress": "0xeth",
                    "quoteTokenAddress": "0xusdc",
                    "baseTokenAmount": 10.0,
                    "quoteTokenAmount": 15000.0,
                    "baseFeeAmount": 0.1,
                    "quoteFeeAmount": 150.0,
                    "lowerBinId": 900,
                    "upperBinId": 1100,
                    "lowerPrice": 1400.0,
                    "upperPrice": 1600.0,
                    "price": 1500.0
                }
            ]
        }

        self.connector._get_gateway_instance().clmm_positions_owned = AsyncMock(return_value=mock_response)
        self.connector.get_token_info = MagicMock(side_effect=[
            {"symbol": "ETH"},
            {"symbol": "USDC"}
        ])

        positions = await self.connector.get_user_positions()

        self.assertEqual(len(positions), 1)
        self.assertIsInstance(positions[0], CLMMPositionInfo)
        self.assertEqual(positions[0].base_fee_amount, 0.1)
        self.assertEqual(positions[0].quote_fee_amount, 150.0)

    def test_add_liquidity_amm(self):
        """Test adding liquidity to AMM pool"""
        with patch('hummingbot.connector.gateway.gateway_lp.get_connector_type') as mock_connector_type:
            mock_connector_type.return_value = ConnectorType.AMM

            with patch('hummingbot.connector.gateway.gateway_lp.safe_ensure_future') as mock_ensure_future:
                order_id = self.connector.add_liquidity(
                    trading_pair="ETH-USDC",
                    price=1500.0,
                    base_token_amount=1.0,
                    quote_token_amount=1500.0
                )

                self.assertTrue(order_id.startswith("range-ETH-USDC-"))
                mock_ensure_future.assert_called_once()

    def test_add_liquidity_clmm(self):
        """Test adding liquidity to CLMM pool"""
        with patch('hummingbot.connector.gateway.gateway_lp.get_connector_type') as mock_connector_type:
            mock_connector_type.return_value = ConnectorType.CLMM

            with patch('hummingbot.connector.gateway.gateway_lp.safe_ensure_future') as mock_ensure_future:
                order_id = self.connector.add_liquidity(
                    trading_pair="ETH-USDC",
                    price=1500.0,
                    spread_pct=10.0,
                    base_token_amount=1.0,
                    quote_token_amount=1500.0
                )

                self.assertTrue(order_id.startswith("range-ETH-USDC-"))
                mock_ensure_future.assert_called_once()

    @patch('hummingbot.connector.gateway.gateway_lp.get_connector_type')
    def test_remove_liquidity_clmm_no_address(self, mock_connector_type):
        """Test removing liquidity from CLMM position without address raises error"""
        mock_connector_type.return_value = ConnectorType.CLMM

        with self.assertRaises(ValueError) as context:
            self.connector.remove_liquidity(
                trading_pair="ETH-USDC",
                position_address=None
            )

        self.assertIn("position_address is required", str(context.exception))

    @patch('hummingbot.connector.gateway.gateway_lp.get_connector_type')
    async def test_get_position_info_clmm(self, mock_connector_type):
        """Test getting specific position info for CLMM"""
        mock_connector_type.return_value = ConnectorType.CLMM

        mock_response = {
            "address": "0xpos123",
            "poolAddress": "0xpool1",
            "baseTokenAddress": "0xeth",
            "quoteTokenAddress": "0xusdc",
            "baseTokenAmount": 10.0,
            "quoteTokenAmount": 15000.0,
            "baseFeeAmount": 0.1,
            "quoteFeeAmount": 150.0,
            "lowerBinId": 900,
            "upperBinId": 1100,
            "lowerPrice": 1400.0,
            "upperPrice": 1600.0,
            "price": 1500.0
        }

        self.connector._get_gateway_instance().clmm_position_info = AsyncMock(return_value=mock_response)

        position_info = await self.connector.get_position_info("ETH-USDC", "0xpos123")

        self.assertIsInstance(position_info, CLMMPositionInfo)
        self.assertEqual(position_info.address, "0xpos123")

    @patch('hummingbot.connector.gateway.gateway_lp.get_connector_type')
    async def test_clmm_open_position_execution(self, mock_connector_type):
        """Test CLMM open position execution"""
        mock_connector_type.return_value = ConnectorType.CLMM

        mock_response = {
            "signature": "0xtx123",
            "fee": 0.001
        }

        self.connector._get_gateway_instance().clmm_open_position = AsyncMock(return_value=mock_response)
        self.connector.start_tracking_order = MagicMock()
        self.connector.update_order_from_hash = MagicMock()

        await self.connector._clmm_add_liquidity(
            trade_type=TradeType.RANGE,
            order_id="test-order-123",
            trading_pair="ETH-USDC",
            price=1500.0,
            spread_pct=10.0,
            base_token_amount=1.0,
            quote_token_amount=1500.0
        )

        self.connector.start_tracking_order.assert_called_once()
        self.connector.update_order_from_hash.assert_called_once_with(
            "test-order-123", "ETH-USDC", "0xtx123", mock_response
        )

    async def test_get_user_positions_error_handling(self):
        """Test error handling in get_user_positions"""
        self.connector._get_gateway_instance().clmm_positions_owned = AsyncMock(
            side_effect=Exception("API Error")
        )

        positions = await self.connector.get_user_positions()

        self.assertEqual(positions, [])

    def test_position_models_validation(self):
        """Test Pydantic model validation"""
        # Test valid AMM position
        amm_pos = AMMPositionInfo(
            poolAddress="0xpool",
            walletAddress="0xwallet",
            baseTokenAddress="0xbase",
            quoteTokenAddress="0xquote",
            lpTokenAmount=100.0,
            baseTokenAmount=10.0,
            quoteTokenAmount=15000.0,
            price=1500.0
        )
        self.assertEqual(amm_pos.pool_address, "0xpool")

        # Test valid CLMM position
        clmm_pos = CLMMPositionInfo(
            address="0xpos",
            poolAddress="0xpool",
            baseTokenAddress="0xbase",
            quoteTokenAddress="0xquote",
            baseTokenAmount=10.0,
            quoteTokenAmount=15000.0,
            baseFeeAmount=0.1,
            quoteFeeAmount=150.0,
            lowerBinId=900,
            upperBinId=1100,
            lowerPrice=1400.0,
            upperPrice=1600.0,
            price=1500.0
        )
        self.assertEqual(clmm_pos.address, "0xpos")


if __name__ == "__main__":
    unittest.main()
