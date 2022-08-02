import asyncio
import json
import re
import time
import unittest
from typing import Any, Awaitable, Dict, List
from unittest.mock import patch

import aiohttp
from aioresponses.core import aioresponses
from bidict import bidict

from hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_api_order_book_data_source import (
    FtxPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book import OrderBook, OrderBookMessage

FTX_REST_URL = "https://ftx.com/api"
FTX_EXCHANGE_INFO_PATH = "/markets"
FTX_WS_FEED = "wss://ftx.com/ws/"


class FtxPerpetualAPIOrderBookDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "USD"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-PERP"
        cls.domain = "ftx_perpetual_testnet"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.async_tasks: List[asyncio.Task] = []

        self.data_source = FtxPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair]
        )
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()
        FtxPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.domain: bidict({self.ex_trading_pair: self.trading_pair})
        }

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        for task in self.async_tasks:
            task.cancel()
        FtxPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def resume_test_callback(self, *_, **__):
        self.resume_test_event.set()
        return None

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _raise_exception(self, exception_class):
        raise exception_class

    def _raise_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    @aioresponses()
    def test_get_last_traded_prices(self, mock_api):
        url = f"{FTX_REST_URL}{FTX_EXCHANGE_INFO_PATH}"
        mock_response: Dict[str, Any] = {
            # Truncated responses
            "result": [
                {
                    "last": "10.0",
                    "name": "COINALPHA-PERP"
                }
            ]
        }
        mock_api.get(url, body=json.dumps(mock_response))

        result: Dict[str, Any] = self.async_run_with_timeout(
            self.data_source.get_last_traded_prices(trading_pairs=[self.trading_pair])
        )
        self.assertTrue(self.trading_pair in result)
        self.assertEqual(10.0, result[self.trading_pair])

    @aioresponses()
    def test_get_snapshot_exception_raised(self, mock_api):
        url = f"{FTX_REST_URL}{FTX_EXCHANGE_INFO_PATH}/COINALPHA-PERP/orderbook?depth=100"
        mock_api.get(url, status=400, body=json.dumps(["ERROR"]))

        with self.assertRaises(IOError) as context:
            self.async_run_with_timeout(
                self.data_source.get_snapshot(client=aiohttp.ClientSession(), trading_pair=self.trading_pair)
            )

        self.assertEqual(str(context.exception), f"Error fetching FTX market snapshot for {self.trading_pair}. HTTP status is 400.")

    @aioresponses()
    def test_get_snapshot_successful(self, mock_api):
        url = f"{FTX_REST_URL}{FTX_EXCHANGE_INFO_PATH}/COINALPHA-PERP/orderbook?depth=100"
        mock_response = {
            "result":
            {
                "bids": [["10", "1"]],
                "asks": [["11", "1"]],
            }
        }
        mock_api.get(url, status=200, body=json.dumps(mock_response))

        result: Dict[str, Any] = self.async_run_with_timeout(
            self.data_source.get_snapshot(client=aiohttp.ClientSession(), trading_pair=self.trading_pair)
        )
        self.assertEqual(mock_response, result)

    @aioresponses()
    def test_get_new_order_book(self, mock_api):
        url = f"{FTX_REST_URL}{FTX_EXCHANGE_INFO_PATH}/COINALPHA-PERP/orderbook?depth=100"
        mock_response = {
            "result":
            {
                "bids": [["10", "1"]],
                "asks": [["11", "1"]],
            }
        }
        mock_api.get(url, status=200, body=json.dumps(mock_response))
        result = self.async_run_with_timeout(self.data_source.get_new_order_book(trading_pair=self.trading_pair))

        self.assertIsInstance(result, OrderBook)
        self.assertTrue((time.time() - result.snapshot_uid) < 1)

    @patch("websockets.connect")
    def test_listen_for_trades(self, ws_connect_mock):
        trades_queue = asyncio.Queue()

        websocket_mock = self.mocking_assistant.create_websocket_mock()
        websocket_mock.recv.side_effect = Exception()
        websocket_mock.close.side_effect = lambda: trades_queue.put_nowait(1)
        ws_connect_mock.return_value = websocket_mock

        self.data_source = FtxPerpetualAPIOrderBookDataSource(
            trading_pairs=["BTC-PERP"]
        )
        task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_trades(ev_loop=asyncio.get_event_loop(), output=trades_queue))

        # Add trade event message be processed

        # Lock the test to let the async task run
        asyncio.get_event_loop().run_until_complete(trades_queue.get())

        try:
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error with WebSocket connection. Retrying after 30 seconds..."))

    @patch("websockets.connect")
    def test_listen_for_order_book_diff_event_logs_exception(self, ws_connect_mock):
        order_book_messages = asyncio.Queue()

        websocket_mock = self.mocking_assistant.create_websocket_mock()
        websocket_mock.recv.side_effect = Exception()
        websocket_mock.close.side_effect = lambda: order_book_messages.put_nowait(1)
        ws_connect_mock.return_value = websocket_mock

        self.data_source = FtxPerpetualAPIOrderBookDataSource(
            trading_pairs=["BTC-PERP"]
        )
        task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_order_book_diffs(ev_loop=asyncio.get_event_loop(), output=order_book_messages))

        # Lock the test to let the async task run
        asyncio.get_event_loop().run_until_complete(order_book_messages.get())

        try:
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error with WebSocket connection. Retrying after 30 seconds..."))

    @aioresponses()
    @patch("hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_api_order_book_data_source"
           ".FtxPerpetualAPIOrderBookDataSource._time")
    def test_get_new_order_book_successful(self, mock_api, time_mock):
        time_mock.return_value = 1640001112.223334
        url = f"{FTX_REST_URL}/markets/{self.ex_trading_pair}/orderbook"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = {
            "success": True,
            "result": {
                "asks": [
                    [
                        4114.25,
                        6.263
                    ]
                ],
                "bids": [
                    [
                        4112.25,
                        49.29
                    ]
                ]
            }
        }

        mock_api.get(regex_url, body=json.dumps(resp))

        order_book: OrderBook = self.async_run_with_timeout(
            self.data_source.get_new_order_book(self.trading_pair)
        )

        expected_update_id = int(time_mock.return_value)

        self.assertEqual(expected_update_id, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(1, len(bids))
        self.assertEqual(4112.25, bids[0].price)
        self.assertEqual(49.29, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(4114.25, asks[0].price)
        self.assertEqual(6.263, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @aioresponses()
    @patch("hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_api_order_book_data_source"
           ".FtxPerpetualAPIOrderBookDataSource._time")
    def test_listen_for_order_book_snapshots_successful(self, mock_api, time_mock):
        time_mock.return_value = 1640001112.223334
        url = f"{FTX_REST_URL}/markets/{self.ex_trading_pair}/orderbook"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = {
            "success": True,
            "result": {
                "asks": [
                    [
                        4114.25,
                        6.263
                    ]
                ],
                "bids": [
                    [
                        4112.25,
                        49.29
                    ]
                ]
            }
        }

        mock_api.get(regex_url, body=json.dumps(resp))

        output_queue = asyncio.Queue()
        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_order_book_snapshots(
                ev_loop=self.ev_loop, output=output_queue)
        )

        snapshot_msg: OrderBookMessage = self.async_run_with_timeout(output_queue.get())
        expected_update_id = int(time_mock.return_value)

        self.assertEqual(expected_update_id, snapshot_msg.update_id)
        bids = list(snapshot_msg.bids)
        asks = list(snapshot_msg.asks)
        self.assertEqual(1, len(bids))
        self.assertEqual(4112.25, bids[0].price)
        self.assertEqual(49.29, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(4114.25, asks[0].price)
        self.assertEqual(6.263, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)
