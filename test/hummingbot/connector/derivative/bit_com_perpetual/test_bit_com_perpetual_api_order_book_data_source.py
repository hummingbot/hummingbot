import asyncio
import json
import re
from decimal import Decimal
from typing import Awaitable, Dict
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.bit_com_perpetual import bit_com_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_api_order_book_data_source import (
    BitComPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_derivative import BitComPerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class BitComPerpetualAPIOrderBookDataSourceTests(TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "BTC"
        cls.quote_asset = "USD"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}-PERPETUAL"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = BitComPerpetualDerivative(
            client_config_map,
            bit_com_perpetual_api_key="",
            bit_com_perpetual_api_secret="",
            trading_pairs=[self.trading_pair],
        )
        self.data_source = BitComPerpetualAPIOrderBookDataSource(
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
            bidict({f"{self.base_asset}-{self.quote_asset}-PERPETUAL": self.trading_pair}))

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
            "code": 0,
            "message": "",
            "data": {
                "instrument_id": "BTC-USD-PERPETUAL",
                "timestamp": 1642994567453,
                "bids": [
                    ["35324.15000000", "0.47000000"],
                    ["35324.10000000", "1.67000000"],
                    ["35321.95000000", "2.40000000"],
                    ["35321.90000000", "4.36000000"],
                    ["35321.85000000", "1.24000000"]
                ],
                "asks": [
                    ["35325.15000000", "4.68000000"],
                    ["35327.80000000", "0.53000000"],
                    ["35351.00000000", "1.00000000"],
                    ["35352.00000000", "1.00000000"],
                    ["35353.00000000", "1.00000000"]
                ]
            }
        }

    def get_ws_snapshot_msg(self) -> Dict:
        return {
            "channel": "depth",
            "timestamp": 1643094930373,
            "module": "linear",
            "data": {
                "type": "snapshot",
                "instrument_id": "BTC-USD-PERPETUAL",
                "sequence": 9,
                "bids": [
                    [
                        "35731.05000000",
                        "6.82000000"
                    ]
                ],
                "asks": [
                    [
                        "35875.00000000",
                        "1.00000000"
                    ]
                ]
            }
        }

    def get_ws_diff_msg(self) -> Dict:
        return {
            "channel": "depth",
            "timestamp": 1643094930373,
            "module": "linear",
            "data": {
                "type": "update",
                "instrument_id": "BTC-USD-PERPETUAL",
                "sequence": 10,
                "prev_sequence": 9,
                "changes": [
                    [
                        "sell",
                        "35733.00000000",
                        "1.10000000"
                    ],
                    [
                        "buy",
                        "35732.00000000",
                        "1.10000000"
                    ]
                ]
            }
        }

    def get_funding_info_msg(self) -> Dict:
        return {
            "code": 0,
            "message": "",
            "data": {
                "instrument_id": "BTC-USD-PERPETUAL",
                "time": 1635913370000,
                "funding_rate": "0.00000000",
                "funding_rate_8h": "-0.00102858",
                "index_price": "62989.63000000",
                "mark_price": "62969.83608581"
            }
        }

    def get_funding_info_rest_msg(self):
        return {
            "code": 0,
            "message": "",
            "data": {
                "instrument_id": "BTC-USD-PERPETUAL",
                "time": 1635913370000,
                "funding_rate": "0.00000000",
                "funding_rate_8h": "-0.00102858",
                "index_price": "62989.63000000",
                "mark_price": "62969.83608581"
            }
        }

    @aioresponses()
    def test_get_new_order_book_successful(self, mock_api):
        endpoint = CONSTANTS.SNAPSHOT_REST_URL
        url = web_utils.public_rest_url(endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        resp = self.get_rest_snapshot_msg()
        mock_api.get(regex_url, body=json.dumps(resp))

        order_book = self.async_run_with_timeout(
            self.data_source.get_new_order_book(self.trading_pair)
        )

        self.assertEqual(1642994567453, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(5, len(bids))
        self.assertEqual(35324.15, bids[0].price)
        self.assertEqual(0.47, bids[0].amount)
        self.assertEqual(5, len(asks))
        self.assertEqual(35325.15, asks[0].price)
        self.assertEqual(4.68, asks[0].amount)

    @aioresponses()
    def test_get_new_order_book_raises_exception(self, mock_api):
        endpoint = CONSTANTS.SNAPSHOT_REST_URL
        url = web_utils.public_rest_url(endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))

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

        self.assertEqual(3, len(sent_subscription_messages))
        expected_trade_subscription_channel = [CONSTANTS.TRADES_ENDPOINT_NAME]
        expected_trade_subscription_payload = [self.ex_trading_pair]
        self.assertEqual(expected_trade_subscription_channel, sent_subscription_messages[0]["channels"])
        self.assertEqual(expected_trade_subscription_payload, sent_subscription_messages[0]["instruments"])
        expected_depth_subscription_channel = [CONSTANTS.ORDERS_UPDATE_ENDPOINT_NAME]
        expected_depth_subscription_payload = [self.ex_trading_pair]
        self.assertEqual(expected_depth_subscription_channel, sent_subscription_messages[1]["channels"])
        self.assertEqual(expected_depth_subscription_payload, sent_subscription_messages[1]["instruments"])
        expected_funding_rate_subscription_channel = [CONSTANTS.FUNDING_INFO_STREAM_NAME]
        expected_funding_rate_subscription_payload = [self.ex_trading_pair]
        self.assertEqual(expected_funding_rate_subscription_channel, sent_subscription_messages[2]["channels"])
        self.assertEqual(expected_funding_rate_subscription_payload, sent_subscription_messages[2]["instruments"])

        self.assertTrue(
            self._is_logged("INFO", "Subscribed to public order book, trade and fundingrate channels...")
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
            "code": 0,
            "message": "",
            "data": [
                {
                    "created_at": 1642994704633,
                    "trade_id": 1005483402,
                    "instrument_id": "BTC-USD-PERPETUAL",
                    "qty": "1.00000000",
                    "side": "sell",
                    "sigma": "0.00000000",
                    "index_price": "2447.79750000",
                    "underlying_price": "0.00000000",
                    "is_block_trade": False
                },
                {
                    "created_at": 1642994704241,
                    "trade_id": 1005483400,
                    "instrument_id": "BTC-USD-PERPETUAL",
                    "qty": "1.00000000",
                    "side": "sell",
                    "sigma": "0.00000000",
                    "index_price": "2447.79750000",
                    "underlying_price": "0.00000000",
                    "is_block_trade": False
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
            "code": 0,
            "timestamp": 1643099734031,
            "channel": "trade",
            "data": [
                {
                    "created_at": 1642994704633,
                    "trade_id": 1005483402,
                    "instrument_id": "BTC-USD-PERPETUAL",
                    "price": "2449.20000000",
                    "qty": "1.00000000",
                    "side": "sell",
                    "sigma": "0.00000000",
                    "index_price": "2447.79750000",
                    "underlying_price": "0.00000000",
                    "is_block_trade": False
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
        self.assertEqual(trade_event["data"][0]["trade_id"], msg.trade_id)
        self.assertEqual(trade_event["timestamp"] * 1e-3, msg.timestamp)

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
        del incomplete_resp["data"]["sequence"]

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
        diff_event = self.get_ws_diff_msg()
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.DIFF, msg.type)
        self.assertEqual(-1, msg.trade_id)
        expected_update_id = int(diff_event["data"]["sequence"])
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(1, len(bids))
        self.assertEqual(35732, bids[0].price)
        self.assertEqual(1.1, bids[0].amount)
        self.assertEqual(1, len(asks))
        self.assertEqual(35733, asks[0].price)
        self.assertEqual(1.1, asks[0].amount)

    @aioresponses()
    def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        endpoint = CONSTANTS.SNAPSHOT_REST_URL
        url = web_utils.public_rest_url(endpoint)
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

        endpoint = CONSTANTS.SNAPSHOT_REST_URL
        url = web_utils.public_rest_url(endpoint)
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
        msg_queue: asyncio.Queue = asyncio.Queue()
        endpoint = CONSTANTS.SNAPSHOT_REST_URL
        url = web_utils.public_rest_url(endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

        resp = self.get_rest_snapshot_msg()

        mock_api.get(regex_url, body=json.dumps(resp))

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(-1, msg.trade_id)
        expected_update_id = resp["data"]["timestamp"]
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(5, len(bids))
        self.assertEqual(35324.15, bids[0].price)
        self.assertEqual(0.47, bids[0].amount)
        self.assertEqual(5, len(asks))
        self.assertEqual(35325.15, asks[0].price)
        self.assertEqual(4.68, asks[0].amount)

    @aioresponses()
    def test_get_funding_info(self, mock_api):
        endpoint = CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL
        url = web_utils.public_rest_url(endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        resp = self.get_funding_info_rest_msg()
        mock_api.get(regex_url, body=json.dumps(resp))

        funding_info: FundingInfo = self.async_run_with_timeout(
            self.data_source.get_funding_info(self.trading_pair)
        )
        msg_result = resp

        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(Decimal(str(msg_result["data"]["mark_price"])), funding_info.mark_price)
        self.assertEqual((int(msg_result["data"]["time"] / CONSTANTS.FUNDING_RATE_INTERNAL_MIL_SECOND) + 1) *
                         CONSTANTS.FUNDING_RATE_INTERNAL_MIL_SECOND,
                         funding_info.next_funding_utc_timestamp)
        self.assertEqual(Decimal(str(msg_result["data"]["funding_rate"])), funding_info.rate)
