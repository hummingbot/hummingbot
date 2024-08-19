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
from hummingbot.connector.exchange.bybit import bybit_constants as CONSTANTS, bybit_web_utils as web_utils
from hummingbot.connector.exchange.bybit.bybit_api_order_book_data_source import BybitAPIOrderBookDataSource
from hummingbot.connector.exchange.bybit.bybit_exchange import BybitExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_message import OrderBookMessage


class TestBybitAPIOrderBookDataSource(unittest.TestCase):
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
        cls.domain = CONSTANTS.DEFAULT_DOMAIN

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.async_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = BybitExchange(
            client_config_map=client_config_map,
            bybit_api_key="",
            bybit_api_secret="",
            trading_pairs=[self.trading_pair])

        self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self.time_synchronnizer = TimeSynchronizer()
        self.time_synchronnizer.add_time_offset_ms_sample(1000)
        self.ob_data_source = BybitAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            throttler=self.throttler,
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            time_synchronizer=self.time_synchronnizer)

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

    def get_exchange_rules_mock(self) -> Dict:
        exchange_rules = {
            "ret_code": 0,
            "ret_msg": "",
            "ext_code": None,
            "ext_info": None,
            "result": [
                {
                    "name": self.ex_trading_pair,
                    "alias": self.ex_trading_pair,
                    "baseCurrency": "COINALPHA",
                    "quoteCurrency": "HBOT",
                    "basePrecision": "0.000001",
                    "quotePrecision": "0.01",
                    "minTradeQuantity": "0.0001",
                    "minTradeAmount": "10",
                    "minPricePrecision": "0.01",
                    "maxTradeQuantity": "2",
                    "maxTradeAmount": "200",
                    "category": 1,
                    "showStatus": True
                },
            ]
        }
        return exchange_rules

    # ORDER BOOK SNAPSHOT
    @staticmethod
    def _snapshot_response() -> Dict:
        snapshot = {
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "ts": 1716863719031,
                "u": 230704,
                "seq": 1432604333,
                "cts": 1716863718905,
                "b": [
                    [
                        "50005.12",
                        "403.0416"
                    ]
                ],
                "a": [
                    [
                        "50006.34",
                        "0.2297"
                    ]
                ]
            },
            "time": 1716863719382,
            "retExtInfo": {}
        }
        return snapshot

    @staticmethod
    def _snapshot_response_processed() -> Dict:
        snapshot_processed = {
            'ts': 1716863719031,
            'u': 230704,
            'seq': 1432604333,
            'cts': 1716863718905,
            'b': [['50005.12', '403.0416']],
            'a': [['50006.34', '0.2297']]
        }
        return snapshot_processed

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
        self.assertEqual(1, len(bid_entries))
        self.assertEqual(50005.12, bid_entries[0].price)
        self.assertEqual(403.0416, bid_entries[0].amount)
        self.assertEqual(1, len(ask_entries))
        self.assertEqual(50006.34, ask_entries[0].price)
        self.assertEqual(int(resp["result"]["u"]), bid_entries[0].update_id)
        self.assertEqual(int(resp["result"]["u"]), ask_entries[0].update_id)
        self.assertEqual(0.2297, ask_entries[0].amount)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_trades_and_depth(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_trades = {
            'topic': 'trade',
            'event': 'sub',
            'symbol': self.ex_trading_pair,
            'params': {
                'binary': 'false',
                'symbolName': self.ex_trading_pair},
            'code': '0',
            'msg': 'Success'
        }

        result_subscribe_depth = {
            'topic': 'depth',
            'event': 'sub',
            'symbol': self.ex_trading_pair,
            'params': {
                'binary': 'false',
                'symbolName': self.ex_trading_pair},
            'code': '0',
            'msg': 'Success'
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
        expected_trade_subscription = {
            'op': 'subscribe',
            'args': ['publicTrade.COINALPHAHBOT']
        }
        self.assertEqual(expected_trade_subscription, sent_subscription_messages[0])
        expected_diff_subscription = {
            'op': 'subscribe',
            'args': ['orderbook.50.COINALPHAHBOT']
        }
        self.assertEqual(expected_diff_subscription, sent_subscription_messages[1])

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.bybit.bybit_api_order_book_data_source.BybitAPIOrderBookDataSource._time")
    def test_listen_for_subscriptions_sends_ping_message_before_ping_interval_finishes(
            self,
            time_mock,
            ws_connect_mock):

        time_mock.side_effect = [1000, 1100, 1101, 1102]  # Simulate first ping interval is already due

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_trades = {
            'topic': 'trade',
            'event': 'sub',
            'symbol': self.ex_trading_pair,
            'params': {
                'binary': 'false',
                'symbolName': self.ex_trading_pair},
            'code': '0',
            'msg': 'Success'
        }

        result_subscribe_depth = {
            'topic': 'depth',
            'event': 'sub',
            'symbol': self.ex_trading_pair,
            'params': {
                'binary': 'false',
                'symbolName': self.ex_trading_pair},
            'code': '0',
            'msg': 'Success'
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trades))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_depth))

        self.listening_task = self.ev_loop.create_task(self.ob_data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        expected_ping_message = {'op': 'ping'}
        self.assertEqual(expected_ping_message, sent_messages[-1])

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
        self.ob_data_source._message_queue["trade"] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.ob_data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_trades_logs_exception(self):
        incomplete_resp = {
            "topic": f"publicTrade.{self.ex_trading_pair}",
            "type": "trade",
            "data": [
                {
                    "s": f"{self.ex_trading_pair}",
                    "S": "Buy",
                    "v": "0.001",
                    "p": "16578.50",
                    "L": "PlusTick",
                    "i": "20f43950-d8dd-5b31-9112-a178eb6023af",
                    "BT": False
                }
            ]
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.ob_data_source._message_queue["trade"] = mock_queue

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
        trade_event = {
            "topic": f"publicTrade.{self.ex_trading_pair}",
            "type": "trade",
            "ts": 1672304486868,
            "data": [
                {
                    "T": 1672304486865,
                    "s": f"{self.ex_trading_pair}",
                    "S": "Buy",
                    "v": "0.001",
                    "p": "16578.50",
                    "L": "PlusTick",
                    "i": "20f43950-d8dd-5b31-9112-a178eb6023af",
                    "BT": False
                }
            ]
        }
        mock_queue.get.side_effect = [trade_event, asyncio.CancelledError()]
        self.ob_data_source._message_queue["trade"] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            self.listening_task = self.ev_loop.create_task(
                self.ob_data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
        except asyncio.CancelledError:
            pass

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())
        print(msg)

        self.assertTrue(trade_event["data"][0]["i"], msg.trade_id)

    def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.ob_data_source._message_queue["order_book_diff"] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.ob_data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_order_book_diffs_logs_exception(self):
        incomplete_resp = {
            "type": "order_book_diff",
            "data": {
                "s": f"{self.ex_trading_pair}",
                "b": [
                    [
                        "30247.20",
                        "30.028"
                    ],
                    [
                        "30245.40",
                        "0.224"
                    ],
                    [
                        "30242.10",
                        "1.593"
                    ],
                    [
                        "30240.30",
                        "1.305"
                    ],
                    [
                        "30240.00",
                        "0"
                    ]
                ],
                "a": [
                    [
                        "30248.70",
                        "0"
                    ],
                    [
                        "30249.30",
                        "0.892"
                    ],
                    [
                        "30249.50",
                        "1.778"
                    ],
                    [
                        "30249.60",
                        "0"
                    ],
                    [
                        "30251.90",
                        "2.947"
                    ],
                    [
                        "30252.20",
                        "0.659"
                    ],
                    [
                        "30252.50",
                        "4.591"
                    ]
                ],
                "u": 177400507,
                "seq": 66544703342
            },
            "cts": 1687940967464
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.ob_data_source._message_queue["order_book_diff"] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.ob_data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
        )

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass
        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public order book updates from exchange"))

    def test_listen_for_order_book_diffs_successful(self):
        mock_queue = AsyncMock()
        diff_event = {
            "topic": f"orderbook.50.{self.ex_trading_pair}",
            "type": "order_book_diff",
            "ts": 1687940967466,
            "data": {
                "s": f"{self.ex_trading_pair}",
                "b": [
                    [
                        "30247.20",
                        "30.028"
                    ],
                    [
                        "30245.40",
                        "0.224"
                    ],
                    [
                        "30242.10",
                        "1.593"
                    ],
                    [
                        "30240.30",
                        "1.305"
                    ],
                    [
                        "30240.00",
                        "0"
                    ]
                ],
                "a": [
                    [
                        "30248.70",
                        "0"
                    ],
                    [
                        "30249.30",
                        "0.892"
                    ],
                    [
                        "30249.50",
                        "1.778"
                    ],
                    [
                        "30249.60",
                        "0"
                    ],
                    [
                        "30251.90",
                        "2.947"
                    ],
                    [
                        "30252.20",
                        "0.659"
                    ],
                    [
                        "30252.50",
                        "4.591"
                    ]
                ],
                "u": 177400507,
                "seq": 66544703342
            },
            "cts": 1687940967464
        }
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.ob_data_source._message_queue["order_book_diff"] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            self.listening_task = self.ev_loop.create_task(
                self.ob_data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
        except asyncio.CancelledError:
            pass

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())
        self.assertTrue(diff_event["data"]["u"], msg.update_id)

    @aioresponses()
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    def test_listen_for_order_book_snapshots_successful_rest(self, mock_api, _):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.TimeoutError

        self.ob_data_source._message_queue["order_book_snapshot"] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()
        url = web_utils.rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        snapshot_data = self._snapshot_response()
        mock_api.get(regex_url, body=json.dumps(snapshot_data))

        self.listening_task = self.ev_loop.create_task(
            self.ob_data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get(), 5)

        self.assertEqual(int(snapshot_data["result"]["u"]), msg.update_id)

    def test_listen_for_order_book_snapshots_successful_ws(self):
        mock_queue = AsyncMock()
        snapshot_event = {
            "topic": f"orderbook.50.{self.ex_trading_pair}",
            "type": "snapshot",
            "ts": 1672304484978,
            "data": {
                "s": f"{self.ex_trading_pair}",
                "b": [
                    ...,
                    [
                        "16493.50",
                        "0.006"
                    ],
                    [
                        "16493.00",
                        "0.100"
                    ]
                ],
                "a": [
                    [
                        "16611.00",
                        "0.029"
                    ],
                    [
                        "16612.00",
                        "0.213"
                    ],
                    ...,
                ],
                "u": 18521288,
                "seq": 7961638724
            },
            "cts": 1672304484976
        }
        mock_queue.get.side_effect = [snapshot_event, asyncio.CancelledError()]
        self.ob_data_source._message_queue["order_book_diff"] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            self.listening_task = self.ev_loop.create_task(
                self.ob_data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
        except asyncio.CancelledError:
            pass

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get(),
                                                            timeout=6)

        self.assertTrue(snapshot_event["data"]["u"], msg.update_id)
