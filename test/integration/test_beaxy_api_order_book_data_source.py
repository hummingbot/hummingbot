from hummingbot.market.beaxy.beaxy_auth import BeaxyAuth
import unittest
import conf
import asyncio
import aiohttp
import pandas as pd
from typing import (
    List,
    Optional,
    Any,
    Dict
)
from hummingbot.market.beaxy.beaxy_api_order_book_data_source import BeaxyAPIOrderBookDataSource
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.market.beaxy.beaxy_order_book_message import BeaxyOrderBookMessage
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class BeaxyApiOrderBookDataSourceUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.get_event_loop()
        cls._auth: BeaxyAuth = BeaxyAuth(conf.beaxy_api_key, conf.beaxy_api_secret)
        cls.data_source: BeaxyAPIOrderBookDataSource = BeaxyAPIOrderBookDataSource()

    def run_async(self, task):
        return self.ev_loop.run_until_complete(task)

    def test_get_active_exchange_markets(self):
        all_markets_df: pd.DataFrame = self.run_async(self.data_source.get_active_exchange_markets())

        # Check DF type
        self.assertIsInstance(all_markets_df, pd.DataFrame)

        # Check DF order, make sure it's sorted by USDVolume col in desending order
        usd_volumes = all_markets_df.loc[:, 'USDVolume'].to_list()
        self.assertListEqual(
            usd_volumes,
            sorted(usd_volumes, reverse=True),
            "The output usd volumes should remain the same after being sorted again")

    def test_get_trading_pairs(self):
        trading_pairs: Optional[List[str]] = self.run_async(self.data_source.get_trading_pairs())
        assert trading_pairs is not None
        self.assertIn("ETCBTC", trading_pairs)
        self.assertNotIn("NRGBTC", trading_pairs)

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
        self.assertIn(snapshot["security"], trading_pairs)

    def test_get_tracking_pairs(self):
        tracking_pairs: Dict[str, OrderBookTrackerEntry] = self.run_async(self.data_source.get_tracking_pairs())
        self.assertIsInstance(tracking_pairs["BTCUSDC"], OrderBookTrackerEntry)

    def test_listen_for_order_book_diffs(self):
        q = asyncio.Queue()
        self.run_async(self.data_source.listen_for_order_book_diffs(self.ev_loop, q))

        first_event = q.get_nowait()
        second_event = q.get_nowait()
        third_event = q.get_nowait()
        fourth_event = q.get_nowait()

        recv_events = [first_event, second_event, third_event, fourth_event]

        for event in recv_events:
            # Validate the data inject into async queue is in order book message type
            self.assertIsInstance(event, BeaxyOrderBookMessage)

            # Validate the event type is equal to DIFF
            self.assertEqual(event.type, OrderBookMessageType.DIFF)

            # Validate the actual content injected is dict type
            self.assertIsInstance(event.content, dict)

    def test_listen_for_trades(self):
        q = asyncio.Queue()
        self.run_async(self.data_source.listen_for_trades(self.ev_loop, q))

        first_event = q.get_nowait()
        self.assertIsInstance(first_event, BeaxyOrderBookMessage)

        # Validate the event type is equal to DIFF
        self.assertEqual(first_event.type, OrderBookMessageType.DIFF)

        # Validate the actual content injected is dict type
        self.assertIsInstance(first_event.content, dict)
