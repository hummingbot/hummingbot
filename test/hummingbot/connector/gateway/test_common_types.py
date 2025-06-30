import unittest

from hummingbot.connector.gateway.common_types import ConnectorType, get_connector_type


class TestCommonTypes(unittest.TestCase):
    """Test connector type detection with Gateway 2.8 trading types"""

    def test_get_connector_type_with_explicit_suffix(self):
        """Test connectors with explicit trading type suffixes"""
        # CLMM suffix
        self.assertEqual(get_connector_type("raydium/clmm"), ConnectorType.CLMM)
        self.assertEqual(get_connector_type("meteora/clmm"), ConnectorType.CLMM)
        self.assertEqual(get_connector_type("uniswap/clmm"), ConnectorType.CLMM)

        # AMM suffix
        self.assertEqual(get_connector_type("raydium/amm"), ConnectorType.AMM)
        self.assertEqual(get_connector_type("uniswap/amm"), ConnectorType.AMM)

    def test_get_connector_type_without_suffix(self):
        """Test connectors without trading type suffix"""
        # Jupiter only supports swap
        self.assertEqual(get_connector_type("jupiter"), ConnectorType.SWAP)

        # Meteora only supports CLMM
        self.assertEqual(get_connector_type("meteora"), ConnectorType.CLMM)

        # Generic connectors default to SWAP
        self.assertEqual(get_connector_type("uniswap"), ConnectorType.SWAP)
        self.assertEqual(get_connector_type("pancakeswap"), ConnectorType.SWAP)

    def test_get_connector_type_case_insensitive(self):
        """Test that detection works regardless of case"""
        self.assertEqual(get_connector_type("Raydium/CLMM"), ConnectorType.CLMM)
        self.assertEqual(get_connector_type("UNISWAP/AMM"), ConnectorType.AMM)
        self.assertEqual(get_connector_type("Jupiter"), ConnectorType.SWAP)

    def test_get_connector_type_edge_cases(self):
        """Test edge cases"""
        # Empty string defaults to SWAP
        self.assertEqual(get_connector_type(""), ConnectorType.SWAP)

        # Unknown connector defaults to SWAP
        self.assertEqual(get_connector_type("unknown-connector"), ConnectorType.SWAP)

        # Connector with slash but no recognized type defaults to SWAP
        self.assertEqual(get_connector_type("some/other"), ConnectorType.SWAP)


if __name__ == "__main__":
    unittest.main()
