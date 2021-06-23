import unittest
from decimal import Decimal
import asyncio
from hummingbot.core.rate_oracle.utils import find_rate
from hummingbot.core.rate_oracle.rate_oracle import RateOracle


class RateOracleTest(unittest.TestCase):

    def test_find_rate_from_source(self):
        asyncio.get_event_loop().run_until_complete(self._test_find_rate_from_source())

    async def _test_find_rate_from_source(self):
        rate = await RateOracle.rate_async("BTC-USDT")
        print(rate)
        self.assertGreater(rate, 100)

    def test_get_rate_coingecko(self):
        asyncio.get_event_loop().run_until_complete(self._test_get_rate_coingecko())

    async def _test_get_rate_coingecko(self):
        rates = await RateOracle.get_coingecko_prices_by_page("USD", 1)
        print(rates)
        self.assertGreater(len(rates), 100)
        rates = await RateOracle.get_coingecko_prices("USD")
        print(rates)
        self.assertGreater(len(rates), 700)

    def test_rate_oracle_network(self):
        oracle = RateOracle.get_instance()
        oracle.start()
        asyncio.get_event_loop().run_until_complete(oracle.get_ready())
        print(oracle.prices)
        self.assertGreater(len(oracle.prices), 0)
        rate = oracle.rate("SCRT-USDT")
        print(f"rate SCRT-USDT: {rate}")
        self.assertGreater(rate, 0)
        rate1 = oracle.rate("BTC-USDT")
        print(f"rate BTC-USDT: {rate1}")
        self.assertGreater(rate1, 100)
        # wait for 5 s to check rate again
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(5))
        rate2 = oracle.rate("BTC-USDT")
        print(f"rate BTC-USDT: {rate2}")
        self.assertNotEqual(0, rate2)
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
        asyncio.get_event_loop().run_until_complete(self._test_get_binance_prices())

    async def _test_get_binance_prices(self):
        com_prices = await RateOracle.get_binance_prices_by_domain(RateOracle.binance_price_url)
        print(com_prices)
        self.assertGreater(len(com_prices), 1)
        us_prices = await RateOracle.get_binance_prices_by_domain(RateOracle.binance_us_price_url, "USD")
        print(us_prices)
        self.assertGreater(len(us_prices), 1)
        quotes = {p.split("-")[1] for p in us_prices}
        self.assertEqual(len(quotes), 1)
        self.assertEqual(list(quotes)[0], "USD")
        combined_prices = await RateOracle.get_binance_prices()
        self.assertGreater(len(combined_prices), 1)
        self.assertGreater(len(combined_prices), len(com_prices))
