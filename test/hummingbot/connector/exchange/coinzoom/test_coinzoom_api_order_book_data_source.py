import asyncio
import json
from decimal import Decimal
from typing import Awaitable

from aioresponses import aioresponses
from unittest import TestCase

from hummingbot.connector.exchange.coinzoom.coinzoom_api_order_book_data_source import CoinzoomAPIOrderBookDataSource
from hummingbot.connector.exchange.coinzoom.coinzoom_constants import Constants
from hummingbot.connector.exchange.coinzoom.coinzoom_order_book import CoinzoomOrderBook
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class CoinzoomAPIOrderBookDataSourceTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.api_key = "testKey"
        cls.api_secret_key = "testSecretKey"
        cls.username = "testUsername"
        cls.throttler = AsyncThrottler(Constants.RATE_LIMITS)

    def setUp(self) -> None:
        super().setUp()
        self.data_source = CoinzoomAPIOrderBookDataSource(
            throttler=self.throttler,
            trading_pairs=[self.trading_pair])

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @staticmethod
    def _register_sent_request(requests_list, url, **kwargs):
        requests_list.append((url, kwargs))

    @aioresponses()
    def test_get_last_traded_prices(self, mock_api):
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['TICKER']}"
        resp = {f"{self.base_asset}_{self.quote_asset}": {"last_price": 51234.56}}
        mock_api.get(url, body=json.dumps(resp))

        results = self.async_run_with_timeout(CoinzoomAPIOrderBookDataSource.get_last_traded_prices(
            trading_pairs=[self.trading_pair],
            throttler=self.throttler))

        self.assertIn(self.trading_pair, results)
        self.assertEqual(Decimal("51234.56"), results[self.trading_pair])

    @aioresponses()
    def test_fetch_trading_pairs(self, mock_api):
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['SYMBOL']}"
        resp = [{"symbol": f"{self.base_asset}/{self.quote_asset}"},
                {"symbol": "BTC/USDT"}]
        mock_api.get(url, body=json.dumps(resp))

        results = self.async_run_with_timeout(CoinzoomAPIOrderBookDataSource.fetch_trading_pairs(
            throttler=self.throttler))

        self.assertIn(self.trading_pair, results)
        self.assertIn("BTC-USDT", results)

    @aioresponses()
    def test_get_new_order_book(self, mock_api):
        url = f"{Constants.REST_URL}/" \
              f"{Constants.ENDPOINT['ORDER_BOOK'].format(trading_pair=self.base_asset+'_'+self.quote_asset)}"
        resp = {"timestamp": 1234567899,
                "bids": [],
                "asks": []}
        mock_api.get(url, body=json.dumps(resp))

        order_book: CoinzoomOrderBook = self.async_run_with_timeout(
            self.data_source.get_new_order_book(self.trading_pair))

        self.assertEqual(1234567899, order_book.snapshot_uid)
