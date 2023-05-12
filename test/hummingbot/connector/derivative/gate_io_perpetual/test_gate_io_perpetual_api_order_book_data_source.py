import asyncio
import json
import re
from decimal import Decimal
from typing import Awaitable, Dict
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.gate_io_perpetual.gate_io_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.gate_io_perpetual import gate_io_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.gate_io_perpetual.gate_io_perpetual_api_order_book_data_source import (
    GateIoPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.gate_io_perpetual.gate_io_perpetual_derivative import GateIoPerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class GateIoPerpetualAPIOrderBookDataSourceTests(TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}_{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = GateIoPerpetualDerivative(
            client_config_map,
            gate_io_perpetual_api_key="",
            gate_io_perpetual_secret_key="",
            gate_io_perpetual_user_id="",
            trading_pairs=[self.trading_pair],
        )
        self.data_source = GateIoPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
        )

        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

        self.connector._set_trading_pair_symbol_map(
            bidict({f"{self.base_asset}_{self.quote_asset}": self.trading_pair}))

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

    def get_rest_snapshot_msg(self) -> Dict:
        return {
            "id": 123456,
            "current": 1623898993.123,
            "update": 1623898993.121,
            "asks": [
                {
                    "p": "1.52",
                    "s": 100
                },
                {
                    "p": "1.53",
                    "s": 40
                }
            ],
            "bids": [
                {
                    "p": "1.17",
                    "s": 150
                },
                {
                    "p": "1.16",
                    "s": 203
                }
            ]
        }

    def get_ws_snapshot_msg(self) -> Dict:
        return {
            "channel": "futures.order_book",
            "event": "all",
            "time": 1541500161,
            "result": {
                "t": 1541500161123,
                "contract": self.ex_trading_pair,
                "id": 93973511,
                "asks": [
                    {
                        "p": "97.1",
                        "s": 2245
                    },
                    {
                        "p": "97.1",
                        "s": 2245
                    }
                ],
                "bids": [
                    {
                        "p": "97.1",
                        "s": 2245
                    },
                    {
                        "p": "97.1",
                        "s": 2245
                    }
                ]
            }
        }

    def get_ws_diff_msg(self) -> Dict:
        return {
            "time": 1615366381,
            "channel": "futures.order_book_update",
            "event": "update",
            "error": None,
            "result": {
                "t": 1615366381417,
                "s": self.ex_trading_pair,
                "U": 2517661101,
                "u": 2517661113,
                "b": [
                    {
                        "p": "54672.1",
                        "s": 0
                    },
                    {
                        "p": "54664.5",
                        "s": 58794
                    }
                ],
                "a": [
                    {
                        "p": "54743.6",
                        "s": 0
                    },
                    {
                        "p": "54742",
                        "s": 95
                    }
                ]
            }
        }

    def get_funding_info_msg(self) -> Dict:
        return {
            "name": self.ex_trading_pair,
            "type": "direct",
            "quanto_multiplier": "0.0001",
            "ref_discount_rate": "0",
            "order_price_deviate": "0.5",
            "maintenance_rate": "0.005",
            "mark_type": "index",
            "last_price": "38026",
            "mark_price": "37985.6",
            "index_price": "37954.92",
            "funding_rate_indicative": "0.000219",
            "mark_price_round": "0.01",
            "funding_offset": 0,
            "in_delisting": False,
            "risk_limit_base": "1000000",
            "interest_rate": "0.0003",
            "order_price_round": "0.1",
            "order_size_min": 1,
            "ref_rebate_rate": "0.2",
            "funding_interval": 28800,
            "risk_limit_step": "1000000",
            "leverage_min": "1",
            "leverage_max": "100",
            "risk_limit_max": "8000000",
            "maker_fee_rate": "-0.00025",
            "taker_fee_rate": "0.00075",
            "funding_rate": "0.002053",
            "order_size_max": 1000000,
            "funding_next_apply": 1610035200,
            "short_users": 977,
            "config_change_time": 1609899548,
            "trade_size": 28530850594,
            "position_size": 5223816,
            "long_users": 455,
            "funding_impact_value": "60000",
            "orders_limit": 50,
            "trade_id": 10851092,
            "orderbook_id": 2129638396
        }

    def get_funding_info_rest_msg(self):
        return {
            "name": self.ex_trading_pair,
            "type": "direct",
            "quanto_multiplier": "0.0001",
            "ref_discount_rate": "0",
            "order_price_deviate": "0.5",
            "maintenance_rate": "0.005",
            "mark_type": "index",
            "last_price": "38026",
            "mark_price": "37985.6",
            "index_price": "37954.92",
            "funding_rate_indicative": "0.000219",
            "mark_price_round": "0.01",
            "funding_offset": 0,
            "in_delisting": False,
            "risk_limit_base": "1000000",
            "interest_rate": "0.0003",
            "order_price_round": "0.1",
            "order_size_min": 1,
            "ref_rebate_rate": "0.2",
            "funding_interval": 28800,
            "risk_limit_step": "1000000",
            "leverage_min": "1",
            "leverage_max": "100",
            "risk_limit_max": "8000000",
            "maker_fee_rate": "-0.00025",
            "taker_fee_rate": "0.00075",
            "funding_rate": "0.002053",
            "order_size_max": 1000000,
            "funding_next_apply": 1610035200,
            "short_users": 977,
            "config_change_time": 1609899548,
            "trade_size": 28530850594,
            "position_size": 5223816,
            "long_users": 455,
            "funding_impact_value": "60000",
            "orders_limit": 50,
            "trade_id": 10851092,
            "orderbook_id": 2129638396
        }

    @aioresponses()
    def test_get_new_order_book_successful(self, mock_api):
        self._simulate_trading_rules_initialized()
        endpoint = CONSTANTS.ORDER_BOOK_PATH_URL
        url = web_utils.public_rest_url(endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        resp = self.get_rest_snapshot_msg()
        mock_api.get(regex_url, body=json.dumps(resp))

        order_book = self.async_run_with_timeout(
            self.data_source.get_new_order_book(self.trading_pair)
        )

        self.assertEqual(123456, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(2, len(bids))
        self.assertEqual(1.17, bids[0].price)
        self.assertEqual(0.00015, bids[0].amount)
        self.assertEqual(2, len(asks))
        self.assertEqual(1.52, asks[0].price)
        self.assertEqual(0.0001, asks[0].amount)

    @aioresponses()
    def test_get_new_order_book_raises_exception(self, mock_api):
        endpoint = CONSTANTS.ORDER_BOOK_PATH_URL
        url = web_utils.public_rest_url(endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                self.data_source.get_new_order_book(self.trading_pair)
            )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_trades_diffs_and_orderbooks(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_diffs = self.get_ws_snapshot_msg()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_diffs),
        )
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )

        self.assertEqual(2, len(sent_subscription_messages))
        expected_trade_subscription_channel = CONSTANTS.TRADES_ENDPOINT_NAME
        expected_trade_subscription_payload = [self.ex_trading_pair]
        self.assertEqual(expected_trade_subscription_channel, sent_subscription_messages[0]["channel"])
        self.assertEqual(expected_trade_subscription_payload, sent_subscription_messages[0]["payload"])
        expected_trade_subscription_channel = CONSTANTS.ORDERS_UPDATE_ENDPOINT_NAME
        expected_trade_subscription_payload = [self.ex_trading_pair, "100ms"]
        self.assertEqual(expected_trade_subscription_channel, sent_subscription_messages[1]["channel"])
        self.assertEqual(expected_trade_subscription_payload, sent_subscription_messages[1]["payload"])

        self.assertTrue(
            self._is_logged("INFO", "Subscribed to public order book and trade channels...")
        )

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
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."
            )
        )

    def test_subscribe_to_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source._subscribe_channels(mock_ws)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_subscribe_to_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            self.listening_task = self.ev_loop.create_task(
                self.data_source._subscribe_channels(mock_ws)
            )
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
            "channel": "futures.trades",
            "event": "update",
            "time": 1541503698,
            "result": [
                {
                    "size": -108,
                    "id": 27753479,
                    "create_time": 1545136464,
                    "create_time_ms": 1545136464123,
                    "price": "96.4",
                    "contract": "BTC_USD"
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
        self._simulate_trading_rules_initialized()
        mock_queue = AsyncMock()
        trade_event = {
            "channel": "futures.trades",
            "event": "update",
            "time": 1541503698,
            "result": [
                {
                    "size": -108,
                    "id": "00c706e1-ba52-5bb0-98d0-bf694bdc69f7",
                    "create_time": 1545136464,
                    "create_time_ms": 1545136464123,
                    "price": "96.4",
                    "contract": self.ex_trading_pair
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
        self.assertEqual(trade_event["result"][0]["id"], msg.trade_id)
        self.assertEqual(trade_event["result"][0]["create_time"], msg.timestamp)

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
        incomplete_resp = self.get_ws_diff_msg()
        del incomplete_resp["result"]["u"]

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
        self._simulate_trading_rules_initialized()
        mock_queue = AsyncMock()
        diff_event = self.get_ws_diff_msg()
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.DIFF, msg.type)
        self.assertEqual(-1, msg.trade_id)
        expected_update_id = int(diff_event["result"]["u"])
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(2, len(bids))
        self.assertEqual(54672.1, bids[0].price)
        self.assertEqual(0, bids[0].amount)
        self.assertEqual(2, len(asks))
        self.assertEqual(54743.6, asks[0].price)
        self.assertEqual(0, asks[0].amount)

    @aioresponses()
    def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        endpoint = CONSTANTS.ORDER_BOOK_PATH_URL
        url = web_utils.public_rest_url(
            endpoint=endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.get(regex_url, exception=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, asyncio.Queue())
            )

    @aioresponses()
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    def test_listen_for_order_book_snapshots_log_exception(self, mock_api, sleep_mock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        endpoint = CONSTANTS.ORDER_SNAPSHOT_ENDPOINT_NAME
        url = web_utils.public_rest_url(
            endpoint=endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.get(regex_url, exception=Exception)

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}.")
        )

    @aioresponses()
    def test_listen_for_order_book_snapshots_successful(self, mock_api):
        self._simulate_trading_rules_initialized()
        msg_queue: asyncio.Queue = asyncio.Queue()
        endpoint = CONSTANTS.ORDER_BOOK_PATH_URL
        url = web_utils.public_rest_url(
            endpoint=endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        resp = self.get_rest_snapshot_msg()

        mock_api.get(regex_url, body=json.dumps(resp))

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(-1, msg.trade_id)
        expected_update_id = resp["id"]
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(2, len(bids))
        self.assertEqual(1.17, bids[0].price)
        self.assertEqual(0.00015, bids[0].amount)
        self.assertEqual(2, len(asks))
        self.assertEqual(1.52, asks[0].price)
        self.assertEqual(0.0001, asks[0].amount)

    @aioresponses()
    def test_get_funding_info(self, mock_api):
        endpoint = CONSTANTS.MARK_PRICE_URL.format(id=self.ex_trading_pair)
        url = web_utils.public_rest_url(endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        resp = self.get_funding_info_rest_msg()
        mock_api.get(regex_url, body=json.dumps(resp))

        funding_info: FundingInfo = self.async_run_with_timeout(
            self.data_source.get_funding_info(self.trading_pair)
        )
        msg_result = resp

        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(Decimal(str(msg_result["index_price"])), funding_info.index_price)
        self.assertEqual(Decimal(str(msg_result["mark_price"])), funding_info.mark_price)
        self.assertEqual(msg_result["funding_next_apply"], funding_info.next_funding_utc_timestamp)
        self.assertEqual(Decimal(str(msg_result["funding_rate_indicative"])), funding_info.rate)

    def _simulate_trading_rules_initialized(self):
        self.connector._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }
