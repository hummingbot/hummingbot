import asyncio
import unittest
from copy import deepcopy
from decimal import Decimal
from typing import Awaitable, Dict, Optional

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.utils import combine_to_hb_trading_pair
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


class RateOracleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.target_token = "COINALPHA"
        cls.global_token = "HBOT"
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.target_token, quote=cls.global_token)

    def setUp(self) -> None:
        if RateOracle._shared_instance is not None:
            RateOracle._shared_instance.stop()
        RateOracle._shared_instance = None

    def tearDown(self) -> None:
        RateOracle._shared_instance = None

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_find_rate_from_source(self):
        expected_rate = Decimal("10")
        rate_oracle = RateOracle(source=DummyRateSource(price_dict={self.trading_pair: expected_rate}))

        rate = self.async_run_with_timeout(rate_oracle.rate_async(self.trading_pair))
        self.assertEqual(expected_rate, rate)

    def test_rate_oracle_network(self):
        expected_rate = Decimal("10")
        rate_oracle = RateOracle(source=DummyRateSource(price_dict={self.trading_pair: expected_rate}))

        rate_oracle.start()
        self.async_run_with_timeout(rate_oracle.get_ready())
        self.assertGreater(len(rate_oracle.prices), 0)
        rate = rate_oracle.get_pair_rate(self.trading_pair)
        self.assertEqual(expected_rate, rate)

        self.async_run_with_timeout(rate_oracle.stop_network())

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
