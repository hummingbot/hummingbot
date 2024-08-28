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
from hummingbot.connector.exchange.hashkey import hashkey_constants as CONSTANTS, hashkey_web_utils as web_utils
from hummingbot.connector.exchange.hashkey.hashkey_api_order_book_data_source import HashkeyAPIOrderBookDataSource
from hummingbot.connector.exchange.hashkey.hashkey_exchange import HashkeyExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_message import OrderBookMessage


class TestHashkeyAPIOrderBookDataSource(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "ETH"
        cls.quote_asset = "USD"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = CONSTANTS.DEFAULT_DOMAIN

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.async_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = HashkeyExchange(
            client_config_map=client_config_map,
            hashkey_api_key="",
            hashkey_api_secret="",
            trading_pairs=[self.trading_pair])

        self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self.time_synchronnizer = TimeSynchronizer()
        self.time_synchronnizer.add_time_offset_ms_sample(1000)
        self.ob_data_source = HashkeyAPIOrderBookDataSource(
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
            "symbol": "ETHUSD",
            "symbolName": "ETHUSD",
            "status": "TRADING",
            "baseAsset": "ETH",
            "baseAssetName": "ETH",
            "baseAssetPrecision": "0.0001",
            "quoteAsset": "USD",
            "quoteAssetName": "USD",
            "quotePrecision": "0.0000001",
            "retailAllowed": True,
            "piAllowed": True,
            "corporateAllowed": True,
            "omnibusAllowed": True,
            "icebergAllowed": True,
            "isAggregate": True,
            "allowMargin": True,
            "filters": [
                {
                    "minPrice": "0.01",
                    "maxPrice": "100000.00000000",
                    "tickSize": "0.01",
                    "filterType": "PRICE_FILTER"
                },
                {
                    "minQty": "0.005",
                    "maxQty": "53",
                    "stepSize": "0.0001",
                    "filterType": "LOT_SIZE"
                },
                {
                    "minNotional": "10",
                    "filterType": "MIN_NOTIONAL"
                },
                {
                    "minAmount": "10",
                    "maxAmount": "10000000",
                    "minBuyPrice": "0",
                    "filterType": "TRADE_AMOUNT"
                },
                {
                    "maxSellPrice": "0",
                    "buyPriceUpRate": "0.2",
                    "sellPriceDownRate": "0.2",
                    "filterType": "LIMIT_TRADING"
                },
                {
                    "buyPriceUpRate": "0.2",
                    "sellPriceDownRate": "0.2",
                    "filterType": "MARKET_TRADING"
                },
                {
                    "noAllowMarketStartTime": "0",
                    "noAllowMarketEndTime": "0",
                    "limitOrderStartTime": "0",
                    "limitOrderEndTime": "0",
                    "limitMinPrice": "0",
                    "limitMaxPrice": "0",
                    "filterType": "OPEN_QUOTE"
                }
            ]
        }
        return exchange_rules

    # ORDER BOOK SNAPSHOT
    @staticmethod
    def _snapshot_response() -> Dict:
        snapshot = {
            "t": 1703613017099,
            "b": [
                [
                    "2500",
                    "1"
                ]
            ],
            "a": [
                [
                    "25981.04",
                    "0.69773"
                ],
                [
                    "25981.76",
                    "0.09316"
                ],
            ]
        }
        return snapshot

    @staticmethod
    def _snapshot_response_processed() -> Dict:
        snapshot_processed = {
            "t": 1703613017099,
            "b": [
                [
                    "2500",
                    "1"
                ]
            ],
            "a": [
                [
                    "25981.04",
                    "0.69773"
                ],
                [
                    "25981.76",
                    "0.09316"
                ],
            ]
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
        self.assertEqual(2500, bid_entries[0].price)
        self.assertEqual(1, bid_entries[0].amount)
        self.assertEqual(int(resp["t"]), bid_entries[0].update_id)
        self.assertEqual(2, len(ask_entries))
        self.assertEqual(25981.04, ask_entries[0].price)
        self.assertEqual(0.69773, ask_entries[0].amount)
        self.assertEqual(25981.76, ask_entries[1].price)
        self.assertEqual(0.09316, ask_entries[1].amount)
        self.assertEqual(int(resp["t"]), ask_entries[0].update_id)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_trades_and_depth(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_trades = {
            "symbol": self.trading_pair,
            "symbolName": self.trading_pair,
            "topic": "trade",
            "event": "sub",
            "params": {
                "binary": False,
                "realtimeInterval": "24h",
            },
            "f": True,
            "sendTime": 1688198964293,
            "shared": False,
            "id": "1"
        }

        result_subscribe_depth = {
            "symbol": self.trading_pair,
            "symbolName": self.trading_pair,
            "topic": "depth",
            "event": "sub",
            "params": {
                "binary": False,
            },
            "f": True,
            "sendTime": 1688198964293,
            "shared": False,
            "id": "1"
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
            "topic": "trade",
            "event": "sub",
            "symbol": self.ex_trading_pair,
            "params": {
                "binary": False
            }
        }
        self.assertEqual(expected_trade_subscription, sent_subscription_messages[0])

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.hashkey.hashkey_api_order_book_data_source.HashkeyAPIOrderBookDataSource._time")
    def test_listen_for_subscriptions_sends_ping_message_before_ping_interval_finishes(
            self,
            time_mock,
            ws_connect_mock):

        time_mock.side_effect = [1000, 1100, 1101, 1102]  # Simulate first ping interval is already due

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_trades = {
            "symbol": self.trading_pair,
            "symbolName": self.trading_pair,
            "topic": "trade",
            "event": "sub",
            "params": {
                "binary": False,
                "realtimeInterval": "24h",
            },
            "id": "1"
        }

        result_subscribe_depth = {
            "symbol": self.trading_pair,
            "symbolName": self.trading_pair,
            "topic": "depth",
            "event": "sub",
            "params": {
                "binary": False,
            },
            "id": "1"
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

        expected_ping_message = {
            "ping": int(1101 * 1e3)
        }
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
        self.ob_data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.ob_data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_trades_logs_exception(self):
        incomplete_resp = {
            "symbol": self.trading_pair,
            "symbolName": self.trading_pair,
            "topic": "trade",
            "event": "sub",
            "params": {
                "binary": False,
            },
            "id": "1",
            "data": [
                {
                    "v": "1447335405363150849",
                    "t": 1687271825415,
                    "p": "10001",
                    "q": "0.001",
                    "m": False,
                },
                {
                    "v": "1447337171483901952",
                    "t": 1687272035953,
                    "p": "10001.1",
                    "q": "0.001",
                    "m": True
                },
            ]
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.ob_data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.ob_data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_trades_successful(self):
        mock_queue = AsyncMock()
        trade_event = {
            "symbol": self.ex_trading_pair,
            "symbolName": self.ex_trading_pair,
            "topic": "trade",
            "params": {
                "realtimeInterval": "24h",
                "binary": "false"
            },
            "data": [
                {
                    "v": "929681067596857345",
                    "t": 1625562619577,
                    "p": "34924.15",
                    "q": "0.00027",
                    "m": True
                }
            ],
            "f": True,
            "sendTime": 1626249138535,
            "shared": False
        }
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

        self.assertTrue(trade_event["data"][0]["t"], msg.trade_id)

    def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.ob_data_source._message_queue[CONSTANTS.SNAPSHOT_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(
                self.ob_data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
            )

    @aioresponses()
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    def test_listen_for_order_book_snapshots_log_exception(self, mock_api, sleep_mock):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = ['ERROR', asyncio.CancelledError]
        self.ob_data_source._message_queue[CONSTANTS.SNAPSHOT_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()
        sleep_mock.side_effect = [asyncio.CancelledError]
        url = web_utils.rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, exception=Exception)

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.ob_data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue))

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

        self.assertEqual(int(snapshot_data["t"]), msg.update_id)

    def test_listen_for_order_book_snapshots_successful_ws(self):
        mock_queue = AsyncMock()
        snapshot_event = {
            "symbol": self.ex_trading_pair,
            "symbolName": self.ex_trading_pair,
            "topic": "depth",
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
        self.ob_data_source._message_queue[CONSTANTS.SNAPSHOT_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            self.listening_task = self.ev_loop.create_task(
                self.ob_data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
            )
        except asyncio.CancelledError:
            pass

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get(),
                                                            timeout=6)

        self.assertTrue(snapshot_event["data"][0]["t"], msg.update_id)
