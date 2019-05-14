#!/usr/bin/env python
from os.path import join, realpath
import sys;sys.path.insert(0, realpath(join(__file__, "../../")))
from hummingbot.data_feed.coin_metrics_data_feed import CoinMetricsDataFeed
import asyncio
import logging; logging.basicConfig(level=logging.ERROR)
import unittest


def async_run(func):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(func)


class CoinMetricsUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        async_run(CoinMetricsDataFeed.get_instance().fetch_data())

    @classmethod
    def tearDownClass(cls):
        async_run(CoinMetricsDataFeed.get_instance()._session.close())

    def setUp(self):
        pass

    def test_get_rates(self):
        price_dict = CoinMetricsDataFeed.get_instance().price_dict
        self.assertTrue(len(price_dict) > 0)
        for asset, price in price_dict.items():
            self.assertTrue(float(price) > 0)


def main():
    unittest.main()


if __name__ == "__main__":
    main()
