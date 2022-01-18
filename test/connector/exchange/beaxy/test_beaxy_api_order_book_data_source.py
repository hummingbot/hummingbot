from hummingbot.connector.exchange.beaxy.beaxy_auth import BeaxyAuth
import unittest
import conf
import asyncio
import aiohttp
from typing import (
    List,
    Optional,
    Any,
    Dict
)
from hummingbot.connector.exchange.beaxy.beaxy_api_order_book_data_source import BeaxyAPIOrderBookDataSource
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry


class BeaxyApiOrderBookDataSourceUnitTest(unittest.TestCase):

    trading_pairs: List[str] = [
        "BTC-USDC",
    ]

    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.get_event_loop()
        cls._auth: BeaxyAuth = BeaxyAuth(conf.beaxy_api_key, conf.beaxy_secret_key)
        cls.data_source: BeaxyAPIOrderBookDataSource = BeaxyAPIOrderBookDataSource(cls.trading_pairs)

    def run_async(self, task):
        return self.ev_loop.run_until_complete(task)

    def test_get_trading_pairs(self):
        trading_pairs: Optional[List[str]] = self.run_async(self.data_source.get_trading_pairs())
        assert trading_pairs is not None
        self.assertIn("ETC-BTC", trading_pairs)
        self.assertNotIn("NRG-BTC", trading_pairs)

    async def get_snapshot(self):
        async with aiohttp.ClientSession() as client:
            trading_pairs: Optional[List[str]] = await self.data_source.get_trading_pairs()
            assert trading_pairs is not None
            trading_pair: str = trading_pairs[0]
            try:
                snapshot: Dict[str, Any] = await self.data_source.get_snapshot(client, trading_pair, 20)
                return snapshot
            except Exception:
                return None

    def test_get_snapshot(self):
        snapshot: Optional[Dict[str, Any]] = self.run_async(self.get_snapshot())
        assert snapshot is not None
        self.assertIsNotNone(snapshot)
        trading_pairs = self.run_async(self.data_source.get_trading_pairs())
        assert trading_pairs is not None
        self.assertIn(snapshot["security"], [p.replace('-', '') for p in trading_pairs])

    def test_get_tracking_pairs(self):
        tracking_pairs: Dict[str, OrderBookTrackerEntry] = self.run_async(self.data_source.get_tracking_pairs())
        self.assertIsInstance(tracking_pairs["BTC-USDC"], OrderBookTrackerEntry)
