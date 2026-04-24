from copy import deepcopy
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Dict, Optional
from unittest.mock import MagicMock

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import PriceType
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.rate_oracle.sources.coin_gecko_rate_source import CoinGeckoRateSource
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.rate_oracle.utils import find_rate


class DummyRateSource(RateSourceBase):
    def __init__(self, price_dict: Dict[str, Decimal]):
        self._price_dict = price_dict

    @property
    def name(self):
        return "dummy_rate_source"

    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        return deepcopy(self._price_dict)


class RateOracleTest(IsolatedAsyncioWrapperTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.target_token = "COINALPHA"
        cls.global_token = "HBOT"
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.target_token, quote=cls.global_token)

    def setUp(self) -> None:
        super().setUp()
        if RateOracle._shared_instance is not None:
            RateOracle._shared_instance.stop()
        RateOracle._shared_instance = None

    async def asyncSetUp(self):
        await super().asyncSetUp()

    def tearDown(self) -> None:
        RateOracle._shared_instance = None

    def test_find_rate_from_source(self):
        expected_rate = Decimal("10")
        rate_oracle = RateOracle(source=DummyRateSource(price_dict={self.trading_pair: expected_rate}))

        rate = self.run_async_with_timeout(rate_oracle.rate_async(self.trading_pair))
        self.assertEqual(expected_rate, rate)

    def test_rate_oracle_network(self):
        expected_rate = Decimal("10")
        rate_oracle = RateOracle(source=DummyRateSource(price_dict={self.trading_pair: expected_rate}))

        rate_oracle.start()
        self.run_async_with_timeout(rate_oracle.get_ready())
        self.assertGreater(len(rate_oracle.prices), 0)
        rate = rate_oracle.get_pair_rate(self.trading_pair)
        self.assertEqual(expected_rate, rate)

        self.run_async_with_timeout(rate_oracle.stop_network())

        self.assertIsNone(rate_oracle._fetch_price_task)

    def test_find_rate(self):
        prices = {"HBOT-USDT": Decimal("100"), "AAVE-USDT": Decimal("50"), "USDT-GBP": Decimal("0.75")}
        rate = find_rate(prices, "HBOT-USDT")
        self.assertEqual(rate, Decimal("100"))
        rate = find_rate(prices, "ZBOT-USDT")
        self.assertEqual(rate, None)
        rate = find_rate(prices, "USDT-HBOT")
        self.assertEqual(rate, Decimal("0.01"))
        rate = find_rate(prices, "HBOT-AAVE")
        self.assertEqual(rate, Decimal("2"))
        rate = find_rate(prices, "AAVE-HBOT")
        self.assertEqual(rate, Decimal("0.5"))
        rate = find_rate(prices, "HBOT-GBP")
        self.assertEqual(rate, Decimal("75"))

    def test_find_rate_skips_zero_prices(self):
        """Test that find_rate doesn't cause DivisionByZero when prices contain zero values."""
        # Test case 1: reverse pair has zero price - should skip division and return None
        prices_with_zero_reverse = {"SOL-FARTCOIN": Decimal("0")}
        rate = find_rate(prices_with_zero_reverse, "FARTCOIN-SOL")
        self.assertIsNone(rate)

        # Test case 2: common denominator pair has zero price - should skip that path
        prices_with_zero_common = {
            "HBOT-USDT": Decimal("100"),
            "GBP-USDT": Decimal("0")  # Zero price in common denominator
        }
        rate = find_rate(prices_with_zero_common, "HBOT-GBP")
        # Should return None since the only route involves dividing by zero
        self.assertIsNone(rate)

        # Test case 3: direct pair has zero price - should still return it (no division involved)
        prices_with_zero_direct = {"FARTCOIN-SOL": Decimal("0")}
        rate = find_rate(prices_with_zero_direct, "FARTCOIN-SOL")
        self.assertEqual(rate, Decimal("0"))

    def test_rate_oracle_single_instance_rate_source_reset_after_configuration_change(self):
        config_map = ClientConfigAdapter(ClientConfigMap())
        config_map.rate_oracle_source = "binance"
        rate_oracle = RateOracle.get_instance()
        config_map.rate_oracle_source = "coin_gecko"
        self.assertEqual(type(rate_oracle.source), CoinGeckoRateSource)

    def test_rate_oracle_single_instance_prices_reset_after_global_token_change(self):
        config_map = ClientConfigAdapter(ClientConfigMap())

        rate_oracle = RateOracle.get_instance()

        self.assertEqual(0, len(rate_oracle.prices))

        rate_oracle._prices = {"BTC-USD": Decimal("20000")}

        config_map.global_token.global_token_name = "EUR"

        self.assertEqual(0, len(rate_oracle.prices))

    @staticmethod
    def _make_connector(name: str, order_books: Dict[str, Decimal]) -> MagicMock:
        connector = MagicMock()
        connector.name = name
        connector.order_books = {pair: MagicMock() for pair in order_books}
        connector.get_price_by_type.side_effect = (
            lambda pair, price_type: order_books.get(pair) if price_type == PriceType.MidPrice else None
        )
        return connector

    def test_register_and_unregister_connector(self):
        rate_oracle = RateOracle(source=DummyRateSource(price_dict={}))
        connector = self._make_connector("binance", {"HBOT-USDT": Decimal("2")})

        rate_oracle.register_connector(connector)
        self.assertIn("binance", rate_oracle._connectors)

        rate_oracle.unregister_connector("binance")
        self.assertNotIn("binance", rate_oracle._connectors)

    def test_get_pair_rate_falls_back_to_connector_order_book(self):
        rate_oracle = RateOracle(source=DummyRateSource(price_dict={}))
        connector = self._make_connector("binance", {"HBOT-USDT": Decimal("10.5")})
        rate_oracle.register_connector(connector)

        self.assertEqual(Decimal("10.5"), rate_oracle.get_pair_rate("HBOT-USDT"))

    def test_get_pair_rate_connector_reverse_pair(self):
        rate_oracle = RateOracle(source=DummyRateSource(price_dict={}))
        connector = self._make_connector("binance", {"USDT-HBOT": Decimal("0.1")})
        rate_oracle.register_connector(connector)

        self.assertEqual(Decimal("1") / Decimal("0.1"), rate_oracle.get_pair_rate("HBOT-USDT"))

    def test_get_pair_rate_prefers_configured_source_over_connector(self):
        rate_oracle = RateOracle(source=DummyRateSource(price_dict={}))
        rate_oracle._prices = {"HBOT-USDT": Decimal("100")}
        connector = self._make_connector("binance", {"HBOT-USDT": Decimal("10")})
        rate_oracle.register_connector(connector)

        self.assertEqual(Decimal("100"), rate_oracle.get_pair_rate("HBOT-USDT"))

    def test_get_pair_rate_reverse_on_source_after_connector_miss(self):
        rate_oracle = RateOracle(source=DummyRateSource(price_dict={}))
        rate_oracle._prices = {"USDT-HBOT": Decimal("0.5")}
        connector = self._make_connector("binance", {"FOO-BAR": Decimal("1")})
        rate_oracle.register_connector(connector)

        self.assertEqual(Decimal("2"), rate_oracle.get_pair_rate("HBOT-USDT"))

    def test_get_pair_rate_returns_none_when_no_route(self):
        rate_oracle = RateOracle(source=DummyRateSource(price_dict={}))
        self.assertIsNone(rate_oracle.get_pair_rate("HBOT-USDT"))

    def test_get_pair_rate_connector_iteration_is_deterministic(self):
        rate_oracle = RateOracle(source=DummyRateSource(price_dict={}))
        connector_b = self._make_connector("b_connector", {"HBOT-USDT": Decimal("2")})
        connector_a = self._make_connector("a_connector", {"HBOT-USDT": Decimal("1")})
        rate_oracle.register_connector(connector_b)
        rate_oracle.register_connector(connector_a)

        self.assertEqual(Decimal("1"), rate_oracle.get_pair_rate("HBOT-USDT"))
