import aiohttp
import asyncio
import re
import ujson
import unittest

import hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_constants as CONSTANTS

from aioresponses import aioresponses
from typing import Awaitable, Optional
from unittest.mock import AsyncMock, patch

from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_api_order_book_data_source import (
    DydxPerpetualAPIOrderBookDataSource,
)
from hummingbot.core.data_type.order_book import OrderBook
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class DydxPerpetualAPIOrderBookDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []
        self.async_task: Optional[asyncio.Task] = None

        self.data_source = DydxPerpetualAPIOrderBookDataSource(trading_pairs=[self.trading_pair])

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        self.async_task and self.async_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_get_shared_client_not_shared_client_provided(self):
        self.assertIsNone(self.data_source._shared_client)
        self.assertIsInstance(self.data_source._get_shared_client(), aiohttp.ClientSession)

    def test_get_shared_client_shared_client_provided(self):
        aiohttp_client = aiohttp.ClientSession()
        self.data_source._shared_client = aiohttp_client
        self.assertEqual(self.data_source._get_shared_client(), aiohttp_client)

    @aioresponses()
    def test_get_snapshot_raise_io_error(self, mock_api):
        url = CONSTANTS.DYDX_REST_URL + CONSTANTS.SNAPSHOT_URL + "/" + self.trading_pair
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400, body=ujson.dumps({}))

        with self.assertRaisesRegex(
            IOError, f"Error fetching dydx market snapshot for {self.trading_pair}. " f"HTTP status is 400."
        ):
            self.async_run_with_timeout(self.data_source.get_snapshot(self.trading_pair))

    @aioresponses()
    def test_get_snapshot_successful(self, mock_api):
        url = CONSTANTS.DYDX_REST_URL + CONSTANTS.SNAPSHOT_URL + "/" + self.trading_pair
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "asks": [{"size": "2.0", "price": "20.0"}],
            "bids": [{"size": "1.0", "price": "10.0"}],
        }
        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        result = self.async_run_with_timeout(self.data_source.get_snapshot(self.trading_pair))

        self.assertEqual(mock_response["asks"][0]["size"], result["asks"][0]["size"])
        self.assertEqual(mock_response["asks"][0]["price"], result["asks"][0]["price"])
        self.assertEqual(mock_response["bids"][0]["size"], result["bids"][0]["size"])
        self.assertEqual(mock_response["bids"][0]["price"], result["bids"][0]["price"])
        self.assertEqual(self.trading_pair, result["trading_pair"])

    @aioresponses()
    def test_get_new_order_book(self, mock_api):
        url = CONSTANTS.DYDX_REST_URL + CONSTANTS.SNAPSHOT_URL + "/" + self.trading_pair
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "asks": [{"size": "2.0", "price": "20.0"}],
            "bids": [{"size": "1.0", "price": "10.0"}],
        }
        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        result = self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))
        self.assertIsInstance(result, OrderBook)
        self.assertEqual(1, len(list(result.bid_entries())))
        self.assertEqual(1, len(list(result.ask_entries())))
        self.assertEqual(float(mock_response["bids"][0]["price"]), list(result.bid_entries())[0].price)
        self.assertEqual(float(mock_response["bids"][0]["size"]), list(result.bid_entries())[0].amount)
        self.assertEqual(float(mock_response["asks"][0]["price"]), list(result.ask_entries())[0].price)
        self.assertEqual(float(mock_response["asks"][0]["size"]), list(result.ask_entries())[0].amount)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_create_websocket_connection_raised_cancelled(self, ws_connect_mock):
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source._create_websocket_connection())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_create_websocket_connection_logs_exception(self, ws_connect_mock):
        ws_connect_mock.side_effect = Exception("TEST ERROR")

        with self.assertRaisesRegex(Exception, "TEST ERROR"):
            self.async_run_with_timeout(self.data_source._create_websocket_connection())

        self.assertTrue(self._is_logged(
            "NETWORK", "Unexpected error occured connecting to dydx_perpetual WebSocket API. (TEST ERROR)"
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_user_stream_data_source.DydxPerpetualUserStreamDataSource._sleep")
    def test_listen_for_subcriptions_raises_cancelled_exception(self, _, ws_connect_mock):
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_subscriptions())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_auth.DydxPerpetualAuth.get_ws_auth_params")
    @patch("hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_user_stream_data_source.DydxPerpetualUserStreamDataSource._sleep")
    def test_listen_for_user_stream_raises_logs_exception(self, mock_sleep, mock_auth, ws_connect_mock):
        mock_sleep.side_effect = lambda: (
            self.ev_loop.run_until_complete(asyncio.sleep(0.5))
        )
        mock_auth.return_value = {}
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.receive.side_effect = lambda: self._create_exception_and_unlock_test_with_event(
            Exception("TEST ERROR")
        )
        self.async_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.async_run_with_timeout(self.resume_test_event.wait(), 1.0)

        self.assertTrue(
            self._is_logged(
                "ERROR", "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."
            )
        )
