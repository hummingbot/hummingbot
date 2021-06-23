#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))

from hummingbot.connector.exchange.loopring.loopring_api_order_book_data_source import LoopringAPIOrderBookDataSource
# from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
import asyncio
import aiohttp
import logging
from typing import (
    Dict,
    Optional,
    Any,
    # List,
)
# import pandas as pd
import unittest

trading_pairs = ["ETH-USDT", "LRC-ETH", "LINK-ETH"]


class LoopringAPIOrderBookDataSourceUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.order_book_data_source: LoopringAPIOrderBookDataSource = LoopringAPIOrderBookDataSource(trading_pairs)

    def run_async(self, task):
        return self.ev_loop.run_until_complete(task)

    async def get_snapshot(self):
        async with aiohttp.ClientSession() as client:
            trading_pair: str = trading_pairs[0]
            try:
                snapshot: Dict[str, Any] = await self.order_book_data_source.get_snapshot(client, trading_pair, 1000)
                return snapshot
            except Exception:
                return None

    def test_get_snapshot(self):
        snapshot: Optional[Dict[str, Any]] = self.run_async(self.get_snapshot())
        self.assertIsNotNone(snapshot)
        self.assertIn(snapshot["market"], trading_pairs)


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
