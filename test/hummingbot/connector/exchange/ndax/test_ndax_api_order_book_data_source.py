import asyncio
import unittest

from collections import deque

from unittest.mock import AsyncMock, patch
from typing import (
    Any,
    Awaitable,
    Dict,
    List,
)

import ujson

import hummingbot.connector.exchange.ndax.ndax_constants as CONSTANTS

from hummingbot.connector.exchange.ndax.ndax_api_order_book_data_source import NdaxAPIOrderBookDataSource
from hummingbot.connector.exchange.ndax.ndax_order_book_message import NdaxOrderBookEntry
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class NdaxAPIOrderBookDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.instrument_id = 1

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None

        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.data_source = NdaxAPIOrderBookDataSource(throttler=self.throttler, trading_pairs=[self.trading_pair])
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)
        self.data_source._trading_pair_id_map.clear()

        self.mocking_assistant = NetworkMockingAssistant()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def simulate_trading_pair_ids_initialized(self):
        self.data_source._trading_pair_id_map.update({self.trading_pair: self.instrument_id})

    def _raise_exception(self, exception_class):
        raise exception_class

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _subscribe_level_2_response(self):
        resp = {
            "m": 1,
            "i": 2,
            "n": "SubscribeLevel2",
            "o": "[[93617617, 1, 1626788175000, 0, 37800.0, 1, 37750.0, 1, 0.015, 0],[93617617, 1, 1626788175000, 0, 37800.0, 1, 37751.0, 1, 0.015, 1]]"
        }
        return ujson.dumps(resp)

    def _orderbook_update_event(self):
        resp = {
            "m": 3,
            "i": 3,
            "n": "Level2UpdateEvent",
            "o": "[[93617618, 1, 1626788175001, 0, 37800.0, 1, 37740.0, 1, 0.015, 0]]"
        }
        return ujson.dumps(resp)

    @patch("aiohttp.ClientSession.get")
    def test_init_trading_pair_ids(self, mock_api):
        self.mocking_assistant.configure_http_request_mock(mock_api)

        mock_response: List[Any] = [
            {
                "Product1Symbol": self.base_asset,
                "Product2Symbol": self.quote_asset,
                "InstrumentId": self.instrument_id,
                "SessionStatus": "Running"
            },
            {
                "Product1Symbol": "ANOTHER_ACTIVE",
                "Product2Symbol": "MARKET",
                "InstrumentId": 2,
                "SessionStatus": "Running"
            },
            {
                "Product1Symbol": "NOT_ACTIVE",
                "Product2Symbol": "MARKET",
                "InstrumentId": 3,
                "SessionStatus": "Stopped"
            }
        ]

        self.mocking_assistant.add_http_response(mock_api, 200, mock_response)

        self.ev_loop.run_until_complete(self.data_source.init_trading_pair_ids())
        self.assertEqual(2, len(self.data_source._trading_pair_id_map))
        self.assertEqual(1, self.data_source._trading_pair_id_map[self.trading_pair])
        self.assertEqual(2, self.data_source._trading_pair_id_map["ANOTHER_ACTIVE-MARKET"])

    @patch("aiohttp.ClientSession.get")
    def test_get_last_traded_prices(self, mock_api):
        self.mocking_assistant.configure_http_request_mock(mock_api)
        self.simulate_trading_pair_ids_initialized()
        mock_response: Dict[Any] = {
            "LastTradedPx": 1.0
        }

        self.mocking_assistant.add_http_response(mock_api, 200, mock_response)

        results = self.ev_loop.run_until_complete(
            asyncio.gather(self.data_source.get_last_traded_prices([self.trading_pair])))
        results: Dict[str, Any] = results[0]

        self.assertEqual(results[self.trading_pair], mock_response["LastTradedPx"])

    @patch("aiohttp.ClientSession.get")
    def test_fetch_trading_pairs(self, mock_api):
        self.mocking_assistant.configure_http_request_mock(mock_api)

        self.simulate_trading_pair_ids_initialized()

        mock_response: List[Any] = [
            {
                "Product1Symbol": self.base_asset,
                "Product2Symbol": self.quote_asset,
                "InstrumentId": self.instrument_id,
                "SessionStatus": "Running"
            },
            {
                "Product1Symbol": "ANOTHER_ACTIVE",
                "Product2Symbol": "MARKET",
                "InstrumentId": 2,
                "SessionStatus": "Running"
            },
            {
                "Product1Symbol": "NOT_ACTIVE",
                "Product2Symbol": "MARKET",
                "InstrumentId": 3,
                "SessionStatus": "Stopped"
            }
        ]

        self.mocking_assistant.add_http_response(mock_api, 200, mock_response)
        self.mocking_assistant.add_http_response(mock_api, 200, mock_response)

        results: List[str] = self.ev_loop.run_until_complete(self.data_source.fetch_trading_pairs())
        self.assertTrue(self.trading_pair in results)
        self.assertTrue("ANOTHER_ACTIVE-MARKET" in results)
        self.assertFalse("NOT_ACTIVE-MARKET" in results)

    @patch("aiohttp.ClientSession.get")
    def test_fetch_trading_pairs_with_error_status_in_response(self, mock_api):
        self.mocking_assistant.configure_http_request_mock(mock_api)
        mock_response = {}
        self.mocking_assistant.add_http_response(mock_api, 100, mock_response)

        result = self.ev_loop.run_until_complete(self.data_source.fetch_trading_pairs())
        self.assertEqual(0, len(result))

    @patch("aiohttp.ClientSession.get")
    def test_get_order_book_data(self, mock_api):
        self.mocking_assistant.configure_http_request_mock(mock_api)
        self.simulate_trading_pair_ids_initialized()
        mock_response: List[List[Any]] = [
            # mdUpdateId, accountId, actionDateTime, actionType, lastTradePrice, orderId, price, productPairCode, quantity, side
            [93617617, 1, 1626788175416, 0, 37813.22, 1, 37750.6, 1, 0.014698, 0]
        ]
        self.mocking_assistant.add_http_response(mock_api, 200, mock_response)

        results = self.ev_loop.run_until_complete(
            asyncio.gather(self.data_source.get_order_book_data(self.trading_pair)))
        result = results[0]

        self.assertTrue("data" in result)
        self.assertGreaterEqual(len(result["data"]), 0)
        self.assertEqual(NdaxOrderBookEntry(*mock_response[0]), result["data"][0])

    @patch("aiohttp.ClientSession.get")
    def test_get_order_book_data_raises_exception_when_response_has_error_code(self, mock_api):
        self.mocking_assistant.configure_http_request_mock(mock_api)

        self.simulate_trading_pair_ids_initialized()
        mock_response = {"Erroneous response"}
        self.mocking_assistant.add_http_response(mock_api, 100, mock_response)

        with self.assertRaises(IOError) as context:
            self.ev_loop.run_until_complete(self.data_source.get_order_book_data(self.trading_pair))

        self.assertEqual(str(context.exception), f"Error fetching OrderBook for {self.trading_pair} "
                                                 f"at {CONSTANTS.ORDER_BOOK_URL}. "
                                                 f"HTTP {100}. Response: {mock_response}")

    @patch("aiohttp.ClientSession.get")
    def test_get_new_order_book(self, mock_api):
        self.mocking_assistant.configure_http_request_mock(mock_api)

        self.simulate_trading_pair_ids_initialized()

        mock_response: List[List[Any]] = [
            # mdUpdateId, accountId, actionDateTime, actionType, lastTradePrice, orderId, price, productPairCode, quantity, side
            [93617617, 1, 1626788175416, 0, 37800.0, 1, 37750.0, 1, 0.015, 0],
            [93617617, 1, 1626788175416, 0, 37800.0, 1, 37751.0, 1, 0.015, 1]
        ]
        self.mocking_assistant.add_http_response(mock_api, 200, mock_response)

        results = self.ev_loop.run_until_complete(
            asyncio.gather(self.data_source.get_new_order_book(self.trading_pair)))
        result: OrderBook = results[0]

        self.assertTrue(type(result) == OrderBook)
        self.assertEqual(result.snapshot_uid, 0)

    @patch("aiohttp.ClientSession.get")
    def test_get_instrument_ids(self, mock_api):
        self.mocking_assistant.configure_http_request_mock(mock_api)

        mock_response: List[Any] = [{
            "Product1Symbol": self.base_asset,
            "Product2Symbol": self.quote_asset,
            "InstrumentId": self.instrument_id,
            "SessionStatus": "Running",
        }]
        self.mocking_assistant.add_http_response(mock_api, 200, mock_response)

        results = self.ev_loop.run_until_complete(asyncio.gather(self.data_source.get_instrument_ids()))
        result: Dict[str, Any] = results[0]

        self.assertEqual(1, self.data_source._trading_pair_id_map[self.trading_pair])
        self.assertEqual(result[self.trading_pair], self.instrument_id)

    @patch("hummingbot.connector.exchange.ndax.ndax_api_order_book_data_source.NdaxAPIOrderBookDataSource._sleep")
    @patch("aiohttp.ClientSession.get")
    def test_listen_for_snapshots_cancelled_when_fetching_snapshot(self, mock_api, mock_sleep):
        mock_api.side_effect = asyncio.CancelledError
        self.simulate_trading_pair_ids_initialized()

        msg_queue: asyncio.Queue = asyncio.Queue()
        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
            )
            self.ev_loop.run_until_complete(self.listening_task)

        self.assertEqual(msg_queue.qsize(), 0)

    @patch("hummingbot.connector.exchange.ndax.ndax_api_order_book_data_source.NdaxAPIOrderBookDataSource._sleep")
    @patch("aiohttp.ClientSession.get")
    def test_listen_for_snapshots_logs_exception_when_fetching_snapshot(self, mock_api, mock_sleep):
        # the queue and the division by zero error are used just to synchronize the test
        sync_queue = deque()
        sync_queue.append(1)

        self.simulate_trading_pair_ids_initialized()

        mock_api.side_effect = Exception
        mock_sleep.side_effect = lambda delay: 1 / 0 if len(sync_queue) == 0 else sync_queue.pop()

        msg_queue: asyncio.Queue = asyncio.Queue()
        with self.assertRaises(ZeroDivisionError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue))
            self.ev_loop.run_until_complete(self.listening_task)

        self.assertEqual(msg_queue.qsize(), 0)
        self.assertTrue(self._is_logged("ERROR",
                                        "Unexpected error occured listening for orderbook snapshots. Retrying in 5 secs..."))

    @patch("hummingbot.connector.exchange.ndax.ndax_api_order_book_data_source.NdaxAPIOrderBookDataSource._sleep")
    @patch("aiohttp.ClientSession.get")
    def test_listen_for_snapshots_successful(self, mock_api, mock_sleep):
        self.mocking_assistant.configure_http_request_mock(mock_api)

        # the queue and the division by zero error are used just to synchronize the test
        sync_queue = deque()
        sync_queue.append(1)

        mock_response: List[List[Any]] = [
            # mdUpdateId, accountId, actionDateTime, actionType, lastTradePrice, orderId, price, productPairCode, quantity, side
            [93617617, 1, 1626788175416, 0, 37800.0, 1, 37750.0, 1, 0.015, 0],
            [93617617, 1, 1626788175416, 0, 37800.0, 1, 37751.0, 1, 0.015, 1],
        ]
        self.mocking_assistant.add_http_response(mock_api, 200, mock_response)
        self.simulate_trading_pair_ids_initialized()

        mock_sleep.side_effect = lambda delay: 1 / 0 if len(sync_queue) == 0 else sync_queue.pop()

        msg_queue: asyncio.Queue = asyncio.Queue()
        with self.assertRaises(ZeroDivisionError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue))
            self.ev_loop.run_until_complete(self.listening_task)

        self.assertEqual(msg_queue.qsize(), 1)

        snapshot_msg: OrderBookMessage = msg_queue.get_nowait()
        self.assertEqual(snapshot_msg.update_id, 0)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_cancelled_when_subscribing(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.send_json.side_effect = asyncio.CancelledError()

        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, self._subscribe_level_2_response())
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, self._orderbook_update_event())

        self.simulate_trading_pair_ids_initialized()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
            self.ev_loop.run_until_complete(self.listening_task)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_cancelled_when_listening(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.receive.side_effect = lambda: (
            self._raise_exception(asyncio.CancelledError)
        )

        self.simulate_trading_pair_ids_initialized()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
            self.ev_loop.run_until_complete(self.listening_task)

        self.assertEqual(msg_queue.qsize(), 0)

    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    @patch("hummingbot.connector.exchange.ndax.ndax_api_order_book_data_source.NdaxAPIOrderBookDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_logs_exception(self, mock_api, mock_ws, *_):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.close.return_value = None

        incomplete_resp = {
            "m": 1,
            "i": 2,
        }

        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, ujson.dumps(incomplete_resp))
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, self._orderbook_update_event())

        self.simulate_trading_pair_ids_initialized()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue))

        self.ev_loop.run_until_complete(msg_queue.get())

        self.assertTrue(self._is_logged("NETWORK", "Unexpected error with WebSocket connection."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_successful(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.send_json.return_value = None

        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, self._subscribe_level_2_response())
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, self._orderbook_update_event())

        self.simulate_trading_pair_ids_initialized()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue))

        first_msg = self.ev_loop.run_until_complete(msg_queue.get())
        second_msg = self.ev_loop.run_until_complete(msg_queue.get())

        self.assertTrue(first_msg.type == OrderBookMessageType.SNAPSHOT)
        self.assertTrue(second_msg.type == OrderBookMessageType.DIFF)

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

        self.assertTrue(self._is_logged("NETWORK", "Unexpected error occurred during ndax WebSocket Connection ()"))
