import unittest

from hummingbot.client.command.command_utils import GatewayCommandUtils
from hummingbot.client.command.lp_command_utils import LPCommandUtils
from hummingbot.connector.gateway.gateway_lp import AMMPoolInfo, AMMPositionInfo, CLMMPoolInfo, CLMMPositionInfo


class TestGatewayCommandUtilsLP(unittest.TestCase):
    """Test LP-specific utilities in GatewayCommandUtils"""

    def test_format_pool_info_display_amm(self):
        """Test formatting AMM pool info for display"""
        pool_info = AMMPoolInfo(
            address="0x1234567890abcdef",
            baseTokenAddress="0xabc",
            quoteTokenAddress="0xdef",
            price=1500.0,
            feePct=0.3,
            baseTokenAmount=1000.0,
            quoteTokenAmount=1500000.0
        )

        rows = LPCommandUtils.format_pool_info_display(pool_info, "ETH", "USDC")

        # Check basic properties
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["Property"], "Pool Address")
        self.assertEqual(rows[0]["Value"], "0x1234...cdef")
        self.assertEqual(rows[1]["Property"], "Current Price")
        self.assertEqual(rows[1]["Value"], "1500.000000 USDC/ETH")
        self.assertEqual(rows[2]["Property"], "Fee Tier")
        self.assertEqual(rows[2]["Value"], "0.3%")

    def test_format_pool_info_display_clmm(self):
        """Test formatting CLMM pool info for display"""
        pool_info = CLMMPoolInfo(
            address="0x1234567890abcdef",
            baseTokenAddress="0xabc",
            quoteTokenAddress="0xdef",
            binStep=10,
            feePct=0.05,
            price=1500.0,
            baseTokenAmount=1000.0,
            quoteTokenAmount=1500000.0,
            activeBinId=1000
        )

        rows = LPCommandUtils.format_pool_info_display(pool_info, "ETH", "USDC")

        # Check CLMM-specific properties
        self.assertEqual(len(rows), 7)  # AMM has 5, CLMM has 2 more
        self.assertEqual(rows[5]["Property"], "Active Bin")
        self.assertEqual(rows[5]["Value"], "1000")
        self.assertEqual(rows[6]["Property"], "Bin Step")
        self.assertEqual(rows[6]["Value"], "10")

    def test_format_position_info_display_amm(self):
        """Test formatting AMM position info for display"""
        position = AMMPositionInfo(
            poolAddress="0xpool1234567890",
            walletAddress="0xwallet",
            baseTokenAddress="0xabc",
            quoteTokenAddress="0xdef",
            lpTokenAmount=100.0,
            baseTokenAmount=10.0,
            quoteTokenAmount=15000.0,
            price=1500.0
        )

        rows = LPCommandUtils.format_position_info_display(position)

        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["Property"], "Pool")
        self.assertEqual(rows[0]["Value"], "0xpool...7890")
        self.assertEqual(rows[1]["Property"], "Base Amount")
        self.assertEqual(rows[1]["Value"], "10.000000")
        self.assertEqual(rows[3]["Property"], "LP Tokens")
        self.assertEqual(rows[3]["Value"], "100.000000")

    def test_format_position_info_display_clmm(self):
        """Test formatting CLMM position info for display"""
        position = CLMMPositionInfo(
            address="0xpos1234567890",
            poolAddress="0xpool1234567890",
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

        rows = LPCommandUtils.format_position_info_display(position)

        # Check for position ID (CLMM specific)
        self.assertEqual(rows[0]["Property"], "Position ID")
        self.assertEqual(rows[0]["Value"], "0xpos1...7890")

        # Check for price range
        price_range_row = next(r for r in rows if r["Property"] == "Price Range")
        self.assertEqual(price_range_row["Value"], "1400.000000 - 1600.000000")

        # Check for uncollected fees
        fees_row = next(r for r in rows if r["Property"] == "Uncollected Fees")
        self.assertEqual(fees_row["Value"], "0.100000 / 150.000000")

    def test_format_position_info_display_clmm_no_fees(self):
        """Test CLMM position with no fees doesn't show fees row"""
        position = CLMMPositionInfo(
            address="0xpos123",
            poolAddress="0xpool123",
            baseTokenAddress="0xabc",
            quoteTokenAddress="0xdef",
            baseTokenAmount=10.0,
            quoteTokenAmount=15000.0,
            baseFeeAmount=0.0,
            quoteFeeAmount=0.0,
            lowerBinId=900,
            upperBinId=1100,
            lowerPrice=1400.0,
            upperPrice=1600.0,
            price=1500.0
        )

        rows = LPCommandUtils.format_position_info_display(position)

        # Should not have uncollected fees row
        fees_rows = [r for r in rows if r["Property"] == "Uncollected Fees"]
        self.assertEqual(len(fees_rows), 0)

    def test_format_address_display_integration(self):
        """Test address formatting works correctly in pool/position display"""
        # Short address
        short_addr = "0x123"
        self.assertEqual(GatewayCommandUtils.format_address_display(short_addr), "0x123")

        # Long address
        long_addr = "0x1234567890abcdef1234567890abcdef"
        self.assertEqual(GatewayCommandUtils.format_address_display(long_addr), "0x1234...cdef")

        # Empty address
        self.assertEqual(GatewayCommandUtils.format_address_display(""), "Unknown")

        # None address
        self.assertEqual(GatewayCommandUtils.format_address_display(None), "Unknown")


if __name__ == "__main__":
    unittest.main()
