import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.client.command.gateway_lp_command import GatewayLPCommand
from hummingbot.connector.gateway.common_types import ConnectorType
from hummingbot.connector.gateway.gateway_lp import AMMPoolInfo, AMMPositionInfo, CLMMPoolInfo, CLMMPositionInfo


class GatewayLPCommandTest(unittest.TestCase):
    def setUp(self):
        self.app = MagicMock()
        self.app.notify = MagicMock()
        self.app.prompt = AsyncMock()
        self.app.to_stop_config = False
        self.app.hide_input = False
        self.app.change_prompt = MagicMock()

        # Create command instance with app's attributes
        self.command = type('TestCommand', (GatewayLPCommand,), {
            'notify': self.app.notify,
            'app': self.app,
            'logger': MagicMock(return_value=MagicMock()),
            '_get_gateway_instance': MagicMock(),
            'ev_loop': asyncio.get_event_loop(),
            'placeholder_mode': False,
            'client_config_map': MagicMock()
        })()

    def test_gateway_lp_no_connector(self):
        """Test gateway lp command without connector"""
        self.command.gateway_lp(None, None)

        self.app.notify.assert_any_call("\nError: Connector is required")
        self.app.notify.assert_any_call("Usage: gateway lp <connector> <action>")

    def test_gateway_lp_no_action(self):
        """Test gateway lp command without action"""
        self.command.gateway_lp("uniswap/amm", None)

        self.app.notify.assert_any_call("\nAvailable LP actions:")
        self.app.notify.assert_any_call("  add-liquidity     - Add liquidity to a pool")
        self.app.notify.assert_any_call("  remove-liquidity  - Remove liquidity from a position")
        self.app.notify.assert_any_call("  position-info     - View your liquidity positions")
        self.app.notify.assert_any_call("  collect-fees      - Collect accumulated fees")

    def test_gateway_lp_invalid_action(self):
        """Test gateway lp command with invalid action"""
        self.command.gateway_lp("uniswap/amm", "invalid-action")

        self.app.notify.assert_any_call("\nError: Unknown action 'invalid-action'")
        self.app.notify.assert_any_call("Valid actions: add-liquidity, remove-liquidity, position-info, collect-fees")

    @patch('hummingbot.client.utils.async_utils.safe_ensure_future')
    def test_gateway_lp_valid_actions(self, mock_ensure_future):
        """Test gateway lp command routes to correct handlers"""
        # Test add-liquidity
        self.command.gateway_lp("uniswap/amm", "add-liquidity")
        mock_ensure_future.assert_called_once()

        # Test remove-liquidity
        mock_ensure_future.reset_mock()
        self.command.gateway_lp("uniswap/amm", "remove-liquidity")
        mock_ensure_future.assert_called_once()

        # Test position-info
        mock_ensure_future.reset_mock()
        self.command.gateway_lp("uniswap/amm", "position-info")
        mock_ensure_future.assert_called_once()

        # Test collect-fees
        mock_ensure_future.reset_mock()
        self.command.gateway_lp("uniswap/clmm", "collect-fees")
        mock_ensure_future.assert_called_once()

    def test_display_pool_info_amm(self):
        """Test display of AMM pool information"""
        pool_info = AMMPoolInfo(
            address="0x123",
            baseTokenAddress="0xabc",
            quoteTokenAddress="0xdef",
            price=1500.0,
            feePct=0.3,
            baseTokenAmount=1000.0,
            quoteTokenAmount=1500000.0
        )

        self.command._display_pool_info(pool_info, is_clmm=False)

        self.app.notify.assert_any_call("\n=== Pool Information ===")
        self.app.notify.assert_any_call("Pool Address: 0x123")
        self.app.notify.assert_any_call("Current Price: 1500.000000")
        self.app.notify.assert_any_call("Fee: 0.3%")
        self.app.notify.assert_any_call("\nPool Reserves:")
        self.app.notify.assert_any_call("  Base: 1000.000000")
        self.app.notify.assert_any_call("  Quote: 1500000.000000")

    def test_display_pool_info_clmm(self):
        """Test display of CLMM pool information"""
        pool_info = CLMMPoolInfo(
            address="0x123",
            baseTokenAddress="0xabc",
            quoteTokenAddress="0xdef",
            binStep=10,
            feePct=0.05,
            price=1500.0,
            baseTokenAmount=1000.0,
            quoteTokenAmount=1500000.0,
            activeBinId=1000
        )

        self.command._display_pool_info(pool_info, is_clmm=True)

        self.app.notify.assert_any_call("Active Bin ID: 1000")
        self.app.notify.assert_any_call("Bin Step: 10")

    def test_calculate_removal_amounts(self):
        """Test calculation of removal amounts"""
        position = AMMPositionInfo(
            poolAddress="0x123",
            walletAddress="0xwallet",
            baseTokenAddress="0xabc",
            quoteTokenAddress="0xdef",
            lpTokenAmount=100.0,
            baseTokenAmount=10.0,
            quoteTokenAmount=15000.0,
            price=1500.0,
            base_token="ETH",
            quote_token="USDC"
        )

        # Test 50% removal
        base_amount, quote_amount = self.command._calculate_removal_amounts(position, 50.0)
        self.assertEqual(base_amount, 5.0)
        self.assertEqual(quote_amount, 7500.0)

        # Test 100% removal
        base_amount, quote_amount = self.command._calculate_removal_amounts(position, 100.0)
        self.assertEqual(base_amount, 10.0)
        self.assertEqual(quote_amount, 15000.0)

    def test_format_position_id(self):
        """Test position ID formatting"""
        # Test CLMM position with address
        clmm_position = CLMMPositionInfo(
            address="0x1234567890abcdef",
            poolAddress="0xpool",
            baseTokenAddress="0xabc",
            quoteTokenAddress="0xdef",
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

        formatted = self.command._format_position_id(clmm_position)
        self.assertEqual(formatted, "0x1234...cdef")

        # Test AMM position without address
        amm_position = AMMPositionInfo(
            poolAddress="0xpool1234567890",
            walletAddress="0xwallet",
            baseTokenAddress="0xabc",
            quoteTokenAddress="0xdef",
            lpTokenAmount=100.0,
            baseTokenAmount=10.0,
            quoteTokenAmount=15000.0,
            price=1500.0
        )

        formatted = self.command._format_position_id(amm_position)
        self.assertEqual(formatted, "0xpool...7890")

    def test_calculate_total_fees(self):
        """Test total fees calculation across positions"""
        positions = [
            CLMMPositionInfo(
                address="0x1",
                poolAddress="0xpool1",
                baseTokenAddress="0xabc",
                quoteTokenAddress="0xdef",
                baseTokenAmount=10.0,
                quoteTokenAmount=15000.0,
                baseFeeAmount=0.1,
                quoteFeeAmount=150.0,
                lowerBinId=900,
                upperBinId=1100,
                lowerPrice=1400.0,
                upperPrice=1600.0,
                price=1500.0,
                base_token="ETH",
                quote_token="USDC"
            ),
            CLMMPositionInfo(
                address="0x2",
                poolAddress="0xpool2",
                baseTokenAddress="0xabc",
                quoteTokenAddress="0xdef",
                baseTokenAmount=5.0,
                quoteTokenAmount=7500.0,
                baseFeeAmount=0.05,
                quoteFeeAmount=75.0,
                lowerBinId=950,
                upperBinId=1050,
                lowerPrice=1450.0,
                upperPrice=1550.0,
                price=1500.0,
                base_token="ETH",
                quote_token="USDC"
            )
        ]

        total_fees = self.command._calculate_total_fees(positions)

        self.assertEqual(total_fees["ETH"], 0.15)  # 0.1 + 0.05
        self.assertEqual(total_fees["USDC"], 225.0)  # 150 + 75

    def test_calculate_clmm_pair_amount(self):
        """Test CLMM pair amount calculation"""
        pool_info = CLMMPoolInfo(
            address="0x123",
            baseTokenAddress="0xabc",
            quoteTokenAddress="0xdef",
            binStep=10,
            feePct=0.05,
            price=1500.0,
            baseTokenAmount=1000.0,
            quoteTokenAmount=1500000.0,
            activeBinId=1000
        )

        # Test when price is in range
        quote_amount = self.command._calculate_clmm_pair_amount(
            known_amount=1.0,
            pool_info=pool_info,
            lower_price=1400.0,
            upper_price=1600.0,
            is_base_known=True
        )
        self.assertGreater(quote_amount, 0)

        # Test when price is below range
        quote_amount = self.command._calculate_clmm_pair_amount(
            known_amount=1.0,
            pool_info=pool_info,
            lower_price=1600.0,
            upper_price=1700.0,
            is_base_known=True
        )
        self.assertEqual(quote_amount, 1500.0)  # All quote token

        # Test when price is above range
        quote_amount = self.command._calculate_clmm_pair_amount(
            known_amount=1500.0,
            pool_info=pool_info,
            lower_price=1300.0,
            upper_price=1400.0,
            is_base_known=False
        )
        self.assertEqual(quote_amount, 0)  # All base token

    @patch('hummingbot.connector.gateway.command_utils.GatewayCommandUtils.get_connector_chain_network')
    @patch('hummingbot.connector.gateway.command_utils.GatewayCommandUtils.get_default_wallet')
    async def test_position_info_no_positions(self, mock_wallet, mock_chain_network):
        """Test position info when no positions exist"""
        mock_chain_network.return_value = ("ethereum", "mainnet", None)
        mock_wallet.return_value = ("0xwallet123", None)

        with patch('hummingbot.connector.gateway.gateway_lp.GatewayLp') as MockLP:
            mock_lp = MockLP.return_value
            mock_lp.get_user_positions = AsyncMock(return_value=[])
            mock_lp.start_network = AsyncMock()
            mock_lp.stop_network = AsyncMock()

            await self.command._position_info("uniswap/amm")

            self.app.notify.assert_any_call("\nNo liquidity positions found for this connector")

    @patch('hummingbot.connector.gateway.command_utils.GatewayCommandUtils.get_connector_chain_network')
    @patch('hummingbot.connector.gateway.command_utils.GatewayCommandUtils.get_default_wallet')
    @patch('hummingbot.connector.gateway.common_types.get_connector_type')
    async def test_position_info_with_positions(self, mock_connector_type, mock_wallet, mock_chain_network):
        """Test position info with existing positions"""
        mock_chain_network.return_value = ("ethereum", "mainnet", None)
        mock_wallet.return_value = ("0xwallet123", None)
        mock_connector_type.return_value = ConnectorType.AMM

        positions = [
            AMMPositionInfo(
                poolAddress="0xpool1",
                walletAddress="0xwallet",
                baseTokenAddress="0xabc",
                quoteTokenAddress="0xdef",
                lpTokenAmount=100.0,
                baseTokenAmount=10.0,
                quoteTokenAmount=15000.0,
                price=1500.0,
                base_token="ETH",
                quote_token="USDC"
            )
        ]

        with patch('hummingbot.connector.gateway.gateway_lp.GatewayLp') as MockLP:
            mock_lp = MockLP.return_value
            mock_lp.get_user_positions = AsyncMock(return_value=positions)
            mock_lp.start_network = AsyncMock()
            mock_lp.stop_network = AsyncMock()

            await self.command._position_info("uniswap/amm")

            # Check that positions were displayed
            self.app.notify.assert_any_call("\nTotal Positions: 1")

    @patch('hummingbot.connector.gateway.command_utils.GatewayCommandUtils.get_connector_chain_network')
    async def test_add_liquidity_invalid_connector(self, mock_chain_network):
        """Test add liquidity with invalid connector format"""
        await self.command._add_liquidity("invalid-connector")

        self.app.notify.assert_any_call("Error: Invalid connector format 'invalid-connector'. Use format like 'uniswap/amm'")

    @patch('hummingbot.connector.gateway.command_utils.GatewayCommandUtils.get_connector_chain_network')
    @patch('hummingbot.connector.gateway.common_types.get_connector_type')
    async def test_collect_fees_wrong_connector_type(self, mock_connector_type, mock_chain_network):
        """Test collect fees with non-CLMM connector"""
        mock_chain_network.return_value = ("ethereum", "mainnet", None)
        mock_connector_type.return_value = ConnectorType.AMM

        await self.command._collect_fees("uniswap/amm")

        self.app.notify.assert_any_call("Fee collection is only available for concentrated liquidity positions")

    def test_display_positions_with_fees(self):
        """Test display of positions with uncollected fees"""
        positions = [
            CLMMPositionInfo(
                address="0x123",
                poolAddress="0xpool",
                baseTokenAddress="0xabc",
                quoteTokenAddress="0xdef",
                baseTokenAmount=10.0,
                quoteTokenAmount=15000.0,
                baseFeeAmount=0.1,
                quoteFeeAmount=150.0,
                lowerBinId=900,
                upperBinId=1100,
                lowerPrice=1400.0,
                upperPrice=1600.0,
                price=1500.0,
                base_token="ETH",
                quote_token="USDC"
            )
        ]

        self.command._display_positions_with_fees(positions)

        self.app.notify.assert_any_call("\nPositions with Uncollected Fees:")


if __name__ == "__main__":
    unittest.main()
