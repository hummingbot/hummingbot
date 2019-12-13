#!/usr/bin/env python
from os.path import (
    join,
    realpath
)
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

import asyncio
import logging
import unittest
from typing import List

from hummingbot.market.bitfinex.bitfinex_api_order_book_data_source import (
    BitfinexAPIOrderBookDataSource,
)


class BitfinexAPIOrderBookDataSourceUnitTest(unittest.TestCase):
    trading_pairs: List[str] = [
        "tBTCUSD",
    ]

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.data_source: BitfinexAPIOrderBookDataSource = BitfinexAPIOrderBookDataSource(
            trading_pairs=cls.trading_pairs
        )

    def test_get_trading_pairs(self):
        result: List[str] = self.ev_loop.run_until_complete(self.data_source.get_trading_pairs())

        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        self.assertIsInstance(result[0], str)
        self.assertEqual(result[0], "tBTCUSD")


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
