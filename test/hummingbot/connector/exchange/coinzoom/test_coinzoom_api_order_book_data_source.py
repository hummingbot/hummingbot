import asyncio
import json
from dateutil.parser import parse as dateparse
from decimal import Decimal
from typing import Awaitable
from unittest.mock import patch, AsyncMock

from aioresponses import aioresponses
from unittest import TestCase

from hummingbot.connector.exchange.coinzoom.coinzoom_api_order_book_data_source import CoinzoomAPIOrderBookDataSource
from hummingbot.connector.exchange.coinzoom.coinzoom_constants import Constants
from hummingbot.connector.exchange.coinzoom.coinzoom_order_book import CoinzoomOrderBook
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


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
        self.listening_task = None
        self.data_source = CoinzoomAPIOrderBookDataSource(
            throttler=self.throttler,
            trading_pairs=[self.trading_pair])
        self.mocking_assistant = NetworkMockingAssistant()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

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

    @patch("websockets.connect", new_callable=AsyncMock)
    def test_listen_for_trades(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        received_messages = asyncio.Queue()

        message = {"ts": [f"{self.base_asset}/{self.quote_asset}", 8772.05, 0.01, "2020-01-16T21:02:23Z"]}

        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_trades(ev_loop=asyncio.get_event_loop(), output=received_messages))

        self.mocking_assistant.add_websocket_text_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(message))
        trade_message = self.async_run_with_timeout(received_messages.get())

        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual(int(dateparse("2020-01-16T21:02:23Z").timestamp() * 1e3), trade_message.timestamp)
        self.assertEqual(trade_message.timestamp, trade_message.trade_id)
        self.assertEqual(self.trading_pair, trade_message.trading_pair)

    @patch("hummingbot.connector.exchange.coinzoom.coinzoom_api_order_book_data_source.CoinzoomAPIOrderBookDataSource._time")
    @patch("websockets.connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diff(self, ws_connect_mock, time_mock):
        time_mock.return_value = 1234567890
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        received_messages = asyncio.Queue()

        message = {"oi": f"{self.base_asset}/{self.quote_asset}",
                   "b": [["9"],
                         ["5"],
                         ["7", 7193.27, 6.95094164],
                         ["8", 7196.15, 0.69481598]],
                   "s": [["2"],
                         ["1"],
                         ["4", 7222.08, 6.92321326],
                         ["6", 7219.2, 0.69259752]]}

        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_order_book_diffs(ev_loop=asyncio.get_event_loop(), output=received_messages))

        self.mocking_assistant.add_websocket_text_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(message))
        diff_message = self.async_run_with_timeout(received_messages.get())

        self.assertEqual(OrderBookMessageType.DIFF, diff_message.type)
        self.assertEqual(1234567890 * 1e3, diff_message.timestamp)
        self.assertEqual(diff_message.timestamp, diff_message.update_id)
        self.assertEqual(-1, diff_message.trade_id)
        self.assertEqual(self.trading_pair, diff_message.trading_pair)
