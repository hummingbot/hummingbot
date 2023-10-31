#!/usr/bin/env python
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
        snapshot_event = {
            "symbol": self.ex_trading_pair,
            "symbolName": self.ex_trading_pair,
            "topic": "diffDepth",
            "params": {
                "realtimeInterval": "24h",
                "binary": "false"
            },
            "data": [{
                "e": 301,
                "s": self.ex_trading_pair,
                "t": 1565600357643,
                "v": "112801745_18",
                "b": [
                    ["11371.49", "0.0014"],
                    ["11371.12", "0.2"],
                    ["11369.97", "0.3523"],
                    ["11369.96", "0.5"],
                    ["11369.95", "0.0934"],
                    ["11369.94", "1.6809"],
                    ["11369.6", "0.0047"],
                    ["11369.17", "0.3"],
                    ["11369.16", "0.2"],
                    ["11369.04", "1.3203"]],
                "a": [
                    ["11375.41", "0.0053"],
                    ["11375.42", "0.0043"],
                    ["11375.48", "0.0052"],
                    ["11375.58", "0.0541"],
                    ["11375.7", "0.0386"],
                    ["11375.71", "2"],
                    ["11377", "2.0691"],
                    ["11377.01", "0.0167"],
                    ["11377.12", "1.5"],
                    ["11377.61", "0.3"]
                ],
                "o": 0
            }],
            "f": True,
            "sendTime": 1626253839401,
            "shared": False
        }
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

        self.assertTrue(snapshot_event["data"][0]["t"], msg.update_id)

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
