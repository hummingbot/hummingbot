import asyncio
import json
import re
from decimal import Decimal
from typing import Awaitable, Dict
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.bitget_perpetual import bitget_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_api_order_book_data_source import (
    BitgetPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_derivative import BitgetPerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class BitgetPerpetualAPIOrderBookDataSourceTests(TestCase):
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
        cls.domain = ""

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = BitgetPerpetualDerivative(
            client_config_map,
            bitget_perpetual_api_key="",
            bitget_perpetual_secret_key="",
            bitget_perpetual_passphrase="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
            domain=self.domain,
        )
        self.data_source = BitgetPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=self.domain,
        )

        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

        self.connector._set_trading_pair_symbol_map(
            bidict({f"{self.base_asset}{self.quote_asset}_UMCBL": self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def get_rest_snapshot_msg(self) -> Dict:
        return {
            "code": "00000",
            "data": {
                "asks": [
                    [
                        "9487.5",
                        "522147"
                    ],
                ],
                "bids": [
                    [
                        "9487",
                        "336241"
                    ],
                ],
                "timestamp": "1627115809358"
            },
            "msg": "success",
            "requestTime": 1627115809358
        }

    def get_ws_diff_msg(self) -> Dict:
        return {
            "action": "update",
            "arg": {
                "instType": "mc",
                "channel": CONSTANTS.WS_ORDER_BOOK_EVENTS_TOPIC,
                "instId": self.ex_trading_pair
            },
            "data": [
                {
                    "asks": [["3001", "0", "1", "4"]],
                    "bids": [
                        ["2999.0", "8", "1", "4"],
                        ["2998.0", "10", "1", "4"]
                    ],
                    "ts": "1627115809358"
                }
            ]
        }

    def ws_snapshot_msg(self) -> Dict:
        return {
            "action": "snapshot",
            "arg": {
                "instType": "mc",
                "channel": CONSTANTS.WS_ORDER_BOOK_EVENTS_TOPIC,
                "instId": self.ex_trading_pair
            },
            "data": [
                {
                    "asks": [["3001", "0", "1", "4"]],
                    "bids": [
                        ["2999.0", "8", "1", "4"],
                        ["2998.0", "10", "1", "4"]
                    ],
                    "ts": "1627115809358"
                }
            ]
        }

    def get_funding_info_msg(self) -> Dict:
        return {
            "action": "snapshot",
            "arg": {
                "instType": "mc",
                "channel": "ticker",
                "instId": self.ex_trading_pair,
            },
            "data": [
                {
                    "instId": self.ex_trading_pair,
                    "last": "44962.00",
                    "bestAsk": "44962",
                    "bestBid": "44961",
                    "high24h": "45136.50",
                    "low24h": "43620.00",
                    "priceChangePercent": "0.02",
                    "capitalRate": "-0.00010",
                    "nextSettleTime": 1632495600000,
                    "systemTime": 1632470889087,
                    "markPrice": "44936.21",
                    "indexPrice": "44959.23",
                    "holding": "1825.822",
                    "baseVolume": "39746.470",
                    "quoteVolume": "1760329683.834"
                }
            ]
        }

    def get_funding_info_event(self):
        return self.get_funding_info_msg()

    def get_funding_info_rest_msg(self):
        return {
            "data": {
                "symbol": self.ex_trading_pair,
                "index": "35000",
                "fundingTime": "1627311600000",
                "timestamp": "1627291836179",
                "fundingRate": "0.0002",
                "amount": "757.8338",
                "markPrice": "35000",
            },
        }

    @aioresponses()
    def test_get_new_order_book_successful(self, mock_api):
        endpoint = CONSTANTS.ORDER_BOOK_ENDPOINT
        url = web_utils.get_rest_url_for_endpoint(endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_rest_snapshot_msg()
        mock_api.get(regex_url, body=json.dumps(resp))

        order_book = self.async_run_with_timeout(
            self.data_source.get_new_order_book(self.trading_pair)
        )

        expected_update_id = int(resp["data"]["timestamp"])

        self.assertEqual(expected_update_id, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(1, len(bids))
        self.assertEqual(9487, bids[0].price)
        self.assertEqual(336241, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(9487.5, asks[0].price)
        self.assertEqual(522147, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @aioresponses()
    def test_get_new_order_book_raises_exception(self, mock_api):
        endpoint = CONSTANTS.ORDER_BOOK_ENDPOINT
        url = web_utils.get_rest_url_for_endpoint(endpoint=endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                self.data_source.get_new_order_book(self.trading_pair)
            )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_trades_diffs_and_funding_info(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_diffs = self.get_ws_diff_msg()
        result_subscribe_funding_info = self.get_funding_info_msg()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_diffs),
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_funding_info),
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )

        self.assertEqual(1, len(sent_subscription_messages))
        expected_subscription = {
            "op": "subscribe",
            "args": [
                {
                    "instType": "mc",
                    "channel": "books",
                    "instId": self.ex_trading_pair
                },
                {
                    "instType": "mc",
                    "channel": "trade",
                    "instId": self.ex_trading_pair
                },
                {
                    "instType": "mc",
                    "channel": "ticker",
                    "instId": self.ex_trading_pair
                }
            ],
        }

        self.assertEqual(expected_subscription, sent_subscription_messages[0])

        self.assertTrue(
            self._is_logged("INFO", "Subscribed to public order book, trade and funding info channels...")
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_for_usdc_product_type_pair(self, ws_connect_mock):
        local_base_asset = "BTC"
        local_quote_asset = "USDC"
        local_trading_pair = f"{local_base_asset}-{local_quote_asset}"
        local_exchange_trading_pair_without_type = f"{local_base_asset}{local_quote_asset}"
        local_exchange_trading_pair = f"{local_exchange_trading_pair_without_type}_{CONSTANTS.USDC_PRODUCT_TYPE}"

        local_data_source = BitgetPerpetualAPIOrderBookDataSource(
            trading_pairs=[local_trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=self.domain,
        )

        self.connector._set_trading_pair_symbol_map(
            bidict({f"{local_exchange_trading_pair}": local_trading_pair}))

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_diffs = self.get_ws_diff_msg()
        result_subscribe_funding_info = self.get_funding_info_msg()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_diffs),
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_funding_info),
        )

        self.listening_task = self.ev_loop.create_task(local_data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )

        self.assertEqual(1, len(sent_subscription_messages))
        expected_subscription = {
            "op": "subscribe",
            "args": [
                {
                    "instType": "mc",
                    "channel": "books",
                    "instId": local_exchange_trading_pair_without_type
                },
                {
                    "instType": "mc",
                    "channel": "trade",
                    "instId": local_exchange_trading_pair_without_type
                },
                {
                    "instType": "mc",
                    "channel": "ticker",
                    "instId": local_exchange_trading_pair_without_type
                }
            ],
        }

        self.assertEqual(expected_subscription, sent_subscription_messages[0])

        self.assertTrue(
            self._is_logged("INFO", "Subscribed to public order book, trade and funding info channels...")
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_for_usd_product_type_pair(self, ws_connect_mock):
        local_base_asset = "BTC"
        local_quote_asset = "USD"
        local_trading_pair = f"{local_base_asset}-{local_quote_asset}"
        local_exchange_trading_pair_without_type = f"{local_base_asset}{local_quote_asset}"
        local_exchange_trading_pair = f"{local_exchange_trading_pair_without_type}_{CONSTANTS.USD_PRODUCT_TYPE}"

        local_data_source = BitgetPerpetualAPIOrderBookDataSource(
            trading_pairs=[local_trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=self.domain,
        )

        self.connector._set_trading_pair_symbol_map(
            bidict({f"{local_exchange_trading_pair}": local_trading_pair}))

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_diffs = self.get_ws_diff_msg()
        result_subscribe_funding_info = self.get_funding_info_msg()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_diffs),
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_funding_info),
        )

        self.listening_task = self.ev_loop.create_task(local_data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )

        self.assertEqual(1, len(sent_subscription_messages))
        expected_subscription = {
            "op": "subscribe",
            "args": [
                {
                    "instType": "mc",
                    "channel": "books",
                    "instId": local_exchange_trading_pair_without_type
                },
                {
                    "instType": "mc",
                    "channel": "trade",
                    "instId": local_exchange_trading_pair_without_type
                },
                {
                    "instType": "mc",
                    "channel": "ticker",
                    "instId": local_exchange_trading_pair_without_type
                }
            ],
        }

        self.assertEqual(expected_subscription, sent_subscription_messages[0])

        self.assertTrue(
            self._is_logged("INFO", "Subscribed to public order book, trade and funding info channels...")
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
        sleep_mock.side_effect = asyncio.CancelledError()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR", "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds...",
            )
        )

    def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source._subscribe_channels(mock_ws)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            self.listening_task = self.ev_loop.create_task(
                self.data_source._subscribe_channels(mock_ws)
            )
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
        incomplete_resp = {}

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
            "action": "snapshot",
            "arg": {
                "instType": "mc",
                "channel": CONSTANTS.WS_TRADES_TOPIC,
                "instId": self.ex_trading_pair,
            },
            "data": [
                ["1632470889087", "10", "411.8", "buy"],
            ]
        }
        mock_queue.get.side_effect = [trade_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.TRADE, msg.type)
        self.assertEqual(int(trade_event["data"][0][0]), msg.trade_id)
        self.assertEqual(int(trade_event["data"][0][0]) * 1e-3, msg.timestamp)

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
        incomplete_resp["data"] = 1

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
        expected_update_id = int(diff_event["data"][0]["ts"])
        expected_timestamp = expected_update_id * 1e-3
        self.assertEqual(expected_timestamp, msg.timestamp)
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(2, len(bids))
        self.assertEqual(2999.0, bids[0].price)
        self.assertEqual(8, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(3001, asks[0].price)
        self.assertEqual(0, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @aioresponses()
    def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        endpoint = CONSTANTS.ORDER_BOOK_ENDPOINT
        url = web_utils.get_rest_url_for_endpoint(endpoint=endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, asyncio.Queue())
            )

    @aioresponses()
    def test_listen_for_order_book_snapshots_log_exception(self, mock_api):
        msg_queue: asyncio.Queue = asyncio.Queue()

        endpoint = CONSTANTS.ORDER_BOOK_ENDPOINT
        url = web_utils.get_rest_url_for_endpoint(endpoint=endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=Exception)
        mock_api.get(regex_url, exception=asyncio.CancelledError)

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )
        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}.")
        )

    @aioresponses()
    def test_listen_for_order_book_rest_snapshots_successful(self, mock_api):
        msg_queue: asyncio.Queue = asyncio.Queue()
        endpoint = CONSTANTS.ORDER_BOOK_ENDPOINT
        url = web_utils.get_rest_url_for_endpoint(endpoint=endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = self.get_rest_snapshot_msg()

        mock_api.get(regex_url, body=json.dumps(resp))

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(float(resp["data"]["timestamp"]) * 1e-3, msg.timestamp)
        expected_update_id = float(resp["data"]["timestamp"])
        expected_timestamp = expected_update_id * 1e-3
        self.assertEqual(expected_update_id, msg.update_id)
        self.assertEqual(expected_timestamp, msg.timestamp)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(1, len(bids))
        self.assertEqual(9487, bids[0].price)
        self.assertEqual(336241, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(9487.5, asks[0].price)
        self.assertEqual(522147, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    def test_listen_for_order_book_snapshots_successful(self):
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time

        mock_queue = AsyncMock()
        event = self.ws_snapshot_msg()
        mock_queue.get.side_effect = [event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(-1, msg.trade_id)
        expected_update_id = int(event["data"][0]["ts"])
        expected_timestamp = expected_update_id * 1e-3
        self.assertEqual(expected_timestamp, msg.timestamp)
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(2, len(bids))
        self.assertEqual(2999.0, bids[0].price)
        self.assertEqual(8, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(3001, asks[0].price)
        self.assertEqual(0, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    def test_listen_for_funding_info_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._funding_info_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_funding_info(msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_funding_info_logs_exception(self):
        incomplete_resp = self.get_funding_info_event()
        incomplete_resp["data"] = 1

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._funding_info_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_funding_info(msg_queue))

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public funding info updates from exchange"))

    def test_listen_for_funding_info_successful(self):
        funding_info_event = self.get_funding_info_event()

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [funding_info_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._funding_info_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_funding_info(msg_queue))

        msg: FundingInfoUpdate = self.async_run_with_timeout(msg_queue.get())
        funding_update = funding_info_event["data"][0]

        self.assertEqual(self.trading_pair, msg.trading_pair)
        expected_index_price = Decimal(str(funding_update["indexPrice"]))
        self.assertEqual(expected_index_price, msg.index_price)
        expected_mark_price = Decimal(str(funding_update["markPrice"]))
        self.assertEqual(expected_mark_price, msg.mark_price)
        expected_funding_time = int(funding_update["nextSettleTime"]) * 1e-3
        self.assertEqual(expected_funding_time, msg.next_funding_utc_timestamp)
        expected_rate = Decimal(funding_update["capitalRate"])
        self.assertEqual(expected_rate, msg.rate)

    @aioresponses()
    def test_get_funding_info(self, mock_api):
        rate_regex_url = re.compile(
            f"^{web_utils.get_rest_url_for_endpoint(CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL)}".replace(".", r"\.").replace("?", r"\?")
        )
        interest_regex_url = re.compile(
            f"^{web_utils.get_rest_url_for_endpoint(CONSTANTS.OPEN_INTEREST_PATH_URL)}".replace(".", r"\.").replace("?", r"\?")
        )
        mark_regex_url = re.compile(
            f"^{web_utils.get_rest_url_for_endpoint(CONSTANTS.MARK_PRICE_PATH_URL)}".replace(".", r"\.").replace("?", r"\?")
        )
        settlement_regex_url = re.compile(
            f"^{web_utils.get_rest_url_for_endpoint(CONSTANTS.FUNDING_SETTLEMENT_TIME_PATH_URL)}".replace(".", r"\.").replace("?", r"\?")
        )
        resp = self.get_funding_info_rest_msg()
        mock_api.get(rate_regex_url, body=json.dumps(resp))
        mock_api.get(interest_regex_url, body=json.dumps(resp))
        mock_api.get(mark_regex_url, body=json.dumps(resp))
        mock_api.get(settlement_regex_url, body=json.dumps(resp))

        funding_info: FundingInfo = self.async_run_with_timeout(
            self.data_source.get_funding_info(self.trading_pair)
        )
        msg_result = resp["data"]

        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(Decimal(str(msg_result["amount"])), funding_info.index_price)
        self.assertEqual(Decimal(str(msg_result["markPrice"])), funding_info.mark_price)
        self.assertEqual(int(msg_result["fundingTime"]) * 1e-3, funding_info.next_funding_utc_timestamp)
        self.assertEqual(Decimal(str(msg_result["fundingRate"])), funding_info.rate)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_events_enqueued_correctly_after_channel_detection(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        diff_event = self.get_ws_diff_msg()
        funding_event = self.get_funding_info_msg()
        trade_event = {
            "action": "snapshot",
            "arg": {
                "instType": "mc",
                "channel": CONSTANTS.WS_TRADES_TOPIC,
                "instId": self.ex_trading_pair,
            },
            "data": [
                ["1632470889087", "10", "411.8", "buy"],
            ]
        }
        snapshot_event = self.ws_snapshot_msg()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(snapshot_event),
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(diff_event),
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(funding_event),
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(trade_event),
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(1, self.data_source._message_queue[self.data_source._snapshot_messages_queue_key].qsize())
        self.assertEqual(
            snapshot_event,
            self.data_source._message_queue[self.data_source._snapshot_messages_queue_key].get_nowait())
        self.assertEqual(1, self.data_source._message_queue[self.data_source._diff_messages_queue_key].qsize())
        self.assertEqual(
            diff_event,
            self.data_source._message_queue[self.data_source._diff_messages_queue_key].get_nowait())
        self.assertEqual(1, self.data_source._message_queue[self.data_source._funding_info_messages_queue_key].qsize())
        self.assertEqual(
            funding_event,
            self.data_source._message_queue[self.data_source._funding_info_messages_queue_key].get_nowait())
        self.assertEqual(1, self.data_source._message_queue[self.data_source._trade_messages_queue_key].qsize())
        self.assertEqual(
            trade_event,
            self.data_source._message_queue[self.data_source._trade_messages_queue_key].get_nowait())
