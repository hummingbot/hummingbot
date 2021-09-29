import unittest
import asyncio
from collections import deque
import ujson
import re
import json
from unittest.mock import patch, AsyncMock
from typing import (
    Any,
    Dict,
    List,
)
from aioresponses import aioresponses
from hummingbot.connector.exchange.bitmart.bitmart_api_order_book_data_source import BitmartAPIOrderBookDataSource
from hummingbot.connector.exchange.bitmart.bitmart_order_book_message import BitmartOrderBookMessage
import hummingbot.connector.exchange.bitmart.bitmart_constants as CONSTANTS
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class BitmartAPIOrderBookDataSourceUnitTests(unittest.TestCase):
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
        self.ws_sent_messages = []
        self.ws_incoming_messages = asyncio.Queue()
        self.listening_task = None

        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.data_source = BitmartAPIOrderBookDataSource(self.throttler, [self.trading_pair])
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)
        self.mocking_assistant = NetworkMockingAssistant()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _order_book_snapshot_example(self):
        return {
            "data": {
                "timestamp": 1527777538000,
                "buys": [
                    {
                        "amount": "4800.00",
                        "total": "4800.00",
                        "price": "0.000767",
                        "count": "1"
                    },
                    {
                        "amount": "99996475.79",
                        "total": "100001275.79",
                        "price": "0.000201",
                        "count": "1"
                    },
                ],
                "sells": [
                    {
                        "amount": "100.00",
                        "total": "100.00",
                        "price": "0.007000",
                        "count": "1"
                    },
                    {
                        "amount": "6997.00",
                        "total": "7097.00",
                        "price": "1.000000",
                        "count": "1"
                    },
                ]
            }
        }

    def set_mock_response(self, mock_api, status: int, json_data: Any):
        mock_api.return_value.__aenter__.return_value.status = status
        mock_api.return_value.__aenter__.return_value.json = AsyncMock(return_value=json_data)

    def _raise_exception(self, exception_class):
        raise exception_class

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    async def _get_next_received_message(self):
        return await self.ws_incoming_messages.get()

    def _create_ws_mock(self):
        ws = AsyncMock()
        ws.send.side_effect = lambda sent_message: self.ws_sent_messages.append(sent_message)
        ws.recv.side_effect = self._get_next_received_message
        return ws

    def _add_orderbook_snapshot_response(self):
        resp = {
            "table": "spot/depth500",
            "data": [
                {
                    "asks": [
                        [
                            "161.96",
                            "7.37567"
                        ]
                    ],
                    "bids": [
                        [
                            "161.94",
                            "4.552355"
                        ]
                    ],
                    "symbol": "ETH_USDT",
                    "ms_t": 1542337219120
                }
            ]
        }
        self.ws_incoming_messages.put_nowait(ujson.dumps(resp))
        return resp

    def _add_subscribe_level_2_response(self):
        resp = {
            "m": 1,
            "i": 2,
            "n": "SubscribeLevel2",
            "o": "[[93617617, 1, 1626788175000, 0, 37800.0, 1, 37750.0, 1, 0.015, 0],[93617617, 1, 1626788175000, 0, 37800.0, 1, 37751.0, 1, 0.015, 1]]"
        }
        return ujson.dumps(resp)

    def _add_orderbook_update_event(self):
        resp = {
            "m": 3,
            "i": 3,
            "n": "Level2UpdateEvent",
            "o": "[[93617618, 1, 1626788175001, 0, 37800.0, 1, 37740.0, 1, 0.015, 0]]"
        }
        self.ws_incoming_messages.put_nowait(ujson.dumps(resp))
        return resp

    @patch("aiohttp.ClientSession.get")
    def test_get_last_traded_prices(self, mock_api):
        mock_response: Dict[Any] = {
            "message": "OK",
            "code": 1000,
            "trace": "6e42c7c9-fdc5-461b-8fd1-b4e2e1b9ed57",
            "data": {
                "tickers": [
                    {
                        "symbol": "COINALPHA_HBOT",
                        "last_price": "1.00",
                        "quote_volume_24h": "201477650.88000",
                        "base_volume_24h": "25186.48000",
                        "high_24h": "8800.00",
                        "low_24h": "1.00",
                        "open_24h": "8800.00",
                        "close_24h": "1.00",
                        "best_ask": "0.00",
                        "best_ask_size": "0.00000",
                        "best_bid": "0.00",
                        "best_bid_size": "0.00000",
                        "fluctuation": "-0.9999",
                        "url": "https://www.bitmart.com/trade?symbol=COINALPHA_HBOT"
                    }
                ]
            }
        }

        self.set_mock_response(mock_api, 200, mock_response)

        results = self.ev_loop.run_until_complete(
            asyncio.gather(self.data_source.get_last_traded_prices([self.trading_pair])))
        results: Dict[str, Any] = results[0]

        self.assertEqual(results[self.trading_pair], float("1.00"))

    @aioresponses()
    def test_fetch_trading_pairs(self, mock_get):
        mock_response: List[Any] = {
            "code": 1000,
            "trace": "886fb6ae-456b-4654-b4e0-d681ac05cea1",
            "message": "OK",
            "data": {
                "symbols": [
                     "COINALPHA_HBOT",
                     "ANOTHER_MARKET",
                ]
            }
        }
        regex_url = re.compile(f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_TRADING_PAIRS_PATH_URL}")
        mock_get.get(regex_url, body=json.dumps(mock_response))
        results: List[str] = self.ev_loop.run_until_complete(self.data_source.fetch_trading_pairs())
        self.assertTrue(self.trading_pair in results)
        self.assertTrue("ANOTHER-MARKET" in results)

    @aioresponses()
    def test_fetch_trading_pairs_with_error_status_in_response(self, mock_get):
        mock_response = {}
        regex_url = re.compile(f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_TRADING_PAIRS_PATH_URL}")
        mock_get.get(regex_url, body=json.dumps(mock_response))
        result = self.ev_loop.run_until_complete(self.data_source.fetch_trading_pairs())
        self.assertEqual(0, len(result))

    @aioresponses()
    def test_get_order_book_data(self, mock_get):
        mock_response: Dict[str, Any] = self._order_book_snapshot_example()
        regex_url = re.compile(f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_ORDER_BOOK_PATH_URL}")
        mock_get.get(regex_url, body=json.dumps(mock_response))

        results = self.ev_loop.run_until_complete(
            asyncio.gather(self.data_source.get_order_book_data(self.trading_pair)))

        result = results[0]
        self.assertTrue("timestamp" in result)
        self.assertTrue("buys" in result)
        self.assertTrue("sells" in result)
        self.assertGreaterEqual(len(result["buys"]) + len(result["sells"]), 0)
        self.assertEqual(mock_response["data"]["buys"][0], result["buys"][0])

    @aioresponses()
    def test_get_order_book_data_raises_exception_when_response_has_error_code(self, mock_get):
        regex_url = re.compile(f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_ORDER_BOOK_PATH_URL}")
        mock_get.get(regex_url, status=100, body=json.dumps({}))

        with self.assertRaises(IOError) as context:
            self.ev_loop.run_until_complete(self.data_source.get_order_book_data(self.trading_pair))

        self.assertEqual(str(context.exception), f"Error fetching OrderBook for {self.trading_pair} at {CONSTANTS.EXCHANGE_NAME}. "
                                                 f"HTTP status is {100}.")

    @aioresponses()
    def test_get_new_order_book(self, mock_get):
        mock_response: Dict[str, Any] = self._order_book_snapshot_example()
        regex_url = re.compile(f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_ORDER_BOOK_PATH_URL}")
        mock_get.get(regex_url, body=json.dumps(mock_response))

        results = self.ev_loop.run_until_complete(
            asyncio.gather(self.data_source.get_new_order_book(self.trading_pair)))
        result: OrderBook = results[0]

        self.assertTrue(type(result) == OrderBook)
        self.assertEqual(result.snapshot_uid, mock_response["data"]["timestamp"])

    def test_listen_for_snapshots_cancelled_when_fetching_snapshot(self):
        trades_queue = asyncio.Queue()
        task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_order_book_snapshots(ev_loop=asyncio.get_event_loop(), output=trades_queue))

        with self.assertRaises(asyncio.CancelledError):
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)

    @aioresponses()
    @patch(
        "hummingbot.connector.exchange.bitmart.bitmart_api_order_book_data_source.BitmartAPIOrderBookDataSource._sleep",
        new_callable=AsyncMock)
    def test_listen_for_snapshots_logs_exception_when_fetching_snapshot(self, mock_get, mock_sleep):
        # the queue and the division by zero error are used just to synchronize the test
        sync_queue = deque()
        sync_queue.append(1)
        sync_queue.append(2)

        regex_url = re.compile(f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_ORDER_BOOK_PATH_URL}")
        mock_get.get(regex_url, body=json.dumps({}))

        mock_sleep.side_effect = lambda delay: 1 / 0 if len(sync_queue) == 0 else sync_queue.pop()

        msg_queue: asyncio.Queue = asyncio.Queue()
        with self.assertRaises(ZeroDivisionError):
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_order_book_snapshots(asyncio.get_event_loop(), msg_queue))
            asyncio.get_event_loop().run_until_complete(self.listening_task)

        self.assertEqual(0, msg_queue.qsize())

        self.assertTrue(self._is_logged("ERROR",
                                        "Unexpected error occured listening for orderbook snapshots. Retrying in 5 secs..."))

    @aioresponses()
    @patch(
        "hummingbot.connector.exchange.bitmart.bitmart_api_order_book_data_source.BitmartAPIOrderBookDataSource._sleep",
        new_callable=AsyncMock)
    def test_listen_for_snapshots_successful(self, mock_get, mock_sleep):
        # the queue and the division by zero error are used just to synchronize the test
        sync_queue = deque()
        sync_queue.append(1)
        sync_queue.append(2)

        mock_response: Dict[str, Any] = self._order_book_snapshot_example()
        regex_url = re.compile(f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_ORDER_BOOK_PATH_URL}")
        mock_get.get(regex_url, body=json.dumps(mock_response))

        mock_sleep.side_effect = lambda delay: 1 / 0 if len(sync_queue) == 0 else sync_queue.pop()

        msg_queue: asyncio.Queue = asyncio.Queue()
        with self.assertRaises(ZeroDivisionError):
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_order_book_snapshots(asyncio.get_event_loop(), msg_queue))
            asyncio.get_event_loop().run_until_complete(self.listening_task)

        self.assertEqual(msg_queue.qsize(), 1)

        snapshot_msg: OrderBookMessage = msg_queue.get_nowait()
        self.assertEqual(snapshot_msg.update_id, mock_response["data"]["timestamp"])

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_cancelled_when_listening(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        msg_queue: asyncio.Queue = asyncio.Queue()
        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue))

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task.cancel()
            asyncio.get_event_loop().run_until_complete(self.listening_task)

        self.assertEqual(msg_queue.qsize(), 0)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_successful(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        msg_queue: asyncio.Queue = asyncio.Queue()
        self.mocking_assistant.add_websocket_json_message(
            mock_ws.return_value, {
                "table": "spot/depth500",
                "data": [
                    {
                        "asks": [
                            [
                                "161.96",
                                "7.37567"
                            ]
                        ],
                        "bids": [
                            [
                                "161.94",
                                "4.552355"
                            ]
                        ],
                        "symbol": "ETH_USDT",
                        "ms_t": 1542337219120
                    }
                ]
            }
        )
        # self._add_orderbook_snapshot_response()

        with self.assertRaises(asyncio.TimeoutError):
            self.listening_task = self.ev_loop.create_task(asyncio.wait_for(
                self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue),
                2.0
            ))
            self.ev_loop.run_until_complete(self.listening_task)

        self.assertGreater(msg_queue.qsize(), 0)
        first_msg: BitmartOrderBookMessage = msg_queue.get_nowait()
        self.assertTrue(first_msg.type == OrderBookMessageType.SNAPSHOT)

    @patch("websockets.connect", new_callable=AsyncMock)
    def test_websocket_connection_creation_raises_cancel_exception(self, mock_ws):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            asyncio.get_event_loop().run_until_complete(self.data_source._create_websocket_connection())

    @patch("websockets.connect", new_callable=AsyncMock)
    def test_websocket_connection_creation_raises_exception_after_loging(self, mock_ws):
        mock_ws.side_effect = Exception

        with self.assertRaises(Exception):
            asyncio.get_event_loop().run_until_complete(self.data_source._create_websocket_connection())

        self.assertTrue(self._is_logged("NETWORK", "Unexpected error occurred during bitmart WebSocket Connection ()"))

    def _trade_ws_messsage(self):
        resp = {
            "table": "spot/trade",
            "data": [
                {
                    "symbol": "ETH_USDT",
                    "price": "162.12",
                    "side": "buy",
                    "size": "11.085",
                    "s_t": 1542337219
                },
                {
                    "symbol": "ETH_USDT",
                    "price": "163.12",
                    "side": "buy",
                    "size": "15",
                    "s_t": 1542337238
                }
            ]
        }
        return ujson.dumps(resp)

    @patch('websockets.connect', new_callable=AsyncMock)
    def test_listen_for_trades(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.close.return_value = None

        # Add message to be processed after subscriptions, to unlock the test
        self.mocking_assistant.add_websocket_text_message(mock_ws.return_value, self._trade_ws_messsage())
        BitmartAPIOrderBookDataSource._trading_pairs = ["ETH-USDT"]

        listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue)
        )
        trade1: OrderBookMessage = self.ev_loop.run_until_complete(msg_queue.get())
        trade2: OrderBookMessage = self.ev_loop.run_until_complete(msg_queue.get())

        try:
            listening_task.cancel()
            asyncio.get_event_loop().run_until_complete(listening_task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass

        self.assertTrue(msg_queue.empty())
        self.assertEqual(1542337219 * 1000, int(trade1.trade_id))
        self.assertEqual(1542337238 * 1000, int(trade2.trade_id))
