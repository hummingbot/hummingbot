

import unittest

from hummingbot.market.okex.okex_api_order_book_data_source import OKExAPIOrderBookDataSource
from unittest import mock
import asyncio
import aiohttp

from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from typing import (
    Any,
    Dict,
)


# EXAMPLE_MARKET_DATA = [
#   {
#     "best_ask": "0.004693",
#     "best_bid": "0.004692",
#     "instrument_id": "LTC-BTC",
#     "product_id": "LTC-BTC",
#     "last": "0.004692",
#     "last_qty": "10.612",
#     "ask": "0.004693",
#     "best_ask_size": "225",
#     "bid": "0.004692",
#     "best_bid_size": "14.528379",
#     "open_24h": "0.00461",
#     "high_24h": "0.004715",
#     "low_24h": "0.004518",
#     "base_volume_24h": "71184.164676",
#     "timestamp": "2020-07-21T16:04:48.369Z",
#     "quote_volume_24h": "329.350827"
#   },
#   {
#     "best_ask": "0.02613",
#     "best_bid": "0.02612",
#     "instrument_id": "ETH-BTC",
#     "product_id": "ETH-BTC",
#     "last": "0.02612",
#     "last_qty": "2.866",
#     "ask": "0.02613",
#     "best_ask_size": "111.276812",
#     "bid": "0.02612",
#     "best_bid_size": "138.068802",
#     "open_24h": "0.02593",
#     "high_24h": "0.02613",
#     "low_24h": "0.02558",
#     "base_volume_24h": "27903.348408",
#     "timestamp": "2020-07-21T16:04:04.643Z",
#     "quote_volume_24h": "722.467909"
#   }
# ]

trading_pairs = ['CELO-USDT', 'BTC-USDT']

class AsyncMock(mock.MagicMock):
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)


class TestOKExAPIOrderBookDataSource(unittest.TestCase):
    def setUp(self):
        self.mocked_trading_pairs = ["BTCUSDT", "ETHUSDT"]
        self.order_book_data_source = OKExAPIOrderBookDataSource(self.mocked_trading_pairs)

    @unittest.skip("skipping, REMOVE ME")
    def test_example_market(self):
        ev_loop = asyncio.get_event_loop()
        # TODO this is currently executing the call, how to mock this?
        restult = ev_loop.run_until_complete(OKExAPIOrderBookDataSource.get_active_exchange_markets())
        print(restult)

        #assert False
    
    @unittest.skip("skipping, REMOVE ME")
    def test_get_snapshot(self):
        ev_loop = asyncio.get_event_loop()
        # TODO this is currently executing the call, how to mock this?
        restult = ev_loop.run_until_complete(self.get_snapshot())

    async def get_snapshot(self):
        async with aiohttp.ClientSession() as client:

            snapshot: Dict[str, Any] = await self.order_book_data_source.get_snapshot(client, 'BTCUSDT')
            return snapshot

    @unittest.skip("skipping, REMOVE ME")
    def test_get_tracking_pairs(self):
        
        tracking_pairs = asyncio.get_event_loop().run_until_complete(self.order_book_data_source.get_tracking_pairs())

        # Validate the number of tracking pairs is equal to the number of trading pairs received
        self.assertEqual(len(self.mocked_trading_pairs), len(tracking_pairs))

        # Make sure the entry key in tracking pairs matches with what's in the trading pairs
        for trading_pair, tracking_pair_obj in zip(self.mocked_trading_pairs, list(tracking_pairs.keys())):
            self.assertEqual(trading_pair, tracking_pair_obj)

        # Validate the data type for each tracking pair value is OrderBookTrackerEntry
        for order_book_tracker_entry in tracking_pairs.values():
            self.assertIsInstance(order_book_tracker_entry, OrderBookTrackerEntry)

        # Validate the order book tracker entry trading_pairs are valid
        for trading_pair, order_book_tracker_entry in zip(self.mocked_trading_pairs, tracking_pairs.values()):
            self.assertEqual(order_book_tracker_entry.trading_pair, trading_pair)


    async def listen_for_trades(self):
        q = asyncio.Queue()
        
        # mock to have only CELO
        async def mock_internal_get_trading_pairs():
            return ['BTC-USDT']
        self.order_book_data_source.internal_get_trading_pairs = mock_internal_get_trading_pairs

        task = asyncio.create_task(self.order_book_data_source.listen_for_trades(None, q))

        await asyncio.sleep(10)
        task.cancel()
        
        self.assertFalse(q.empty())

    @unittest.skip("skipping, REMOVE ME")
    def test_listen_for_trades(self):
        # WARNING: this test will fail if there are no trades in 10s in the BTC-USDT pair
        q = asyncio.Queue()
        asyncio.get_event_loop().run_until_complete(self.listen_for_trades())
        
    @unittest.skip("skipping, REMOVE ME")
    async def listen_for_order_book_diffs(self):
        q = asyncio.Queue()
        
        # mock to have only CELO
        async def mock_internal_get_trading_pairs():
            return ['BTC-USDT']
        self.order_book_data_source.internal_get_trading_pairs = mock_internal_get_trading_pairs

        task = asyncio.create_task(self.order_book_data_source.listen_for_order_book_diffs(None, q))

        await asyncio.sleep(10)
        task.cancel()
        
        self.assertFalse(q.empty())

    @unittest.skip("skipping, REMOVE ME")
    def test_listen_for_order_book_diffs(self):
        q = asyncio.Queue()
        asyncio.get_event_loop().run_until_complete(self.listen_for_order_book_diffs())


    def test_get_last_traded_prices(self):
        out = asyncio.get_event_loop().run_until_complete(self.order_book_data_source.get_last_traded_prices(trading_pairs))

        self.assertTrue('CELO-USDT' in out)
        self.assertTrue(type(out['CELO-USDT']) is float)
        