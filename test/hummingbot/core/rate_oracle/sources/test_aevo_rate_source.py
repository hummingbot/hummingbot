from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock

from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.rate_oracle.sources.aevo_rate_source import AevoRateSource


class AevoRateSourceTest(IsolatedAsyncioWrapperTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.eth_pair = combine_to_hb_trading_pair(base="ETH", quote="USDC")
        cls.btc_pair = combine_to_hb_trading_pair(base="BTC", quote="USDC")

    def _get_mock_exchange(self) -> MagicMock:
        mock_exchange = MagicMock()

        async def mock_get_all_pairs_prices():
            return [
                {"symbol": "ETH-PERP", "price": "2000"},
                {"symbol": "BTC-PERP", "price": "50000"},
                {"symbol": "SOL-PERP", "price": None},
                {"symbol": "UNKNOWN-PERP", "price": "1"},
            ]

        async def mock_trading_pair_associated_to_exchange_symbol(symbol: str):
            symbol_map = {
                "ETH-PERP": self.eth_pair,
                "BTC-PERP": self.btc_pair,
                "SOL-PERP": combine_to_hb_trading_pair(base="SOL", quote="USDC"),
            }
            if symbol in symbol_map:
                return symbol_map[symbol]
            raise KeyError(f"Unknown symbol: {symbol}")

        mock_exchange.get_all_pairs_prices = mock_get_all_pairs_prices
        mock_exchange.trading_pair_associated_to_exchange_symbol = mock_trading_pair_associated_to_exchange_symbol
        return mock_exchange

    async def test_get_prices(self):
        rate_source = AevoRateSource()
        rate_source._exchange = self._get_mock_exchange()

        prices = await rate_source.get_prices()

        self.assertEqual(Decimal("2000"), prices[self.eth_pair])
        self.assertEqual(Decimal("50000"), prices[self.btc_pair])
        self.assertEqual(2, len(prices))

    async def test_get_prices_with_quote_token_filter(self):
        rate_source = AevoRateSource()
        rate_source._exchange = self._get_mock_exchange()

        prices = await rate_source.get_prices(quote_token="USD")

        self.assertEqual({}, prices)

    async def test_get_prices_handles_exchange_errors(self):
        rate_source = AevoRateSource()
        rate_source.get_prices.cache_clear()
        mock_exchange = MagicMock()

        async def mock_get_all_pairs_prices():
            raise Exception("network error")

        mock_exchange.get_all_pairs_prices = mock_get_all_pairs_prices
        rate_source._exchange = mock_exchange

        prices = await rate_source.get_prices()

        self.assertEqual({}, prices)
