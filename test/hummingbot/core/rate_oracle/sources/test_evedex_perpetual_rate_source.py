from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock

from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.rate_oracle.sources.evedex_perpetual_rate_source import EvedexPerpetualRateSource


class EvedexPerpetualRateSourceTest(IsolatedAsyncioWrapperTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.target_token = "XRP"
        cls.global_token = "USDT"
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.target_token, quote=cls.global_token)

    def _get_mock_exchange(self, expected_rate: Decimal):
        mock_exchange = MagicMock()

        async def mock_get_all_pairs_prices():
            return [
                {"symbol": "XRPUSD", "price": str(expected_rate)},
                {"symbol": "BTCUSD", "price": "100000.0"},
            ]

        async def mock_trading_pair_associated_to_exchange_symbol(symbol: str):
            symbol_map = {
                "XRPUSD": combine_to_hb_trading_pair("XRP", "USDT"),
                "BTCUSD": combine_to_hb_trading_pair("BTC", "USDT"),
            }
            if symbol in symbol_map:
                return symbol_map[symbol]
            raise KeyError(f"Unknown symbol: {symbol}")

        mock_exchange.get_all_pairs_prices = mock_get_all_pairs_prices
        mock_exchange.trading_pair_associated_to_exchange_symbol = mock_trading_pair_associated_to_exchange_symbol
        return mock_exchange

    async def test_get_evedex_perpetual_prices(self):
        expected_rate = Decimal("0.5")
        rate_source = EvedexPerpetualRateSource()
        rate_source._exchange = self._get_mock_exchange(expected_rate)

        prices = await rate_source.get_prices()

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(expected_rate, prices[self.trading_pair])

    async def test_get_evedex_perpetual_prices_handles_unknown_symbols(self):
        rate_source = EvedexPerpetualRateSource()
        mock_exchange = MagicMock()

        async def mock_get_all_pairs_prices():
            return [
                {"symbol": "XRPUSD", "price": "0.5"},
                {"symbol": "UNKNOWN", "price": "1.0"},
            ]

        async def mock_trading_pair_associated_to_exchange_symbol(symbol: str):
            if symbol == "XRPUSD":
                return combine_to_hb_trading_pair("XRP", "USDT")
            raise KeyError(f"Unknown symbol: {symbol}")

        mock_exchange.get_all_pairs_prices = mock_get_all_pairs_prices
        mock_exchange.trading_pair_associated_to_exchange_symbol = mock_trading_pair_associated_to_exchange_symbol
        rate_source._exchange = mock_exchange

        prices = await rate_source.get_prices()

        self.assertEqual(1, len(prices))
        self.assertIn(self.trading_pair, prices)

    async def test_get_evedex_perpetual_prices_with_quote_filter(self):
        expected_rate = Decimal("0.5")
        rate_source = EvedexPerpetualRateSource()
        rate_source._exchange = self._get_mock_exchange(expected_rate)

        prices = await rate_source.get_prices(quote_token="USDT")

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(expected_rate, prices[self.trading_pair])

    async def test_get_evedex_perpetual_prices_with_non_matching_quote_filter(self):
        expected_rate = Decimal("0.5")
        rate_source = EvedexPerpetualRateSource()
        rate_source._exchange = self._get_mock_exchange(expected_rate)

        prices = await rate_source.get_prices(quote_token="BTC")

        self.assertEqual(0, len(prices))

    async def test_get_evedex_perpetual_prices_with_none_price(self):
        rate_source = EvedexPerpetualRateSource()
        mock_exchange = MagicMock()

        async def mock_get_all_pairs_prices():
            return [
                {"symbol": "XRPUSD", "price": "0.5"},
                {"symbol": "BTCUSD", "price": None},
            ]

        async def mock_trading_pair_associated_to_exchange_symbol(symbol: str):
            symbol_map = {
                "XRPUSD": combine_to_hb_trading_pair("XRP", "USDT"),
                "BTCUSD": combine_to_hb_trading_pair("BTC", "USDT"),
            }
            if symbol in symbol_map:
                return symbol_map[symbol]
            raise KeyError(f"Unknown symbol: {symbol}")

        mock_exchange.get_all_pairs_prices = mock_get_all_pairs_prices
        mock_exchange.trading_pair_associated_to_exchange_symbol = mock_trading_pair_associated_to_exchange_symbol
        rate_source._exchange = mock_exchange

        prices = await rate_source.get_prices()

        self.assertIn(self.trading_pair, prices)
        self.assertNotIn(combine_to_hb_trading_pair("BTC", "USDT"), prices)

    async def test_get_evedex_perpetual_prices_exception_handling(self):
        rate_source = EvedexPerpetualRateSource()
        rate_source.get_prices.cache_clear()
        mock_exchange = MagicMock()

        async def mock_get_all_pairs_prices():
            raise Exception("Network error")

        mock_exchange.get_all_pairs_prices = mock_get_all_pairs_prices
        rate_source._exchange = mock_exchange

        prices = await rate_source.get_prices()

        self.assertEqual({}, prices)

    async def test_ensure_exchange_creates_connector(self):
        rate_source = EvedexPerpetualRateSource()
        self.assertIsNone(rate_source._exchange)
        rate_source._ensure_exchange()
        self.assertIsNotNone(rate_source._exchange)

    def test_name_property(self):
        rate_source = EvedexPerpetualRateSource()
        self.assertEqual("evedex_perpetual", rate_source.name)
