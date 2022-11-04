import asyncio
import json
import re
import unittest
from typing import Awaitable
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses.core import aioresponses
from bidict import bidict

import hummingbot.connector.exchange.okx.okx_constants as CONSTANTS
import hummingbot.connector.exchange.okx.okx_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.okx.okx_api_order_book_data_source import OkxAPIOrderBookDataSource
from hummingbot.connector.exchange.okx.okx_exchange import OkxExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class OkxAPIOrderBookDataSourceUnitTests(unittest.TestCase):
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

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = OkxExchange(
            client_config_map=client_config_map,
            okx_api_key="",
            okx_secret_key="",
            okx_passphrase="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        self.data_source = OkxAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory)

        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

        self.connector._set_trading_pair_symbol_map(
            bidict({f"{self.base_asset}-{self.quote_asset}": self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @aioresponses()
    def test_get_new_order_book_successful(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.OKX_ORDER_BOOK_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "asks": [
                        [
                            "41006.8",
                            "0.60038921",
                            "0",
                            "1"
                        ]
                    ],
                    "bids": [
                        [
                            "41006.3",
                            "0.30178218",
                            "0",
                            "2"
                        ]
                    ],
                    "ts": "1629966436396"
                }
            ]
        }

        mock_api.get(regex_url, body=json.dumps(resp))

        order_book: OrderBook = self.async_run_with_timeout(
            self.data_source.get_new_order_book(self.trading_pair)
        )

        expected_update_id = int(int(resp["data"][0]["ts"]) * 1e-3)

        self.assertEqual(expected_update_id, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(1, len(bids))
        self.assertEqual(41006.3, bids[0].price)
        self.assertEqual(0.30178218, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(41006.8, asks[0].price)
        self.assertEqual(0.60038921, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @aioresponses()
    def test_get_new_order_book_raises_exception(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.OKX_ORDER_BOOK_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                self.data_source.get_new_order_book(self.trading_pair)
            )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_trades = {
            "event": "subscribe",
            "args": {
                "channel": "trades",
                "instId": self.trading_pair
            }
        }
        result_subscribe_diffs = {
            "event": "subscribe",
            "arg": {
                "channel": "books",
                "instId": self.trading_pair
            }
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trades))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_diffs))

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(2, len(sent_subscription_messages))
        expected_trade_subscription = {
            "op": "subscribe",
            "args": [
                {
                    "channel": "trades",
                    "instId": self.trading_pair
                }
            ]
        }
        self.assertEqual(expected_trade_subscription, sent_subscription_messages[0])
        expected_diff_subscription = {
            "op": "subscribe",
            "args": [
                {
                    "channel": "books",
                    "instId": self.trading_pair
                }
            ]
        }
        self.assertEqual(expected_diff_subscription, sent_subscription_messages[1])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to public order book and trade channels..."
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_sends_ping_message_before_ping_interval_finishes(self, ws_connect_mock):

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.receive.side_effect = [asyncio.TimeoutError("Test timeiout"),
                                                            asyncio.CancelledError]

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        sent_messages = self.mocking_assistant.text_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        expected_ping_message = "ping"
        self.assertEqual(expected_ping_message, sent_messages[0])

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws, _: AsyncMock):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."))

    def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

    def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            self.listening_task = self.ev_loop.create_task(self.data_source._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred subscribing to order book trading and delta streams...")
        )

    def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_trades_logs_exception(self):
        incomplete_resp = {
            "arg": {
                "channel": "trades",
                "instId": "BTC-USDT"
            },
            "data": [
                {
                    "instId": "BTC-USDT",
                }
            ]
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue)
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
            "arg": {
                "channel": "trades",
                "instId": self.trading_pair
            },
            "data": [
                {
                    "instId": self.trading_pair,
                    "tradeId": "130639474",
                    "px": "42219.9",
                    "sz": "0.12060306",
                    "side": "buy",
                    "ts": "1630048897897"
                }
            ]
        }
        mock_queue.get.side_effect = [trade_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.TRADE, msg.type)
        self.assertEqual(trade_event["data"][0]["tradeId"], msg.trade_id)
        self.assertEqual(int(trade_event["data"][0]["ts"]) * 1e-3, msg.timestamp)

    def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_order_book_diffs_logs_exception(self):
        incomplete_resp = {
            "arg": {
                "channel": "books",
                "instId": self.trading_pair
            },
            "action": "update",
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
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
            "arg": {
                "channel": "books",
                "instId": self.trading_pair
            },
            "action": "update",
            "data": [
                {
                    "asks": [
                        ["8476.98", "415", "0", "13"],
                        ["8477", "7", "0", "2"],
                        ["8477.34", "85", "0", "1"],
                    ],
                    "bids": [
                        ["8476.97", "256", "0", "12"],
                        ["8475.55", "101", "0", "1"],
                    ],
                    "ts": "1597026383085",
                    "checksum": -855196043
                }
            ]
        }
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.DIFF, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(int(diff_event["data"][0]["ts"]) * 1e-3, msg.timestamp)
        expected_update_id = int(int(diff_event["data"][0]["ts"]) * 1e-3)
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(2, len(bids))
        self.assertEqual(8476.97, bids[0].price)
        self.assertEqual(256, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(3, len(asks))
        self.assertEqual(8476.98, asks[0].price)
        self.assertEqual(415, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    def test_listen_for_order_book_snapshots_websocket_successful(self):
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = 1
        mock_queue = AsyncMock()
        snapshot_event = {
            "arg": {
                "channel": "books",
                "instId": self.trading_pair
            },
            "action": "snapshot",
            "data": [
                {
                    "asks": [
                        ["8476.98", "415", "0", "13"],
                        ["8477", "7", "0", "2"],
                        ["8477.34", "85", "0", "1"],
                    ],
                    "bids": [
                        ["8476.97", "256", "0", "12"],
                        ["8475.55", "101", "0", "1"],
                    ],
                    "ts": "1597026383085",
                    "checksum": -855196043
                }
            ]
        }
        mock_queue.get.side_effect = [snapshot_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(int(snapshot_event["data"][0]["ts"]) * 1e-3, msg.timestamp)
        expected_update_id = int(int(snapshot_event["data"][0]["ts"]) * 1e-3)
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(2, len(bids))
        self.assertEqual(8476.97, bids[0].price)
        self.assertEqual(256, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(3, len(asks))
        self.assertEqual(8476.98, asks[0].price)
        self.assertEqual(415, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @aioresponses()
    def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.OKX_ORDER_BOOK_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, asyncio.Queue())
            )

    @aioresponses()
    @patch("hummingbot.connector.exchange.okx.okx_api_order_book_data_source"
           ".OkxAPIOrderBookDataSource._sleep")
    def test_listen_for_order_book_snapshots_log_exception(self, mock_api, sleep_mock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        url = web_utils.public_rest_url(path_url=CONSTANTS.OKX_ORDER_BOOK_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=Exception)

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}."))

    @aioresponses()
    def test_listen_for_order_book_snapshots_api_successful(self, mock_api, ):
        msg_queue: asyncio.Queue = asyncio.Queue()
        url = web_utils.public_rest_url(path_url=CONSTANTS.OKX_ORDER_BOOK_PATH)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "asks": [
                        [
                            "41006.8",
                            "0.60038921",
                            "0",
                            "1"
                        ]
                    ],
                    "bids": [
                        [
                            "41006.3",
                            "0.30178218",
                            "0",
                            "2"
                        ]
                    ],
                    "ts": "1629966436396"
                }
            ]
        }

        mock_api.get(regex_url, body=json.dumps(resp))

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(int(resp["data"][0]["ts"]) * 1e-3, msg.timestamp)
        expected_update_id = int(int(resp["data"][0]["ts"]) * 1e-3)
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(1, len(bids))
        self.assertEqual(41006.3, bids[0].price)
        self.assertEqual(0.30178218, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(41006.8, asks[0].price)
        self.assertEqual(0.60038921, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    def test_channel_originating_message_snapshot_queue(self):
        event_message = {
            "arg": {
                "channel": "books",
                "instId": self.trading_pair
            },
            "action": "snapshot",
            "data": [
                {
                    "asks": [
                        ["8476.98", "415", "0", "13"],
                    ],
                    "bids": [
                        ["8476.97", "256", "0", "12"],
                    ],
                    "ts": "1597026383085",
                    "checksum": -855196043
                }
            ]
        }
        channel_result = self.data_source._channel_originating_message(event_message)
        self.assertEqual(channel_result, self.data_source._snapshot_messages_queue_key)

    def test_channel_originating_message_diff_queue(self):
        event_message = {
            "arg": {
                "channel": "books",
                "instId": self.trading_pair
            },
            "action": "update",
            "data": [
                {
                    "asks": [
                        ["8476.98", "415", "0", "13"],
                    ],
                    "bids": [
                        ["8476.97", "256", "0", "12"],
                    ],
                    "ts": "1597026383085",
                    "checksum": -855196043
                }
            ]
        }
        channel_result = self.data_source._channel_originating_message(event_message)
        self.assertEqual(channel_result, self.data_source._diff_messages_queue_key)
