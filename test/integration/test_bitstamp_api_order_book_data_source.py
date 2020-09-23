#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

from hummingbot.connector.exchange.bitstamp.bitstamp_api_order_book_data_source import BitstampAPIOrderBookDataSource
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
import asyncio
import aiohttp
import logging
from typing import (
    Dict,
    Optional,
    Any,
)
import unittest


class BitstampAPIOrderBookDataSourceUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.order_book_data_source: BitstampAPIOrderBookDataSource = BitstampAPIOrderBookDataSource()

    def run_async(self, task):
        return self.ev_loop.run_until_complete(task)

    async def get_snapshot(self, trading_pair):
        async with aiohttp.ClientSession() as client:
            try:
                snapshot: Dict[str, Any] = await self.order_book_data_source.get_snapshot(client, trading_pair)
                return snapshot
            except Exception:
                return None

    def test_get_snapshot(self):
        snapshot: Optional[Dict[str, Any]] = self.run_async(self.get_snapshot("ETH-USD"))
        self.assertIsNotNone(snapshot)
        self.assertIn(snapshot["trading_pair"], ["ETH-USD"])

    def test_get_last_traded_prices(self):
        last_traded_prices: Dict[str, float] = self.run_async(
            self.order_book_data_source.get_last_traded_prices(["ETH-USD", "BTC-USD"])
        )
        self.assertIn("ETH-USD", last_traded_prices)
        self.assertIn("BTC-USD", last_traded_prices)

    def test_get_tracking_pairs(self):
        tracking_pairs: Dict[str, OrderBookTrackerEntry] = self.run_async(
            self.order_book_data_source.get_last_traded_prices(["ETH-USD", "BTC-USD"])
        )
        self.assertIsInstance(tracking_pairs["ethusd"], OrderBookTrackerEntry)


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
