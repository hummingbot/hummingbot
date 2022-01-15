import unittest
import conf

from hummingbot.connector.exchange.btc_markets.btc_markets_api_order_book_data_source \
    import BtcMarketsAPIOrderBookDataSource
from hummingbot.connector.exchange.btc_markets.btc_markets_auth import BtcMarketsAuth
from unittest import mock
import asyncio
import aiohttp
from typing import (
    Any,
    Dict,
)

trading_pairs = ['USDT-AUD', 'BTC-AUD']


class AsyncMock(mock.MagicMock):
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)


class TestBtcMarketsAPIOrderBookDataSource(unittest.TestCase):
    def setUp(self):
        self.mocked_trading_pairs = ["BTC-AUD"]
        self.order_book_data_source = BtcMarketsAPIOrderBookDataSource(self.mocked_trading_pairs)
        api_key = conf.btc_markets_api_key
        secret_key = conf.btc_markets_secret_key
        self.auth = BtcMarketsAuth(api_key, secret_key)

    def test_fetch_trading_pairs(self):
        ev_loop = asyncio.get_event_loop()
        # TODO this is currently executing the call, how to mock this?
        ev_loop.run_until_complete(BtcMarketsAPIOrderBookDataSource.fetch_trading_pairs())

    def test_get_order_book_data(self):
        ev_loop = asyncio.get_event_loop()
        self.mocked_trading_pairs = "BTC-AUD"
        # TODO this is currently executing the call, how to mock this?
        ev_loop.run_until_complete(BtcMarketsAPIOrderBookDataSource.get_order_book_data(self.mocked_trading_pairs))

    def test_get_snapshot(self):
        ev_loop = asyncio.get_event_loop()
        # TODO this is currently executing the call, how to mock this?
        ev_loop.run_until_complete(self.get_snapshot())

    async def get_snapshot(self):
        async with aiohttp.ClientSession():
            snapshot: Dict[str, Any] = await self.order_book_data_source.get_order_book_data('BTC-AUD')
            return snapshot

    async def listen_for_trades(self):
        q = asyncio.Queue()

        # mock to have only BTC-AUD
        async def mock_internal_get_trading_pairs():
            return ['BTC-AUD']
        self.order_book_data_source.internal_get_trading_pairs = mock_internal_get_trading_pairs

        task = asyncio.create_task(self.order_book_data_source.listen_for_trades(None, q))

        await asyncio.sleep(30)
        task.cancel()

    #    self.assertTrue(q.empty())

    def test_listen_for_trades(self):
        # WARNING: this test will fail if there are no trades in 30s in the BTC-AUD pair
        # q = asyncio.Queue()
        asyncio.get_event_loop().run_until_complete(self.listen_for_trades())

    async def listen_for_order_book_diffs(self):
        q = asyncio.Queue()

        async def mock_internal_fetch_trading_pairs():
            return 'BTC-AUD'
        self.order_book_data_source.fetch_trading_pairs = mock_internal_fetch_trading_pairs

        task = asyncio.create_task(self.order_book_data_source.listen_for_order_book_diffs(None, q))

        await asyncio.sleep(10)
        task.cancel()

        self.assertFalse(q.empty())

    def test_listen_for_order_book_diffs(self):
        # q = asyncio.Queue()
        asyncio.get_event_loop().run_until_complete(self.listen_for_order_book_diffs())

    def test_get_last_traded_prices(self):
        out = asyncio.get_event_loop().run_until_complete(self.order_book_data_source.get_last_traded_prices(trading_pairs))

        self.assertTrue('USDT-AUD' in out)
        self.assertTrue(type(out['USDT-AUD']) is float)
