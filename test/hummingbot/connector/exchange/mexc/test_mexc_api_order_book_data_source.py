import unittest
import asyncio
from collections import deque, Awaitable

import ujson

import hummingbot.connector.exchange.mexc.mexc_constants as CONSTANTS

from unittest.mock import patch, AsyncMock
from typing import (
    Any,
    Dict,
)

from hummingbot.connector.exchange.mexc.mexc_api_order_book_data_source import MexcAPIOrderBookDataSource

from hummingbot.core.data_type.order_book import OrderBook

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.core.utils.async_utils import safe_ensure_future
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class MexcAPIOrderBookDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.instrument_id = 1

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None

        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.data_source = MexcAPIOrderBookDataSource(throttler=self.throttler, trading_pairs=[self.trading_pair])
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _raise_exception(self, exception_class):
        raise exception_class

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch("aiohttp.ClientSession.get")
    def test_get_last_traded_prices(self, mock_api):
        self.mocking_assistant.configure_http_request_mock(mock_api)
        mock_response: Dict[Any] = {"code": 200, "data": [
            {"symbol": "BTC_USDT", "volume": "1076.002782", "high": "59387.98", "low": "57009", "bid": "57920.98",
             "ask": "57921.03", "open": "57735.92", "last": "57902.52", "time": 1637898900000,
             "change_rate": "0.00288555"}]}
        self.mocking_assistant.add_http_response(mock_api, 200, mock_response)

        results = self.async_run_with_timeout(
            asyncio.gather(self.data_source.get_last_traded_prices([self.trading_pair])))
        results: Dict[str, Any] = results[0]

        self.assertEqual(results[self.trading_pair], 57902.52)

    @patch("aiohttp.ClientSession.get")
    def test_fetch_trading_pairs_with_error_status_in_response(self, mock_api):
        self.mocking_assistant.configure_http_request_mock(mock_api)
        mock_response = {}
        self.mocking_assistant.add_http_response(mock_api, 100, mock_response)

        result = self.async_run_with_timeout(self.data_source.fetch_trading_pairs())
        self.assertEqual(0, len(result))

    @patch("aiohttp.ClientSession.get")
    def test_get_order_book_data(self, mock_api):
        self.mocking_assistant.configure_http_request_mock(mock_api)
        mock_response = {"code": 200, "data": {"asks": [{"price": "57974.06", "quantity": "0.247421"}],
                                               "bids": [{"price": "57974.01", "quantity": "0.201635"}],
                                               "version": "562370278"}}
        self.mocking_assistant.add_http_response(mock_api, 200, mock_response)

        results = self.async_run_with_timeout(
            asyncio.gather(self.data_source.get_snapshot(self.data_source._shared_client, self.trading_pair)))
        result = results[0]

        self.assertTrue("asks" in result)
        self.assertGreaterEqual(len(result), 0)
        self.assertEqual(mock_response.get("data"), result)

    @patch("aiohttp.ClientSession.get")
    def test_get_order_book_data_raises_exception_when_response_has_error_code(self, mock_api):
        self.mocking_assistant.configure_http_request_mock(mock_api)

        mock_response = {"Erroneous response"}
        self.mocking_assistant.add_http_response(mock_api, 100, mock_response)

        with self.assertRaises(IOError) as context:
            self.async_run_with_timeout(self.data_source.get_snapshot(self.data_source._shared_client, self.trading_pair))

        self.assertEqual(str(context.exception),
                         f'Error fetching MEXC market snapshot for {self.trading_pair.replace("-", "_")}. '
                         f'HTTP status is {100}.')

    @patch("aiohttp.ClientSession.get")
    def test_get_new_order_book(self, mock_api):
        self.mocking_assistant.configure_http_request_mock(mock_api)

        mock_response = {"code": 200, "data": {"asks": [{"price": "57974.06", "quantity": "0.247421"}],
                                               "bids": [{"price": "57974.01", "quantity": "0.201635"}],
                                               "version": "562370278"}}
        self.mocking_assistant.add_http_response(mock_api, 200, mock_response)

        results = self.async_run_with_timeout(
            asyncio.gather(self.data_source.get_new_order_book(self.trading_pair)))
        result: OrderBook = results[0]

        self.assertTrue(type(result) == OrderBook)

    @patch("aiohttp.ClientSession.get")
    def test_listen_for_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        mock_api.side_effect = asyncio.CancelledError

        msg_queue: asyncio.Queue = asyncio.Queue()
        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

        self.assertEqual(msg_queue.qsize(), 0)

    @patch("hummingbot.connector.exchange.mexc.mexc_api_order_book_data_source.MexcAPIOrderBookDataSource._sleep")
    @patch("aiohttp.ClientSession.get")
    def test_listen_for_snapshots_successful(self, mock_api, mock_sleep):
        self.mocking_assistant.configure_http_request_mock(mock_api)

        # the queue and the division by zero error are used just to synchronize the test
        sync_queue = deque()
        sync_queue.append(1)

        mock_response = {"code": 200, "data": {"asks": [{"price": "57974.06", "quantity": "0.247421"}],
                                               "bids": [{"price": "57974.01", "quantity": "0.201635"}],
                                               "version": "562370278"}}
        self.mocking_assistant.add_http_response(mock_api, 200, mock_response)

        mock_sleep.side_effect = lambda delay: 1 / 0 if len(sync_queue) == 0 else sync_queue.pop()

        msg_queue: asyncio.Queue = asyncio.Queue()
        with self.assertRaises(ZeroDivisionError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue))
            self.async_run_with_timeout(self.listening_task)

        self.assertEqual(msg_queue.qsize(), 1)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_cancelled_when_subscribing(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.send_str.side_effect = asyncio.CancelledError()

        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, {'channel': 'push.personal.order'})

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_subscriptions()
            )
            self.async_run_with_timeout(self.listening_task)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_cancelled_when_listening(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        data = {'symbol': 'MX_USDT',
                'data': {'version': '44000093', 'bids': [{'p': '2.9311', 'q': '0.00', 'a': '0.00000000'}],
                         'asks': [{'p': '2.9311', 'q': '22720.37', 'a': '66595.6765'}]},
                'channel': 'push.depth'}
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, ujson.dumps(data))
        safe_ensure_future(self.data_source.listen_for_subscriptions())

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue))

        first_msg = self.async_run_with_timeout(msg_queue.get())
        self.assertTrue(first_msg.type == OrderBookMessageType.DIFF)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_websocket_connection_creation_raises_cancel_exception(self, mock_ws):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source._create_websocket_connection())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_websocket_connection_creation_raises_exception_after_loging(self, mock_ws):
        mock_ws.side_effect = Exception

        with self.assertRaises(Exception):
            self.async_run_with_timeout(self.data_source._create_websocket_connection())

        self.assertTrue(self._is_logged("NETWORK", 'Unexpected error occured connecting to mexc WebSocket API. ()'))
