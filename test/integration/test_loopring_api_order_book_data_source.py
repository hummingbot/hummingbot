#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

from hummingbot.market.loopring.loopring_api_order_book_data_source import LoopringAPIOrderBookDataSource
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
import asyncio
import aiohttp
import logging
from typing import (
    Dict,
    Optional,
    Any,
    List,
)
import pandas as pd
import unittest


class LoopringAPIOrderBookDataSourceUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.order_book_data_source: LoopringAPIOrderBookDataSource = LoopringAPIOrderBookDataSource(["ETH-USDT", "LRC-ETH", "LINK-ETH"])

    def run_async(self, task):
        return self.ev_loop.run_until_complete(task)

    def test_get_active_exchange_markets(self):
        market_data: pd.DataFrame = self.run_async(self.order_book_data_source.get_active_exchange_markets())
        self.assertIn("LRC-ETH", market_data.index)

    def test_get_trading_pairs(self):
        trading_pairs: List[str] = self.run_async(self.order_book_data_source.get_trading_pairs())
        self.assertIn("LRC-ETH", trading_pairs)

    async def get_snapshot(self):
        async with aiohttp.ClientSession() as client:
            trading_pairs: List[str] = await self.order_book_data_source.get_trading_pairs()
            trading_pair: str = trading_pairs[0]
            try:
                snapshot: Dict[str, Any] = await self.order_book_data_source.get_snapshot(client, trading_pair, 1000)
                return snapshot
            except Exception:
                return None

    def test_get_snapshot(self):
        snapshot: Optional[Dict[str, Any]] = self.run_async(self.get_snapshot())
        self.assertIsNotNone(snapshot)
        self.assertIn(snapshot["market"], self.run_async(self.order_book_data_source.get_trading_pairs()))

    def test_get_tracking_pairs(self):
        tracking_pairs: Dict[str, OrderBookTrackerEntry] = self.run_async(self.order_book_data_source.get_tracking_pairs())
        self.assertIsInstance(tracking_pairs["LRC-ETH"], OrderBookTrackerEntry)


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
