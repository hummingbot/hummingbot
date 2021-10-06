import asyncio
import re
import ujson
import unittest

import hummingbot.connector.exchange.binance.binance_constants as CONSTANTS
import hummingbot.connector.exchange.binance.binance_utils as utils

from aioresponses.core import aioresponses
from typing import (
    Any,
    Dict,
    List,
)
from unittest.mock import AsyncMock, patch

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.connector.exchange.binance.binance_api_order_book_data_source import BinanceAPIOrderBookDataSource

from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class BinanceAPIOrderBookDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = "com"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.data_source = BinanceAPIOrderBookDataSource(trading_pairs=[self.trading_pair],
                                                         throttler=self.throttler,
                                                         domain=self.domain)
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _raise_exception(self, exception_class):
        raise exception_class

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _successfully_subscribed_event(self):
        resp = {
            "result": None,
            "id": 1
        }
        return resp

    def _trade_update_event(self):
        resp = {
            "e": "trade",
            "E": 123456789,
            "s": self.ex_trading_pair,
            "t": 12345,
            "p": "0.001",
            "q": "100",
            "b": 88,
            "a": 50,
            "T": 123456785,
            "m": True,
            "M": True
        }
        return resp

    def _order_diff_event(self):
        resp = {
            "e": "depthUpdate",
            "E": 123456789,
            "s": self.ex_trading_pair,
            "U": 157,
            "u": 160,
            "b": [["0.0024", "10"]],
            "a": [["0.0026", "100"]]
        }
        return resp

    def _snapshot_response(self):
        resp = {
            "lastUpdateId": 1027024,
            "bids": [
                [
                    "4.00000000",
                    "431.00000000"
                ]
            ],
            "asks": [
                [
                    "4.00000200",
                    "12.00000000"
                ]
            ]
        }
        return resp

    @aioresponses()
    def test_get_last_trade_prices(self, mock_api):
        url = utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response: Dict[str, Any] = {
            # Truncated Response
            "lastPrice": "100",
        }

        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        result: Dict[str, float] = self.ev_loop.run_until_complete(
            self.data_source.get_last_traded_prices(trading_pairs=[self.trading_pair],
                                                    throttler=self.throttler)
        )

        self.assertEqual(1, len(result))
        self.assertEqual(100, result[self.trading_pair])

    @aioresponses()
    @patch("hummingbot.connector.exchange.binance.binance_utils.convert_from_exchange_trading_pair")
    def test_get_all_mid_prices(self, mock_api, mock_utils):
        # Mocks binance_utils for BinanceOrderBook.diff_message_from_exchange()
        mock_utils.return_value = self.trading_pair
        url = utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response: List[Dict[str, Any]] = [{
            # Truncated Response
            "symbol": self.ex_trading_pair,
            "bidPrice": "99",
            "askPrice": "101",
        }]

        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        result: Dict[str, float] = self.ev_loop.run_until_complete(
            self.data_source.get_all_mid_prices()
        )

        self.assertEqual(1, len(result))
        self.assertEqual(100, result[self.trading_pair])

    @aioresponses()
    @patch("hummingbot.connector.exchange.binance.binance_utils.convert_from_exchange_trading_pair")
    def test_fetch_trading_pairs(self, mock_api, mock_utils):
        # Mocks binance_utils for BinanceOrderBook.diff_message_from_exchange()
        mock_utils.return_value = self.trading_pair
        url = utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response: Dict[str, Any] = {
            # Truncated Response
            "symbols":
            [
                {
                    "symbol": self.ex_trading_pair,
                    "status": "TRADING",
                    "baseAsset": self.base_asset,
                    "quoteAsset": self.quote_asset,
                },
            ]
        }

        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        result: Dict[str] = self.ev_loop.run_until_complete(
            self.data_source.fetch_trading_pairs()
        )

        self.assertEqual(1, len(result))
        self.assertTrue(self.trading_pair in result)

    @aioresponses()
    @patch("hummingbot.connector.exchange.binance.binance_utils.convert_from_exchange_trading_pair")
    def test_fetch_trading_pairs_exception_raised(self, mock_api, mock_utils):
        # Mocks binance_utils for BinanceOrderBook.diff_message_from_exchange()
        mock_utils.return_value = self.trading_pair
        url = utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=Exception)

        result: Dict[str] = self.ev_loop.run_until_complete(
            self.data_source.fetch_trading_pairs()
        )

        self.assertEqual(0, len(result))

    def test_get_throttler_instance(self):
        self.assertIsInstance(BinanceAPIOrderBookDataSource._get_throttler_instance(), AsyncThrottler)

    @aioresponses()
    def test_get_snapshot_successful(self, mock_api):
        url = utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, body=ujson.dumps(self._snapshot_response()))

        result: Dict[str, Any] = self.ev_loop.run_until_complete(
            self.data_source.get_snapshot(self.trading_pair)
        )

        self.assertEqual(self._snapshot_response(), result)

    @aioresponses()
    def test_get_snapshot_catch_exception(self, mock_api):
        url = utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            self.ev_loop.run_until_complete(
                self.data_source.get_snapshot(self.trading_pair)
            )

    @aioresponses()
    def test_get_new_order_book(self, mock_api):
        url = utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response: Dict[str, Any] = {
            "lastUpdateId": 1,
            "bids": [
                [
                    "4.00000000",
                    "431.00000000"
                ]
            ],
            "asks": [
                [
                    "4.00000200",
                    "12.00000000"
                ]
            ]
        }
        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        result: OrderBook = self.ev_loop.run_until_complete(
            self.data_source.get_new_order_book(self.trading_pair)
        )

        self.assertEqual(1, result.snapshot_uid)

    @patch("aiohttp.ClientSession.ws_connect")
    def test_create_websocket_connection_cancelled_when_connecting(self, mock_ws):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.ev_loop.run_until_complete(
                self.data_source._create_websocket_connection()
            )

    @patch("aiohttp.ClientSession.ws_connect")
    def test_create_websocket_connection_exception_raised(self, mock_ws):
        mock_ws.side_effect = Exception("TEST ERROR.")

        with self.assertRaises(Exception):
            self.ev_loop.run_until_complete(
                self.data_source._create_websocket_connection()
            )

        self.assertTrue(self._is_logged("NETWORK",
                                        "Unexpected error occured when connecting to WebSocket server. Error: TEST ERROR."))

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    def test_listen_for_trades_cancelled_when_connecting(self, mock_ws, _: AsyncMock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
            self.ev_loop.run_until_complete(self.listening_task)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_trades_exception_raised_when_connecting(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.side_effect = lambda **_: self._create_exception_and_unlock_test_with_event(Exception("TEST ERROR."))

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue)
        )

        self.ev_loop.run_until_complete(self.resume_test_event.wait())

        self.assertTrue(self._is_logged("NETWORK", "Unexpected error occured when connecting to WebSocket server. Error: TEST ERROR."))
        self.assertTrue(self._is_logged("ERROR", "Unexpected error with WebSocket connection. Retrying after 30 seconds..."))

    @patch("hummingbot.connector.exchange.binance.binance_api_order_book_data_source"
           ".BinanceAPIOrderBookDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_trades_cancelled_when_listening(self, mock_ws, _: AsyncMock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.receive_json.side_effect = lambda: (
            self._raise_exception(asyncio.CancelledError)
        )
        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
            self.ev_loop.run_until_complete(self.listening_task)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_trades_logs_exception(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.close.return_value = None

        incomplete_resp = {
            "m": 1,
            "i": 2,
        }
        self.mocking_assistant.add_websocket_json_message(mock_ws.return_value, incomplete_resp)
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue)
        )

        with self.assertRaises(asyncio.TimeoutError):
            self.ev_loop.run_until_complete(
                asyncio.wait_for(self.listening_task, 1)
            )

        self.assertTrue(self._is_logged("ERROR", "Unexpected error with WebSocket connection. Retrying after 30 seconds..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_trades_iter_message_throws_exception(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.receive_json.side_effect = lambda: self._raise_exception(Exception("TEST ERROR"))
        mock_ws.close.return_value = None

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue)
        )

        with self.assertRaises(asyncio.TimeoutError):
            self.ev_loop.run_until_complete(
                asyncio.wait_for(self.listening_task, 1)
            )
        self.assertTrue(self._is_logged("NETWORK", "Unexpected error occured when parsing websocket payload. Error: TEST ERROR"))
        self.assertTrue(self._is_logged("ERROR", "Unexpected error with WebSocket connection. Retrying after 30 seconds..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_trades_successful(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.close.return_value = None

        self.mocking_assistant.add_websocket_json_message(mock_ws.return_value, self._successfully_subscribed_event())
        self.mocking_assistant.add_websocket_json_message(mock_ws.return_value, self._trade_update_event())
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.ev_loop.run_until_complete(msg_queue.get())

        self.assertTrue(12345, msg.trade_id)

    @patch("hummingbot.connector.exchange.binance.binance_api_order_book_data_source"
           ".BinanceAPIOrderBookDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    def test_listen_for_order_book_diffs_cancelled_when_connecting(self, mock_ws, _: AsyncMock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
            self.ev_loop.run_until_complete(self.listening_task)

    @patch("hummingbot.connector.exchange.binance.binance_api_order_book_data_source"
           ".BinanceAPIOrderBookDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_cancelled_when_listening(self, mock_ws, _: AsyncMock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.receive_json.side_effect = lambda: (
            self._raise_exception(asyncio.CancelledError)
        )
        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
            self.ev_loop.run_until_complete(self.listening_task)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_logs_exception(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.close.return_value = None

        incomplete_resp = {
            "m": 1,
            "i": 2,
        }
        self.mocking_assistant.add_websocket_json_message(mock_ws.return_value, incomplete_resp)
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
        )

        with self.assertRaises(asyncio.TimeoutError):
            self.ev_loop.run_until_complete(
                asyncio.wait_for(self.listening_task, 1)
            )

        self.assertTrue(self._is_logged("ERROR", "Unexpected error with WebSocket connection. Retrying after 30 seconds..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_successful(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.close.return_value = None

        self.mocking_assistant.add_websocket_json_message(mock_ws.return_value, self._successfully_subscribed_event())
        self.mocking_assistant.add_websocket_json_message(mock_ws.return_value, self._order_diff_event())
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.ev_loop.run_until_complete(msg_queue.get())

        self.assertTrue(12345, msg.update_id)

    @aioresponses()
    def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        url = utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            self.ev_loop.run_until_complete(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, asyncio.Queue())
            )

    @aioresponses()
    def test_listen_for_order_book_snapshots_log_exception(self, mock_api):
        msg_queue: asyncio.Queue = asyncio.Queue()

        url = utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=Exception)

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )
        with self.assertRaises(asyncio.TimeoutError):
            self.ev_loop.run_until_complete(
                asyncio.wait_for(self.listening_task, 1)
            )

        self.assertTrue(self._is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}."))

    @aioresponses()
    def test_listen_for_order_book_snapshots_successful(self, mock_api,):
        msg_queue: asyncio.Queue = asyncio.Queue()
        url = utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, body=ujson.dumps(self._snapshot_response()))

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.ev_loop.run_until_complete(msg_queue.get())

        self.assertTrue(12345, msg.update_id)
