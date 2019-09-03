#!/usr/bin/env python
import time
from os.path import join, realpath
import sys;sys.path.insert(0, realpath(join(__file__, "../../")))
import asyncio
from hummingbot.data_feed.data_feed_base import DataFeedBase
import logging; logging.basicConfig(level=logging.ERROR)
import unittest
from hummingbot.core.utils.exchange_rate_conversion import ExchangeRateConversion


class MockDataFeed1(DataFeedBase):
    _mdf_shared_instance: "MockDataFeed1" = None
    @classmethod
    def get_instance(cls) -> "MockDataFeed1":
        if cls._mdf_shared_instance is None:
            cls._mdf_shared_instance = MockDataFeed1()
        return cls._mdf_shared_instance

    @property
    def name(self):
        return "coin_alpha_feed"

    def __init__(self):
        super().__init__()
        self.mock_price_dict = {"coin_alpha": 1, "cat": 2}

    def get_price(self, symbol):
        return self.mock_price_dict.get(symbol)


class MockDataFeed2(DataFeedBase):
    _mdf2_shared_instance: "MockDataFeed2" = None

    @classmethod
    def get_instance(cls) -> "MockDataFeed2":
        if cls._mdf2_shared_instance is None:
            cls._mdf2_shared_instance = MockDataFeed2()
        return cls._mdf2_shared_instance

    @property
    def name(self):
        return "cat"

    def __init__(self):
        super().__init__()
        self.mock_price_dict = {"coin_alpha": 1, "cat": 5}

    def get_price(self, symbol):
        return self.mock_price_dict.get(symbol)


def async_run(func):
    loop = asyncio.new_event_loop()
    loop.run_until_complete(func)


class ExchangeRateConverterUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ExchangeRateConversion.set_global_exchange_rate_config({
            "global_config": {
                "cat": {"default": 1, "source": "cat"},
                "coin_alpha": {"default": 0, "source": "coin_alpha_feed"}
            },
            "conversion_required": {
                "cat": {"default": 100, "source": "cat"}
            }
        })
        ExchangeRateConversion.set_data_feeds([
            MockDataFeed1.get_instance(),
            MockDataFeed2.get_instance()
        ])
        ExchangeRateConversion.set_update_interval(0.1)
        ExchangeRateConversion.get_instance().start()
        time.sleep(1)

    def setUp(self):
        async_run(ExchangeRateConversion.get_instance().update_exchange_rates_from_data_feeds())

    def test_adjust_token_rate(self):
        adjusted_cat = ExchangeRateConversion.get_instance().adjust_token_rate("cat", 10)
        self.assertEqual(adjusted_cat, 50)

    def test_convert_token_value(self):
        coin_alpha_to_cat = ExchangeRateConversion.get_instance().convert_token_value(
            10, from_currency="coin_alpha", to_currency="cat"
        )
        self.assertEqual(coin_alpha_to_cat, 2.0)

        coin_alpha_to_cat = ExchangeRateConversion.get_instance().convert_token_value(
            1, from_currency="coin_alpha", to_currency="cat"
        )
        self.assertEqual(coin_alpha_to_cat, 0.2)

    def test_get_multiple_data_feed(self):
        exchaneg_rate = ExchangeRateConversion.get_instance().exchange_rate
        self.assertEqual(exchaneg_rate, {'cat': 5, 'coin_alpha': 1})


def main():
    unittest.main()


if __name__ == "__main__":
    main()
