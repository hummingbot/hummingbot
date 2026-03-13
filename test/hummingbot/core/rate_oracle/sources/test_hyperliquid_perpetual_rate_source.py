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

    async def test_get_hyperliquid_prices_with_non_matching_quote_filter(self):
        """Test filtering prices by quote token that doesn't match (line 38)."""
        expected_rate = Decimal("10")

        rate_source = HyperliquidPerpetualRateSource()
        rate_source._exchange = self._get_mock_exchange(expected_rate)

        prices = await rate_source.get_prices(quote_token="BTC")  # Not USD

        # Should return empty dict since quote doesn't match
        self.assertEqual(0, len(prices))

    async def test_get_hyperliquid_prices_with_none_price(self):
        """Test handling of None price values (lines 42-43)."""
        rate_source = HyperliquidPerpetualRateSource()

        mock_exchange = MagicMock()

        async def mock_get_all_pairs_prices():
            return [
                {"symbol": "xyz:XYZ100", "price": "10"},
                {"symbol": "BTC", "price": None},  # None price should be skipped
            ]

        async def mock_trading_pair_associated_to_exchange_symbol(symbol: str):
            symbol_map = {
                "xyz:XYZ100": combine_to_hb_trading_pair("xyz:XYZ100", "USD"),
                "BTC": combine_to_hb_trading_pair("BTC", "USD"),
            }
            if symbol in symbol_map:
                return symbol_map[symbol]
            raise KeyError(f"Unknown symbol: {symbol}")

        mock_exchange.get_all_pairs_prices = mock_get_all_pairs_prices
        mock_exchange.trading_pair_associated_to_exchange_symbol = mock_trading_pair_associated_to_exchange_symbol

        rate_source._exchange = mock_exchange

        prices = await rate_source.get_prices()

        self.assertIn(self.trading_pair, prices)
        # BTC should not be in prices due to None price
        btc_pair = combine_to_hb_trading_pair("BTC", "USD")
        self.assertNotIn(btc_pair, prices)

    async def test_get_hyperliquid_prices_exception_handling(self):
        """Test exception handling in get_prices (lines 50, 54, 58)."""
        rate_source = HyperliquidPerpetualRateSource()

        # Clear the cache to ensure our mock is called
        rate_source.get_prices.cache_clear()

        mock_exchange = MagicMock()

        async def mock_get_all_pairs_prices():
            raise Exception("Network error")

        mock_exchange.get_all_pairs_prices = mock_get_all_pairs_prices

        rate_source._exchange = mock_exchange

        prices = await rate_source.get_prices()

        # Should return empty dict on exception
        self.assertEqual({}, prices)

    async def test_ensure_exchange_creates_connector(self):
        """Test _ensure_exchange creates connector when None (line 21)."""
        rate_source = HyperliquidPerpetualRateSource()

        # Initially exchange should be None
        self.assertIsNone(rate_source._exchange)

        # Call _ensure_exchange
        rate_source._ensure_exchange()

        # Now exchange should be created
        self.assertIsNotNone(rate_source._exchange)

    def test_name_property(self):
        """Test name property returns correct value."""
        rate_source = HyperliquidPerpetualRateSource()
        self.assertEqual("hyperliquid_perpetual", rate_source.name)
