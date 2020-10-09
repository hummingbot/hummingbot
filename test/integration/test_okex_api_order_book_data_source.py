

import unittest

from hummingbot.connector.exchange.okex.okex_api_order_book_data_source import OkexAPIOrderBookDataSource
from unittest import mock
import asyncio
import aiohttp
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


class TestOkexAPIOrderBookDataSource(unittest.TestCase):
    def setUp(self):
        self.mocked_trading_pairs = ["BTC-USDT", "ETH-USDT"]
        self.order_book_data_source = OkexAPIOrderBookDataSource(self.mocked_trading_pairs)

    def test_example_market(self):
        ev_loop = asyncio.get_event_loop()
        # TODO this is currently executing the call, how to mock this?
        ev_loop.run_until_complete(OkexAPIOrderBookDataSource.get_active_exchange_markets())

    def test_get_snapshot(self):
        ev_loop = asyncio.get_event_loop()
        # TODO this is currently executing the call, how to mock this?
        ev_loop.run_until_complete(self.get_snapshot())

    async def get_snapshot(self):
        async with aiohttp.ClientSession() as client:

            snapshot: Dict[str, Any] = await self.order_book_data_source.get_snapshot(client, 'BTC-USDT')
            return snapshot

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

    def test_listen_for_trades(self):
        # WARNING: this test will fail if there are no trades in 10s in the BTC-USDT pair
        # q = asyncio.Queue()
        asyncio.get_event_loop().run_until_complete(self.listen_for_trades())

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

    def test_listen_for_order_book_diffs(self):
        # q = asyncio.Queue()
        asyncio.get_event_loop().run_until_complete(self.listen_for_order_book_diffs())

    def test_get_last_traded_prices(self):
        out = asyncio.get_event_loop().run_until_complete(self.order_book_data_source.get_last_traded_prices(trading_pairs))

        self.assertTrue('CELO-USDT' in out)
        self.assertTrue(type(out['CELO-USDT']) is float)
