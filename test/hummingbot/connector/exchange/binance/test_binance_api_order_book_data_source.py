import asyncio
import ujson
import unittest


import hummingbot.connector.exchange.binance.binance_constants as CONSTANTS

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
        return ujson.dumps(resp)

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
        return ujson.dumps(resp)

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

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_get_last_trade_prices(self, mock_api):
        self.mocking_assistant.configure_http_request_mock(mock_api)

        mock_response: Dict[str, Any] = {
            # Truncated Response
            "lastPrice": "100",
        }

        self.mocking_assistant.add_http_response(mock_api, 200, mock_response)

        result: Dict[str, float] = self.ev_loop.run_until_complete(
            self.data_source.get_last_traded_prices(trading_pairs=[self.trading_pair],
                                                    throttler=self.throttler)
        )

        self.assertEqual(1, len(result))
        self.assertEqual(100, result[self.trading_pair])

    @patch("hummingbot.connector.exchange.binance.binance_utils.convert_from_exchange_trading_pair")
    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_get_all_mid_prices(self, mock_api, mock_utils):
        # Mocks binance_utils for BinanceOrderBook.diff_message_from_exchange()
        mock_utils.return_value = self.trading_pair
        self.mocking_assistant.configure_http_request_mock(mock_api)

        mock_response: List[Dict[str, Any]] = [{
            # Truncated Response
            "symbol": self.ex_trading_pair,
            "bidPrice": "99",
            "askPrice": "101",
        }]

        self.mocking_assistant.add_http_response(mock_api, 200, mock_response)

        result: Dict[str, float] = self.ev_loop.run_until_complete(
            self.data_source.get_all_mid_prices()
        )

        self.assertEqual(1, len(result))
        self.assertEqual(100, result[self.trading_pair])

    @patch("hummingbot.connector.exchange.binance.binance_utils.convert_from_exchange_trading_pair")
    @patch("aiohttp.ClientSession.get")
    def test_fetch_trading_pairs(self, mock_api, mock_utils):
        # Mocks binance_utils for BinanceOrderBook.diff_message_from_exchange()
        mock_utils.return_value = self.trading_pair
        self.mocking_assistant.configure_http_request_mock(mock_api)

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

        self.mocking_assistant.add_http_response(mock_api, 200, mock_response)

        result: Dict[str] = self.ev_loop.run_until_complete(
            self.data_source.fetch_trading_pairs()
        )

        self.assertEqual(1, len(result))
        self.assertTrue(self.trading_pair in result)

    def test_get_throttler_instance(self):
        self.assertIsInstance(BinanceAPIOrderBookDataSource._get_throttler_instance(), AsyncThrottler)

    @patch("aiohttp.ClientSession.get")
    def test_get_snapshot_successful(self, mock_api):
        self.mocking_assistant.configure_http_request_mock(mock_api)

        self.mocking_assistant.add_http_response(mock_api, 200, self._snapshot_response())

        result: Dict[str, Any] = self.ev_loop.run_until_complete(
            self.data_source.get_snapshot(self.trading_pair)
        )

        self.assertEqual(self._snapshot_response(), result)

    @patch("aiohttp.ClientSession.get")
    def test_get_snapshot_catch_exception(self, mock_api):
        self.mocking_assistant.configure_http_request_mock(mock_api)

        self.mocking_assistant.add_http_response(mock_api, 400, {})
        with self.assertRaises(IOError):
            self.ev_loop.run_until_complete(
                self.data_source.get_snapshot(self.trading_pair)
            )

    @patch("aiohttp.ClientSession.get")
    def test_get_new_order_book(self, mock_api):
        self.mocking_assistant.configure_http_request_mock(mock_api)

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
        self.mocking_assistant.add_http_response(mock_api, 200, mock_response)

        result: OrderBook = self.ev_loop.run_until_complete(
            self.data_source.get_new_order_book(self.trading_pair)
        )

        self.assertEqual(1, result.snapshot_uid)

    @patch("websockets.connect")
    def test_listen_for_trades_cancelled_when_connecting(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
            self.ev_loop.run_until_complete(self.listening_task)

    @patch("websockets.connect", new_callable=AsyncMock)
    def test_listen_for_trades_cancelled_when_listening(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.recv.side_effect = lambda: (
            self._raise_exception(asyncio.CancelledError)
        )
        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
            self.ev_loop.run_until_complete(self.listening_task)

    @patch("websockets.connect", new_callable=AsyncMock)
    def test_listen_for_trades_logs_exception(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.close.return_value = None

        incomplete_resp = {
            "m": 1,
            "i": 2,
        }
        self.mocking_assistant.add_websocket_text_message(mock_ws.return_value, ujson.dumps(incomplete_resp))
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue)
        )

        with self.assertRaises(asyncio.TimeoutError):
            self.ev_loop.run_until_complete(
                asyncio.wait_for(self.listening_task, 1)
            )

        self.assertTrue(self._is_logged("ERROR", "Unexpected error with WebSocket connection. Retrying after 30 seconds..."))

    @patch("websockets.connect", new_callable=AsyncMock)
    def test_listen_for_trades_successful(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.close.return_value = None

        self.mocking_assistant.add_websocket_text_message(mock_ws.return_value, self._trade_update_event())
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.ev_loop.run_until_complete(msg_queue.get())

        self.assertTrue(12345, msg.trade_id)

    @patch("websockets.connect")
    def test_listen_for_order_book_diffs_cancelled_when_connecting(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
            self.ev_loop.run_until_complete(self.listening_task)

    @patch("websockets.connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_cancelled_when_listening(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.recv.side_effect = lambda: (
            self._raise_exception(asyncio.CancelledError)
        )
        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
            self.ev_loop.run_until_complete(self.listening_task)

    @patch("websockets.connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_logs_exception(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.close.return_value = None

        incomplete_resp = {
            "m": 1,
            "i": 2,
        }
        self.mocking_assistant.add_websocket_text_message(mock_ws.return_value, ujson.dumps(incomplete_resp))
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
        )

        with self.assertRaises(asyncio.TimeoutError):
            self.ev_loop.run_until_complete(
                asyncio.wait_for(self.listening_task, 1)
            )

        self.assertTrue(self._is_logged("ERROR", "Unexpected error with WebSocket connection. Retrying after 30 seconds..."))

    @patch("websockets.connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_successful(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.close.return_value = None

        self.mocking_assistant.add_websocket_text_message(mock_ws.return_value, self._order_diff_event())
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.ev_loop.run_until_complete(msg_queue.get())

        self.assertTrue(12345, msg.update_id)

    @patch("aiohttp.ClientSession.get")
    def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        mock_api.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.ev_loop.run_until_complete(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, asyncio.Queue())
            )

    @patch("aiohttp.ClientSession.get")
    def test_listen_for_order_book_snapshots_log_exception(self, mock_api):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_api.side_effect = lambda: self._raise_exception(Exception)

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )
        with self.assertRaises(asyncio.TimeoutError):
            self.ev_loop.run_until_complete(
                asyncio.wait_for(self.listening_task, 1)
            )

        self.assertTrue(self._is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}."))

    @patch("aiohttp.ClientSession.get")
    def test_listen_for_order_book_snapshots_successful(self, mock_api,):
        msg_queue: asyncio.Queue = asyncio.Queue()
        self.mocking_assistant.configure_http_request_mock(mock_api)

        self.mocking_assistant.add_http_response(mock_api, 200, self._snapshot_response())

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.ev_loop.run_until_complete(msg_queue.get())

        self.assertTrue(12345, msg.update_id)
