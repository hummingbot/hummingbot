import asyncio
import logging
import unittest
from os.path import join, realpath
from typing import List

from hummingbot.connector.exchange.latoken import latoken_constants as CONSTANTS
from hummingbot.connector.exchange.latoken.latoken_api_order_book_data_source import LatokenAPIOrderBookDataSource

import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))


class LatokenAPIOrderBookDataSourceUnitTest(unittest.TestCase):
    trading_pairs: List[str] = [
        "BTC-USDT",
    ]

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.data_source: LatokenAPIOrderBookDataSource = LatokenAPIOrderBookDataSource(
            trading_pairs=cls.trading_pairs
        )

    def test_get_trading_pairs(self):
        result: List[str] = self.ev_loop.run_until_complete(
            self.data_source.get_trading_pairs())

        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        index = result.index("BTC-USDT")
        self.assertIsInstance(result[index], str)
        self.assertEqual(result[index], "BTC-USDT")

    def test_size_snapshot(self):
        async def run_session_for_fetch_snaphot():
            # async with aiohttp.ClientSession() as client:
            result = await self.data_source.get_snapshot("BTC-USDT")  # verify the default set to 100
            assert len(result["bid"]) == CONSTANTS.SNAPSHOT_LIMIT_SIZE
            assert len(result["ask"]) == CONSTANTS.SNAPSHOT_LIMIT_SIZE

            # 25 is default fetch value, that is very small for use in production
            assert len(result["bid"]) > 25
            assert len(result["ask"]) > 25

        self.ev_loop.run_until_complete(run_session_for_fetch_snaphot())


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
