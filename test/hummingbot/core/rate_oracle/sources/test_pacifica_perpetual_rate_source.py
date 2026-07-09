from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock

import pytest

from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.rate_oracle.sources.pacifica_perpetual_rate_source import PacificaPerpetualRateSource


class PacificaPerpetualRateSourceTest(IsolatedAsyncioWrapperTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.target_token = "BTC"
        cls.global_token = "USDC"
        cls.pacifica_symbol = "BTC"
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.target_token, quote=cls.global_token)
        cls.ignored_trading_pair = combine_to_hb_trading_pair(base="SOME", quote="PAIR")

    def _get_mock_exchange(self, expected_rate: Decimal):
        """Create a mock exchange that returns properly structured price data."""
        mock_exchange = MagicMock()

        # Mock get_all_pairs_prices to return a list of symbol/price dicts
        async def mock_get_all_pairs_prices():
            return [
                {"trading_pair": "BTC-USDC", "price": str(expected_rate)},
                {"trading_pair": "ETH-USDC", "price": "2500.00"},
            ]

        mock_exchange.get_all_pairs_prices = mock_get_all_pairs_prices

        # Mock trading_pair_associated_to_exchange_symbol
        async def mock_trading_pair_associated_to_exchange_symbol(trading_pair: str):
            symbol_map = {
                "BTC-USDC": combine_to_hb_trading_pair("BTC", "USDC"),
                "ETH-USDC": combine_to_hb_trading_pair("ETH", "USDC"),
            }
            if trading_pair in symbol_map:
                return symbol_map[trading_pair]
            raise KeyError(f"Unknown symbol: {trading_pair}")

        mock_exchange.trading_pair_associated_to_exchange_symbol = mock_trading_pair_associated_to_exchange_symbol

        return mock_exchange

    async def test_get_pacifica_prices(self):
        expected_rate = Decimal("95000")

        rate_source = PacificaPerpetualRateSource()
        # Replace the exchange with our mock
        rate_source._exchange = self._get_mock_exchange(expected_rate)

        prices = await rate_source.get_prices()

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(expected_rate, prices[self.trading_pair])
        self.assertNotIn(self.ignored_trading_pair, prices)

    async def test_get_pacifica_prices_with_quote_filter(self):
        """Test filtering prices by quote token."""
        expected_rate = Decimal("95000")

        rate_source = PacificaPerpetualRateSource()
        rate_source._exchange = self._get_mock_exchange(expected_rate)

        prices = await rate_source.get_prices(quote_token="USDC")

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(expected_rate, prices[self.trading_pair])

    async def test_get_pacifica_prices_with_non_matching_quote_filter(self):
        """Test filtering prices by quote token that doesn't match."""
        expected_rate = Decimal("95000")

        rate_source = PacificaPerpetualRateSource()
        rate_source._exchange = self._get_mock_exchange(expected_rate)

        # Should raise ValueError since quote token is not USDC
        with pytest.raises(ValueError, match="Pacifica Perpetual only supports USDC as quote token."):
            await rate_source.get_prices(quote_token="USDT")  # Not USDC

    async def test_get_pacifica_prices_exception_handling(self):
        """Test exception handling in get_prices."""
        rate_source = PacificaPerpetualRateSource()

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
        """Test _ensure_exchange creates connector when None."""
        rate_source = PacificaPerpetualRateSource()

        # Initially exchange should be None
        self.assertIsNone(rate_source._exchange)

        # Call _ensure_exchange
        rate_source._ensure_exchange()

        # Now exchange should be created
        self.assertIsNotNone(rate_source._exchange)

    def test_name_property(self):
        """Test name property returns correct value."""
        rate_source = PacificaPerpetualRateSource()
        self.assertEqual("pacifica_perpetual", rate_source.name)
