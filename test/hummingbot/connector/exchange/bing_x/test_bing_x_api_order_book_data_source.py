#!/usr/bin/env python
from decimal import Decimal
import aiohttp
from os.path import (
    join,
    realpath
)
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../../")))


import asyncio
import json
import re
import unittest
from typing import Awaitable, Dict
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.bing_x import bing_x_constants as CONSTANTS, bing_x_web_utils as web_utils
from hummingbot.connector.exchange.bing_x.bing_x_api_order_book_data_source import BingXAPIOrderBookDataSource
from hummingbot.connector.exchange.bing_x.bing_x_exchange import BingXExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.connector.exchange.bybit.bybit_exchange import BybitExchange


class TestBingXAPIOrderBookDataSource(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "AURA"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = CONSTANTS.DEFAULT_DOMAIN

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.async_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = BingXExchange(
            client_config_map=client_config_map,
            bingx_api_key="",
            bingx_api_secret="",
            trading_pairs=[self.trading_pair])

        self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self.time_synchronnizer = TimeSynchronizer()
        self.time_synchronnizer.add_time_offset_ms_sample(1000)
        self.ob_data_source = BingXAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            throttler=self.throttler,
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
        )

        self._original_full_order_book_reset_time = self.ob_data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.ob_data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.ob_data_source.logger().setLevel(1)
        self.ob_data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        self.async_task and self.async_task.cancel()
        self.ob_data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @aioresponses()
    def test_request_order_book_snapshot(self, mock_api):
        url = web_utils.rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        snapshot_data = self._snapshot_response()
        tradingrule_url = web_utils.rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL)
        tradingrule_resp = self.get_exchange_rules_mock()
        mock_api.get(tradingrule_url, body=json.dumps(tradingrule_resp))
        mock_api.get(regex_url, body=json.dumps(snapshot_data))

        ret = self.async_run_with_timeout(
            coroutine=self.ob_data_source._request_order_book_snapshot(self.trading_pair)
        )

        self.assertEqual(ret, self._snapshot_response_processed())  # shallow comparison ok

    @aioresponses()
    def test_get_snapshot_raises(self, mock_api):
        url = web_utils.rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        tradingrule_url = web_utils.rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL)
        tradingrule_resp = self.get_exchange_rules_mock()
        mock_api.get(tradingrule_url, body=json.dumps(tradingrule_resp))
        mock_api.get(regex_url, status=500)

        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                coroutine=self.ob_data_source._order_book_snapshot(self.trading_pair)
            )

    @aioresponses()
    def test_get_new_order_book(self, mock_api):
        url = web_utils.rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self._snapshot_response()
        mock_api.get(regex_url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.ob_data_source.get_new_order_book(self.trading_pair))
        bid_entries = list(ret.bid_entries())
        ask_entries = list(ret.ask_entries())
        self.assertEqual(2, len(bid_entries))
        self.assertEqual(0.031, bid_entries[0].price)
        self.assertEqual(35.0, bid_entries[0].amount)
        self.assertEqual(int(resp["ts"]), bid_entries[0].update_id)
        self.assertEqual(2, len(ask_entries))
        self.assertEqual(0.095, ask_entries[0].price)
        self.assertEqual(988.7, ask_entries[0].amount)
        self.assertEqual(int(resp["ts"]), ask_entries[0].update_id)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_trades_and_depth(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_trades = {
            'id': 'trade',
            'dataType': self.ex_trading_pair + "@trade"
        }

        result_subscribe_depth = {
            'id': 'depth',
            'dataType': self.ex_trading_pair + "@depth"
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trades))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_depth))

        self.listening_task = self.ev_loop.create_task(self.ob_data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(2, len(sent_subscription_messages))
        self.assertTrue(self._is_logged(
            "INFO",
            f"Subscribed to public order book and trade channels of {self.trading_pair}..."
        ))

    @aioresponses()
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    def test_listen_for_order_book_snapshots_successful_rest(self, mock_api, _):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.TimeoutError
        self.ob_data_source._message_queue[CONSTANTS.SNAPSHOT_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()
        url = web_utils.rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        snapshot_data = self._snapshot_response()
        mock_api.get(regex_url, body=json.dumps(snapshot_data))

        self.listening_task = self.ev_loop.create_task(
            self.ob_data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(int(snapshot_data["ts"]), msg.update_id)

    def test_listen_for_order_book_snapshots_successful_ws(self):
        mock_queue = AsyncMock()
        snapshot_event = {"code": 0, "data": {"asks": [["36719.12", "0.00006"], ["36711.77", "0.00006"], ["36710.20", "0.00008"], ["36709.84", "0.00003"], ["36709.75", "0.00024"], ["36706.60", "0.01970"], ["36706.59", "0.00027"], ["36706.00", "0.00006"], ["36702.47", "0.00003"], ["36700.00", "0.00073"], ["36697.87", "0.00024"], ["36695.12", "0.00122"], ["36693.58", "0.00003"], ["36689.16", "0.00003"], ["36688.20", "0.00009"], ["36684.90", "0.00045"], ["36684.72", "0.00015"], ["36684.22", "0.00004"], ["36630.03", "45.81320"], ["36621.09", "19.39050"], ["36617.36", "24.33784"], ["36617.23", "26.39174"], ["36605.02", "7.81271"], ["36604.69", "45.17086"], ["36604.37", "10.15167"], ["36603.41", "10.65501"], ["36602.30", "8.46013"], ["36602.15", "6.22030"], ["36602.13", "9.94170"], ["36602.10", "9.02612"], ["36602.08", "2.93909"], ["36602.06", "2.93909"], ["36602.03", "3.24589"], ["36602.02", "3.84824"], ["36601.99", "3.20728"], ["36601.96", "2.74891"], ["36601.93", "3.27233"], ["36601.92", "3.27233"], ["36601.90", "3.51604"], ["36601.88", "7.90918"], ["36601.86", "6.84844"], ["36601.85", "2.82023"], ["36601.84", "3.09484"], ["36601.82", "9.95274"], ["36601.80", "3.70646"], ["36601.79", "9.94170"], ["36601.78", "3.70646"], ["36601.77", "3.74076"], ["36601.76", "3.58971"], ["36601.73", "3.89171"]], "bids": [["36600.88", "3.98861"], ["36600.82", "3.99039"], ["36600.78", "7.19757"], ["36600.76", "3.14702"], ["36600.74", "2.94611"], ["36600.72", "13.10343"], ["36600.71", "3.37661"], ["36600.69", "2.97868"], ["36600.67", "3.98861"], ["36600.66", "3.38748"], ["36600.65", "3.23822"], ["36600.64", "3.37090"], ["36600.63", "3.00087"], ["36600.62", "7.71135"], ["36600.60", "8.92355"], ["36600.58", "3.13724"], ["36600.56", "3.33551"], ["36600.52", "4.05712"], ["36600.49", "9.42464"], ["36600.47", "3.67233"], ["36600.45", "3.67233"], ["36595.27", "9.44341"], ["36594.28", "7.53681"], ["36589.83", "9.11043"], ["36589.49", "25.66650"], ["36589.41", "25.28057"], ["36587.76", "10.04297"], ["36573.46", "0.00016"], ["36572.25", "0.00003"], ["36571.02", "0.00001"], ["36570.02", "0.00002"], ["36568.07", "0.00009"], ["36568.00", "0.00049"], ["36567.76", "0.00007"], ["36567.63", "0.00014"], ["36567.56", "0.00003"], ["36567.55", "0.00001"], ["36567.50", "0.00004"], ["36562.50", "0.00003"], ["36560.83", "0.00015"], ["36560.32", "0.00016"], ["36560.00", "0.00009"], ["36559.47", "0.00005"], ["36559.31", "0.00006"], ["36558.61", "0.00040"], ["36558.23", "0.00007"], ["36556.85", "0.00037"], ["36556.78", "0.00026"], ["36556.30", "0.00007"], ["36556.26", "0.00003"]]}, "dataType": "BTC-USDT@depth", "success": True}
        mock_queue.get.side_effect = [snapshot_event, asyncio.CancelledError()]
        self.ob_data_source._message_queue[CONSTANTS.DIFF_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            self.listening_task = self.ev_loop.create_task(
                self.ob_data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
        except asyncio.CancelledError:
            pass

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get(),
                                                            timeout=6)

        self.assertTrue(Decimal(snapshot_event["data"]["asks"][0][0]), msg.asks[0].price)

    # ORDER BOOK SNAPSHOT

    @staticmethod
    def _snapshot_response() -> Dict:
        snapshot = {
            "code": 0,
            "timestamp": 1698722045839,
            "data": {
                "bids": [
                    [
                        "0.031000",
                        "35.0"
                    ],
                    [
                        "0.029017",
                        "11054.2"
                    ]
                ],
                "asks": [
                    [
                        "0.260000",
                        "130.1"
                    ],
                    [
                        "0.095000",
                        "988.7"
                    ],
                ]
            },
            "ts": 1698722045839
        }
        return snapshot

    @staticmethod
    def _snapshot_response_processed() -> Dict:
        snapshot_processed = {
            "timestamp": 1698722045839,
            "bids": [
                [
                    "0.031000",
                    "35.0"
                ],
                [
                    "0.029017",
                    "11054.2"
                ]
            ],
            "asks": [
                [
                    "0.260000",
                    "130.1"
                ],
                [
                    "0.095000",
                    "988.7"
                ],
            ]
        }
        return snapshot_processed

    def get_exchange_rules_mock(self) -> Dict:
        exchange_rules = {
            "code": 0,
            "msg": "",
            "debugMsg": "",
            "data": {
                "symbols": [
                    {
                        "symbol": self.ex_trading_pair,
                        "minQty": 0,
                        "maxQty": 100,
                        "minNotional": 5,
                        "maxNotional": 100000,
                        "status": 1,
                        "tickSize": 0.01,
                        "stepSize": 0.00001
                    },
                ]
            }
        }
        return exchange_rules

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    def test_listen_for_subscriptions_raises_cancel_exception(self, _, ws_connect_mock):
        ws_connect_mock.side_effect = asyncio.CancelledError
        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.ob_data_source.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    def test_listen_for_subscriptions_logs_exception_details(self, sleep_mock, ws_connect_mock):
        sleep_mock.side_effect = asyncio.CancelledError
        ws_connect_mock.side_effect = Exception("TEST ERROR.")

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.ob_data_source.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."))

    def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.ob_data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.ob_data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_trades_logs_exception(self):
        incomplete_resp = {
            "topic": "trade",
            "params": {
                "symbol": self.ex_trading_pair,
                "binary": "false",
                "symbolName": self.ex_trading_pair
            },
            "data": {
                "v": "564265886622695424",
                # "t": 1582001735462,
                "p": "9787.5",
                "q": "0.195009",
                "m": True
            }
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.ob_data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.ob_data_source.listen_for_trades(self.ev_loop, msg_queue)
        )

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public trade updates from exchange"))

    def test_listen_for_trades_successful(self):
        mock_queue = AsyncMock()
        trade_event = {"code": 0, "data": {"E": 1698820885373, "T": 1698820885294, "e": "trade", "m": True, "p": "34411.07", "q": "0.01530", "s": "BTC-USDT", "t": "68710186"}, "dataType": "BTC-USDT@trade", "success": True}
        mock_queue.get.side_effect = [trade_event, asyncio.CancelledError()]
        self.ob_data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            self.listening_task = self.ev_loop.create_task(
                self.ob_data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
        except asyncio.CancelledError:
            pass

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertTrue(trade_event["data"]['T'], msg.trade_id)
