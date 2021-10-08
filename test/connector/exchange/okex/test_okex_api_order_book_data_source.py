

import unittest

from hummingbot.connector.exchange.okex.okex_api_order_book_data_source import OkexAPIOrderBookDataSource
from unittest import mock
import asyncio
import aiohttp
from typing import (
    Any,
    Dict,
)

trading_pairs = ['CELO-USDT', 'BTC-USDT']


class AsyncMock(mock.MagicMock):
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)


class TestOkexAPIOrderBookDataSource(unittest.TestCase):
    def setUp(self):
        self.mocked_trading_pairs = ["BTC-USDT", "ETH-USDT"]
        self.order_book_data_source = OkexAPIOrderBookDataSource(self.mocked_trading_pairs)

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

        self.assertTrue(q.empty())

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
