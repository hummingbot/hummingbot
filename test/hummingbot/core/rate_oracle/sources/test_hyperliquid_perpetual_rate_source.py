from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock

from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.rate_oracle.sources.hyperliquid_perpetual_rate_source import HyperliquidPerpetualRateSource


class HyperliquidPerpetualRateSourceTest(IsolatedAsyncioWrapperTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.target_token = "xyz:XYZ100"
        cls.global_token = "USD"
        cls.hyperliquid_pair = f"{cls.target_token}-{cls.global_token}"
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.target_token, quote=cls.global_token)
        cls.hyperliquid_ignored_pair = "SOMEPAIR"
        cls.ignored_trading_pair = combine_to_hb_trading_pair(base="SOME", quote="PAIR")

    def _get_mock_exchange(self, expected_rate: Decimal):
        """Create a mock exchange that returns properly structured price data."""
        mock_exchange = MagicMock()

        # Mock get_all_pairs_prices to return a list of symbol/price dicts
        async def mock_get_all_pairs_prices():
            return [
                {"symbol": "xyz:XYZ100", "price": str(expected_rate)},
                {"symbol": "xyz:TSLA", "price": "483.02"},
                {"symbol": "BTC", "price": "100000.0"},
            ]

        mock_exchange.get_all_pairs_prices = mock_get_all_pairs_prices

        # Mock trading_pair_associated_to_exchange_symbol
        async def mock_trading_pair_associated_to_exchange_symbol(symbol: str):
            symbol_map = {
                "xyz:XYZ100": combine_to_hb_trading_pair("xyz:XYZ100", "USD"),
                "xyz:TSLA": combine_to_hb_trading_pair("xyz:TSLA", "USD"),
                "BTC": combine_to_hb_trading_pair("BTC", "USD"),
            }
            if symbol in symbol_map:
                return symbol_map[symbol]
            raise KeyError(f"Unknown symbol: {symbol}")

        mock_exchange.trading_pair_associated_to_exchange_symbol = mock_trading_pair_associated_to_exchange_symbol

        return mock_exchange

    async def test_get_hyperliquid_prices(self):
        expected_rate = Decimal("10")

        rate_source = HyperliquidPerpetualRateSource()
        # Replace the exchange with our mock
        rate_source._exchange = self._get_mock_exchange(expected_rate)

        prices = await rate_source.get_prices()

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(expected_rate, prices[self.trading_pair])
        self.assertNotIn(self.ignored_trading_pair, prices)

    async def test_get_hyperliquid_prices_handles_unknown_symbols(self):
        """Test that unknown symbols are gracefully skipped."""
        rate_source = HyperliquidPerpetualRateSource()

        mock_exchange = MagicMock()

        async def mock_get_all_pairs_prices():
            return [
                {"symbol": "xyz:XYZ100", "price": "10"},
                {"symbol": "UNKNOWN_SYMBOL", "price": "100"},  # This should be skipped
            ]

        async def mock_trading_pair_associated_to_exchange_symbol(symbol: str):
            if symbol == "xyz:XYZ100":
                return combine_to_hb_trading_pair("xyz:XYZ100", "USD")
            raise KeyError(f"Unknown symbol: {symbol}")

        mock_exchange.get_all_pairs_prices = mock_get_all_pairs_prices
        mock_exchange.trading_pair_associated_to_exchange_symbol = mock_trading_pair_associated_to_exchange_symbol

        rate_source._exchange = mock_exchange

        prices = await rate_source.get_prices()

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(Decimal("10"), prices[self.trading_pair])
        # UNKNOWN_SYMBOL should not appear in prices
        self.assertEqual(1, len(prices))

    async def test_get_hyperliquid_prices_with_quote_filter(self):
        """Test filtering prices by quote token."""
        expected_rate = Decimal("10")

        rate_source = HyperliquidPerpetualRateSource()
        rate_source._exchange = self._get_mock_exchange(expected_rate)

        prices = await rate_source.get_prices(quote_token="USD")

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(expected_rate, prices[self.trading_pair])
