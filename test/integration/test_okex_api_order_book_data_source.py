

import unittest

from hummingbot.market.okex.okex_api_order_book_data_source import OKExAPIOrderBookDataSource
from unittest import mock
import asyncio
import aiohttp

EXAMPLE_MARKET_DATA = [
  {
    "best_ask": "0.004693",
    "best_bid": "0.004692",
    "instrument_id": "LTC-BTC",
    "product_id": "LTC-BTC",
    "last": "0.004692",
    "last_qty": "10.612",
    "ask": "0.004693",
    "best_ask_size": "225",
    "bid": "0.004692",
    "best_bid_size": "14.528379",
    "open_24h": "0.00461",
    "high_24h": "0.004715",
    "low_24h": "0.004518",
    "base_volume_24h": "71184.164676",
    "timestamp": "2020-07-21T16:04:48.369Z",
    "quote_volume_24h": "329.350827"
  },
  {
    "best_ask": "0.02613",
    "best_bid": "0.02612",
    "instrument_id": "ETH-BTC",
    "product_id": "ETH-BTC",
    "last": "0.02612",
    "last_qty": "2.866",
    "ask": "0.02613",
    "best_ask_size": "111.276812",
    "bid": "0.02612",
    "best_bid_size": "138.068802",
    "open_24h": "0.02593",
    "high_24h": "0.02613",
    "low_24h": "0.02558",
    "base_volume_24h": "27903.348408",
    "timestamp": "2020-07-21T16:04:04.643Z",
    "quote_volume_24h": "722.467909"
  }
]

class AsyncMock(mock.MagicMock):
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)


class TestOKExAPIOrderBookDataSource(unittest.TestCase):
    def setUp(self):
        pass

    def test_example_market(self):
        ev_loop = asyncio.get_event_loop()
        # TODO this is currently executing the call, how to mock this?
        restult = ev_loop.run_until_complete(OKExAPIOrderBookDataSource.get_active_exchange_markets())
        print(restult)

        #assert False
    
    def test_get_snapshot(self):
        ev_loop = asyncio.get_event_loop()
        # TODO this is currently executing the call, how to mock this?
        restult = ev_loop.run_until_complete(self.get_snapshot())

    async def get_snapshot(self):
        self.order_book_data_source = OKExAPIOrderBookDataSource(["BTCUSDT", "ETHUSDT"])

        async with aiohttp.ClientSession() as client:

            snapshot: Dict[str, Any] = await self.order_book_data_source.get_snapshot(client, 'BTCUSDT')
            return snapshot