import asyncio
import json
import re
import unittest
from decimal import Decimal
from typing import Dict, Awaitable

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.connector.exchange.binance.binance_api_order_book_data_source import BinanceAPIOrderBookDataSource
from hummingbot.core.rate_oracle.rate_oracle import RateOracle, RateOracleSource
from hummingbot.core.rate_oracle.utils import find_rate
from .fixture import Fixture


class RateOracleTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        BinanceAPIOrderBookDataSource._trading_pair_symbol_map = {
            "com": bidict(
                {"ETHBTC": "ETH-BTC",
                 "LTCBTC": "LTC-BTC",
                 "BTCUSDT": "BTC-USDT",
                 "SCRTBTC": "SCRT-BTC"}),
            "us": bidict(
                {"BTCUSD": "BTC-USD",
                 "ETHUSD": "ETH-USD"})
        }

    @classmethod
    def tearDownClass(cls) -> None:
        BinanceAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        RateOracle.source = RateOracleSource.binance
        RateOracle.get_binance_prices.cache_clear()
        RateOracle.get_kucoin_prices.cache_clear()
        RateOracle.get_ascend_ex_prices.cache_clear()
        RateOracle.get_coingecko_prices.cache_clear()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @aioresponses()
    def test_find_rate_from_source(self, mock_api):
        url = RateOracle.binance_price_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.Binance), repeat=True)

        url = RateOracle.binance_us_price_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response: Fixture.Binance
        mock_api.get(regex_url, body=json.dumps(Fixture.BinanceUS), repeat=True)

        expected_rate = (Decimal("33327.43000000") + Decimal("33327.44000000")) / Decimal(2)

        rate = self.async_run_with_timeout(RateOracle.rate_async("BTC-USDT"))
        self.assertEqual(expected_rate, rate)

    @aioresponses()
    def test_get_rate_coingecko(self, mock_api):
        url = RateOracle.coingecko_usd_price_url.format(1, "USD")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.CoinGeckoPage1), repeat=True)

        url = RateOracle.coingecko_usd_price_url.format(2, "USD")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.CoinGeckoPage2), repeat=True)

        url = RateOracle.coingecko_usd_price_url.format(3, "USD")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.CoinGeckoPage3), repeat=True)

        url = RateOracle.coingecko_usd_price_url.format(4, "USD")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.CoinGeckoPage4), repeat=True)

        url = RateOracle.coingecko_supported_vs_tokens_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.CoinGeckoVSCurrencies), repeat=True)

        rates = self.async_run_with_timeout(RateOracle.get_coingecko_prices_by_page("USD", 1))
        self._assert_rate_dict(rates)
        rates = self.async_run_with_timeout(RateOracle.get_coingecko_prices("USD"))
        self._assert_rate_dict(rates)

    @aioresponses()
    def test_rate_oracle_network(self, mock_api):
        url = RateOracle.binance_price_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.Binance))

        url = RateOracle.binance_us_price_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response: Fixture.Binance
        mock_api.get(regex_url, body=json.dumps(Fixture.BinanceUS))

        oracle = RateOracle()
        oracle.start()
        self.async_run_with_timeout(oracle.get_ready())
        self.assertGreater(len(oracle.prices), 0)
        rate = oracle.rate("SCRT-USDT")
        self.assertGreater(rate, 0)
        rate1 = oracle.rate("BTC-USDT")
        self.assertGreater(rate1, 100)
        oracle.stop()

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

    @aioresponses()
    def test_get_binance_prices(self, mock_api):
        url = RateOracle.binance_price_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.Binance), repeat=True)

        url = RateOracle.binance_us_price_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response: Fixture.Binance
        mock_api.get(regex_url, body=json.dumps(Fixture.BinanceUS), repeat=True)

        com_prices = self.async_run_with_timeout(RateOracle.get_binance_prices_by_domain(RateOracle.binance_price_url))
        self._assert_rate_dict(com_prices)

        us_prices = self.async_run_with_timeout(
            RateOracle.get_binance_prices_by_domain(RateOracle.binance_us_price_url, "USD", domain="us"))
        self._assert_rate_dict(us_prices)
        self.assertGreater(len(us_prices), 1)

        quotes = {p.split("-")[1] for p in us_prices}
        self.assertEqual(len(quotes), 1)
        self.assertEqual(list(quotes)[0], "USD")
        combined_prices = self.async_run_with_timeout(RateOracle.get_binance_prices())
        self._assert_rate_dict(combined_prices)
        self.assertGreater(len(combined_prices), len(com_prices))

    @aioresponses()
    def test_get_kucoin_prices(self, mock_api):
        url = RateOracle.kucoin_price_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.Kucoin), repeat=True)

        prices = self.async_run_with_timeout(RateOracle.get_kucoin_prices())
        self._assert_rate_dict(prices)

    def _assert_rate_dict(self, rates: Dict[str, Decimal]):
        self.assertGreater(len(rates), 0)
        self.assertTrue(all(r > 0 for r in rates.values()))
        self.assertTrue(all(isinstance(k, str) and isinstance(v, Decimal) for k, v in rates.items()))

    @aioresponses()
    def test_get_ascend_ex_prices(self, mock_api):
        url = RateOracle.ascend_ex_price_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.AscendEx), repeat=True)

        prices = self.async_run_with_timeout(RateOracle.get_ascend_ex_prices())
        self._assert_rate_dict(prices)
