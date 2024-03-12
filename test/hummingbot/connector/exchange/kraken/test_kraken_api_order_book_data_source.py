import asyncio
import json
import re
import unittest
from typing import Awaitable
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.kraken import kraken_constants as CONSTANTS, kraken_web_utils as web_utils
from hummingbot.connector.exchange.kraken.kraken_api_order_book_data_source import KrakenAPIOrderBookDataSource
from hummingbot.connector.exchange.kraken.kraken_constants import KrakenAPITier
from hummingbot.connector.exchange.kraken.kraken_exchange import KrakenExchange
from hummingbot.connector.exchange.kraken.kraken_utils import build_rate_limits_by_tier
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook, OrderBookMessage


class KrakenAPIOrderBookDataSourceTest(unittest.TestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.ws_ex_trading_pairs = cls.base_asset + "/" + cls.quote_asset
        cls.api_tier = KrakenAPITier.STARTER

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.throttler = AsyncThrottler(build_rate_limits_by_tier(self.api_tier))
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = KrakenExchange(
            client_config_map=client_config_map,
            kraken_api_key="",
            kraken_secret_key="",
            trading_pairs=[],
            trading_required=False)
        self.data_source = KrakenAPIOrderBookDataSource(
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            trading_pairs=[self.trading_pair])

        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

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

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _trade_update_event(self):
        resp = [
            0,
            [
                [
                    "5541.20000",
                    "0.15850568",
                    "1534614057.321597",
                    "s",
                    "l",
                    ""
                ]
            ],
            "trade",
            f"{self.base_asset}/{self.quote_asset}"
        ]
        return resp

    def _order_diff_event(self):
        resp = [
            1234,
            {
                "a": [
                    [
                        "5541.30000",
                        "2.50700000",
                        "1534614248.456738"
                    ],
                    [
                        "5542.50000",
                        "0.40100000",
                        "1534614248.456738"
                    ]
                ],
                "c": "974942666"
            },
            "book-10",
            "XBT/USD"
        ]
        return resp

    def _snapshot_response(self):
        resp = {
            "error": [],
            "result": {
                f"X{self.base_asset}{self.quote_asset}": {
                    "asks": [
                        [
                            "52523.00000",
                            "1.199",
                            1616663113
                        ],
                        [
                            "52536.00000",
                            "0.300",
                            1616663112
                        ]
                    ],
                    "bids": [
                        [
                            "52522.90000",
                            "0.753",
                            1616663112
                        ],
                        [
                            "52522.80000",
                            "0.006",
                            1616663109
                        ]
                    ]
                }
            }
        }
        return resp

    @aioresponses()
    def test_get_new_order_book_successful(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL)
        regex_url = re.compile(f"^{url}?pair={self.ex_trading_pair}".replace(".", r"\.").replace("?", r"\?"))

        resp = self._snapshot_response()

        mock_api.get(regex_url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))

        self.assertTrue(isinstance(ret, OrderBook))

        bids_df, asks_df = ret.snapshot
        pair_data = resp["result"][f"X{self.base_asset}{self.quote_asset}"]
        first_bid_price = float(pair_data["bids"][0][0])
        first_ask_price = float(pair_data["asks"][0][0])

        self.assertEqual(first_bid_price, bids_df.iloc[0]["price"])
        self.assertEqual(first_ask_price, asks_df.iloc[0]["price"])

    @aioresponses()
    def test_get_new_order_book_raises_exception(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL)
        regex_url = re.compile(f"^{url}?pair={self.ex_trading_pair}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                self.data_source.get_new_order_book(self.trading_pair)
            )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_trades = {
            "code": None,
            "id": 1
        }
        result_subscribe_diffs = {
            "code": None,
            "id": 2
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
            "event": "subscribe",
            "pair": [self.ws_ex_trading_pairs],
            "subscription": {"name": 'trade'},
        }
        self.assertEqual(expected_trade_subscription, sent_subscription_messages[0])
        expected_diff_subscription = {
            "event": "subscribe",
            "pair": [self.ws_ex_trading_pairs],
            "subscription": {"name": 'book', "depth": 1000},
        }
        self.assertEqual(expected_diff_subscription, sent_subscription_messages[1])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to public order book and trade channels..."
        ))

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
            self._is_logged("ERROR", "Unexpected error occurred subscribing to order book data streams.")
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
            "m": 1,
            "i": 2,
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
        mock_queue.get.side_effect = [self._trade_update_event(), asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(1534614057.321597, msg.trade_id)

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
            "m": 1,
            "i": 2,
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
        diff_event = self._order_diff_event()
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(diff_event[1]["a"][0][2], str(msg.update_id))

    @aioresponses()
    def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL)
        regex_url = re.compile(f"^{url}?pair={self.ex_trading_pair}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=asyncio.CancelledError, repeat=True)

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, asyncio.Queue())
            )

    @aioresponses()
    @patch("hummingbot.connector.exchange.kraken.kraken_api_order_book_data_source"
           ".KrakenAPIOrderBookDataSource._sleep")
    def test_listen_for_order_book_snapshots_log_exception(self, mock_api, sleep_mock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL)
        regex_url = re.compile(f"^{url}?pair={self.ex_trading_pair}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=Exception, repeat=True)

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}."))

    @aioresponses()
    def test_listen_for_order_book_snapshots_successful(self, mock_api, ):
        msg_queue: asyncio.Queue = asyncio.Queue()
        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL)
        regex_url = re.compile(f"^{url}?pair={self.ex_trading_pair}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, body=json.dumps(self._snapshot_response()))

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(1616663113, msg.update_id)
