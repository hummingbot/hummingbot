#!/usr/bin/env python
import asyncio
import logging
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))
import unittest

from hummingbot.data_feed.coin_gecko_data_feed import CoinGeckoDataFeed


def async_run(func):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(func)


class CoinGeckoUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        async_run(CoinGeckoDataFeed.get_instance().fetch_data())

    @classmethod
    def tearDownClass(cls):
        async_run(CoinGeckoDataFeed.get_instance()._shared_client.close())

    def setUp(self):
        pass

    def test_get_rates(self):
        price_dict = CoinGeckoDataFeed.get_instance().price_dict
        self.assertTrue(len(price_dict) > 0)
        for asset, price in price_dict.items():
            self.assertTrue(isinstance(price, float))
        self.assertTrue(price_dict["BTC"] > 0)
        self.assertTrue(price_dict["ETH"] > 0)
        self.assertTrue(price_dict["ZRX"] > 0)
        self.assertTrue(price_dict["XLM"] > 0)


def main():
    logging.basicConfig(level=logging.ERROR)
    unittest.main()


if __name__ == "__main__":
    main()
