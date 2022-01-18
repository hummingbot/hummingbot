import asyncio
import unittest

from decimal import Decimal
from typing import Dict
from unittest import mock

from bidict import bidict
from yarl import URL

from hummingbot.connector.exchange.binance.binance_api_order_book_data_source import BinanceAPIOrderBookDataSource
from hummingbot.core.mock_api.mock_web_server import MockWebServer
from hummingbot.core.rate_oracle.utils import find_rate
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from .fixture import Fixture


class RateOracleTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
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

        cls.web_app = MockWebServer.get_instance()
        cls.web_app.add_host_to_mock(URL(RateOracle.binance_price_url).host)
        cls.web_app.add_host_to_mock(URL(RateOracle.binance_us_price_url).host)
        cls.web_app.add_host_to_mock(URL(RateOracle.coingecko_supported_vs_tokens_url).host)
        cls.web_app.add_host_to_mock(URL(RateOracle.kucoin_price_url).host)
        cls.web_app.add_host_to_mock(URL(RateOracle.ascend_ex_price_url).host)
        cls.web_app.start()
        cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())
        cls._patcher = mock.patch("aiohttp.client.URL")
        cls._url_mock = cls._patcher.start()
        cls._url_mock.side_effect = cls.web_app.reroute_local

        cls.web_app.update_response(
            "get", URL(RateOracle.binance_price_url).host,
            URL(RateOracle.binance_price_url).path, Fixture.Binance)
        cls.web_app.update_response(
            "get", URL(RateOracle.binance_us_price_url).host,
            URL(RateOracle.binance_us_price_url).path, Fixture.BinanceUS)
        cls.web_app.update_response(
            "get", URL(RateOracle.coingecko_supported_vs_tokens_url).host,
            URL(RateOracle.coingecko_supported_vs_tokens_url).path, Fixture.CoinGeckoVSCurrencies)
        cls.web_app.update_response(
            "get", URL(RateOracle.kucoin_price_url).host,
            URL(RateOracle.kucoin_price_url).path, Fixture.Kucoin)
        cls.web_app.update_response(
            "get", URL(RateOracle.ascend_ex_price_url).host,
            URL(RateOracle.ascend_ex_price_url).path, Fixture.AscendEx)

        cls.web_app.update_response(
            "get", URL(RateOracle.coingecko_usd_price_url).host,
            URL(RateOracle.coingecko_usd_price_url).path, Fixture.CoinGeckoPage1, params={"page": 1})
        cls.web_app.update_response(
            "get", URL(RateOracle.coingecko_usd_price_url).host,
            URL(RateOracle.coingecko_usd_price_url).path, Fixture.CoinGeckoPage2, params={"page": 2})
        cls.web_app.update_response(
            "get", URL(RateOracle.coingecko_usd_price_url).host,
            URL(RateOracle.coingecko_usd_price_url).path, Fixture.CoinGeckoPage3, params={"page": 3})
        cls.web_app.update_response(
            "get", URL(RateOracle.coingecko_usd_price_url).host,
            URL(RateOracle.coingecko_usd_price_url).path, Fixture.CoinGeckoPage4, params={"page": 4})

    @classmethod
    def tearDownClass(cls) -> None:
        BinanceAPIOrderBookDataSource._trading_pair_symbol_map = {}
        cls.web_app.stop()
        cls._patcher.stop()

    def test_find_rate_from_source(self):
        self.ev_loop.run_until_complete(self._test_find_rate_from_source())

    async def _test_find_rate_from_source(self):
        rate = await RateOracle.rate_async("BTC-USDT")
        self.assertGreater(rate, 100)

    def test_get_rate_coingecko(self):
        self.ev_loop.run_until_complete(self._test_get_rate_coingecko())

    async def _test_get_rate_coingecko(self):
        rates = await RateOracle.get_coingecko_prices_by_page("USD", 1)
        self._assert_rate_dict(rates)
        rates = await RateOracle.get_coingecko_prices("USD")
        self._assert_rate_dict(rates)

    def test_rate_oracle_network(self):
        oracle = RateOracle.get_instance()
        oracle.start()
        asyncio.get_event_loop().run_until_complete(oracle.get_ready())
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

    def test_get_binance_prices(self):
        self.ev_loop.run_until_complete(self._test_get_binance_prices())

    async def _test_get_binance_prices(self):
        com_prices = await RateOracle.get_binance_prices_by_domain(RateOracle.binance_price_url)
        self._assert_rate_dict(com_prices)
        us_prices = await RateOracle.get_binance_prices_by_domain(RateOracle.binance_us_price_url, "USD", domain="us")
        self._assert_rate_dict(us_prices)
        self.assertGreater(len(us_prices), 1)
        quotes = {p.split("-")[1] for p in us_prices}
        self.assertEqual(len(quotes), 1)
        self.assertEqual(list(quotes)[0], "USD")
        combined_prices = await RateOracle.get_binance_prices()
        self._assert_rate_dict(combined_prices)
        self.assertGreater(len(combined_prices), len(com_prices))

    def test_get_kucoin_prices(self):
        self.ev_loop.run_until_complete(self._test_get_kucoin_prices())

    async def _test_get_kucoin_prices(self):
        prices = await RateOracle.get_kucoin_prices()
        self._assert_rate_dict(prices)

    def _assert_rate_dict(self, rates: Dict[str, Decimal]):
        self.assertGreater(len(rates), 0)
        self.assertTrue(all(r > 0 for r in rates.values()))
        self.assertTrue(all(isinstance(k, str) and isinstance(v, Decimal) for k, v in rates.items()))

    def test_get_ascend_ex_prices(self):
        self.ev_loop.run_until_complete(self._test_get_ascend_ex_prices())

    async def _test_get_ascend_ex_prices(self):
        prices = await RateOracle.get_ascend_ex_prices()
        self._assert_rate_dict(prices)
