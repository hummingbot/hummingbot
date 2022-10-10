import asyncio
import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Awaitable, Dict
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
from aioresponses import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.ftx_perpetual import ftx_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_api_order_book_data_source import (
    FtxPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_derivative import FtxPerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class FtxPerpetualAPIOrderBookDataSourceTests(TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "PERP"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = FtxPerpetualDerivative(
            client_config_map,
            ftx_perpetual_api_key="",
            ftx_perpetual_secret_key="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        self.data_source = FtxPerpetualAPIOrderBookDataSource(
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
            bidict({self.ex_trading_pair: self.trading_pair}))

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
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": [
                {
                    "symbol": self.ex_trading_pair,
                    "price": "9487",
                    "size": 336241,
                    "side": "Buy"
                },
                {
                    "symbol": self.ex_trading_pair,
                    "price": "9487.5",
                    "size": 522147,
                    "side": "Sell"
                }
            ],
            "time_now": "1567108756.834357"
        }

    def get_ws_snapshot_msg(self) -> Dict:
        return {
            "topic": f"orderBook_200.100ms.{self.ex_trading_pair}",
            "type": "snapshot",
            "data": [
                {
                    "price": "2999.00",
                    "symbol": self.ex_trading_pair,
                    "id": 29990000,
                    "side": "Buy",
                    "size": 9
                },
                {
                    "price": "3001.00",
                    "symbol": self.ex_trading_pair,
                    "id": 30010000,
                    "side": "Sell",
                    "size": 10
                }
            ],
            "cross_seq": 11518,
            "timestamp_e6": 1555647164875373
        }

    def get_ws_diff_msg(self) -> Dict:
        return {
            "topic": f"orderBook_200.100ms.{self.ex_trading_pair}",
            "type": "delta",
            "data": {
                "delete": [
                    {
                        "price": "3001.00",
                        "symbol": self.ex_trading_pair,
                        "id": 30010000,
                        "side": "Sell"
                    }
                ],
                "update": [
                    {
                        "price": "2999.00",
                        "symbol": self.ex_trading_pair,
                        "id": 29990000,
                        "side": "Buy",
                        "size": 8
                    }
                ],
                "insert": [
                    {
                        "price": "2998.00",
                        "symbol": self.ex_trading_pair,
                        "id": 29980000,
                        "side": "Buy",
                        "size": 8
                    }
                ],
                "transactTimeE6": 0
            },
            "cross_seq": 11519,
            "timestamp_e6": 1555647221331673
        }

    def get_funding_info_msg(self) -> Dict:
        return {
            "topic": f"instrument_info.100ms.{self.ex_trading_pair}",
            "type": "snapshot",
            "data": {
                "id": 1,
                "symbol": self.ex_trading_pair,
                "last_price_e4": 81165000,
                "last_price": "81165000",
                "bid1_price_e4": 400025000,
                "bid1_price": "400025000",
                "ask1_price_e4": 475450000,
                "ask1_price": "475450000",
                "last_tick_direction": "ZeroPlusTick",
                "prev_price_24h_e4": 81585000,
                "prev_price_24h": "81585000",
                "price_24h_pcnt_e6": -5148,
                "high_price_24h_e4": 82900000,
                "high_price_24h": "82900000",
                "low_price_24h_e4": 79655000,
                "low_price_24h": "79655000",
                "prev_price_1h_e4": 81395000,
                "prev_price_1h": "81395000",
                "price_1h_pcnt_e6": -2825,
                "mark_price_e4": 81178500,
                "mark_price": "81178500",
                "index_price_e4": 81172800,
                "index_price": "81172800",
                "open_interest": 154418471,
                "open_value_e8": 1997561103030,
                "total_turnover_e8": 2029370141961401,
                "turnover_24h_e8": 9072939873591,
                "total_volume": 175654418740,
                "volume_24h": 735865248,
                "funding_rate_e6": 100,
                "predicted_funding_rate_e6": 100,
                "cross_seq": 1053192577,
                "created_at": "2018-11-14T16:33:26Z",
                "updated_at": "2020-01-12T18:25:16Z",
                "next_funding_time": "2020-01-13T00:00:00Z",

                "countdown_hour": 6,
                "funding_rate_interval": 8
            },
            "cross_seq": 9267002,
            "timestamp_e6": 1615794861826248
        }

    def get_funding_info_event(self):
        return {
            "topic": f"instrument_info.100ms.{self.ex_trading_pair}",
            "type": "delta",
            "data": {
                "delete": [],
                "update": [
                    {
                        "id": 1,
                        "symbol": self.ex_trading_pair,
                        "prev_price_24h_e4": 81565000,
                        "prev_price_24h": "81565000",
                        "price_24h_pcnt_e6": -4904,
                        "open_value_e8": 2000479681106,
                        "total_turnover_e8": 2029370495672976,
                        "turnover_24h_e8": 9066215468687,
                        "volume_24h": 735316391,
                        "cross_seq": 1053192657,
                        "created_at": "2018-11-14T16:33:26Z",
                        "updated_at": "2020-01-12T18:25:25Z",
                        "index_price": 123,
                        "mark_price": 234,
                        "next_funding_time": "2020-01-12T18:25:25Z",
                        "predicted_funding_rate_e6": 456,
                    }
                ],
                "insert": []
            },
            "cross_seq": 1053192657,
            "timestamp_e6": 1578853525691123
        }

    def get_funding_info_rest_msg(self):
        return {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": [
                {
                    "symbol": self.ex_trading_pair,
                    "bid_price": "7230",
                    "ask_price": "7230.5",
                    "last_price": "7230.00",
                    "last_tick_direction": "ZeroMinusTick",
                    "prev_price_24h": "7163.00",
                    "price_24h_pcnt": "0.009353",
                    "high_price_24h": "7267.50",
                    "low_price_24h": "7067.00",
                    "prev_price_1h": "7209.50",
                    "price_1h_pcnt": "0.002843",
                    "mark_price": "7230.31",
                    "index_price": "7230.14",
                    "open_interest": 117860186,
                    "open_value": "16157.26",
                    "total_turnover": "3412874.21",
                    "turnover_24h": "10864.63",
                    "total_volume": 28291403954,
                    "volume_24h": 78053288,
                    "funding_rate": "0.0001",
                    "predicted_funding_rate": "0.0001",
                    "next_funding_time": "2019-12-28T00:00:00Z",
                    "countdown_hour": 2,
                    "delivery_fee_rate": "0",
                    "predicted_delivery_price": "0.00",
                    "delivery_time": ""
                },
            ],
            "time_now": "1577484619.817968",
        }

    @aioresponses()
    @patch("hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_api_order_book_data_source.FtxPerpetualAPIOrderBookDataSource._time")
    def test_get_new_order_book_successful(self, mock_api, time_mock):
        time_mock.return_value = 1640001112.223334
        url = web_utils.public_rest_url(path_url=CONSTANTS.FTX_ORDER_BOOK_PATH.format(self.ex_trading_pair))
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

        expected_update_id = int(time_mock.return_value * 1e3)

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
    def test_get_new_order_book_raises_exception(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.FTX_ORDER_BOOK_PATH.format(self.ex_trading_pair))
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
            "channel": CONSTANTS.WS_TRADES_CHANNEL,
            "market": self.ex_trading_pair,
            "type": "subscribed",
            "code": 0,
            "msg": "",
            "data": None,
        }
        result_subscribe_order_book = {
            "channel": CONSTANTS.WS_ORDER_BOOK_CHANNEL,
            "market": self.ex_trading_pair,
            "type": "subscribed",
            "code": 0,
            "msg": "",
            "data": None,
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trades))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_order_book))

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(2, len(sent_subscription_messages))
        expected_trade_subscription = {
            "op": "subscribe",
            "channel": CONSTANTS.WS_TRADES_CHANNEL,
            "market": self.ex_trading_pair}
        self.assertEqual(expected_trade_subscription, sent_subscription_messages[0])
        expected_diff_subscription = {
            "op": "subscribe",
            "channel": CONSTANTS.WS_ORDER_BOOK_CHANNEL,
            "market": self.ex_trading_pair}
        self.assertEqual(expected_diff_subscription, sent_subscription_messages[1])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to public order book and trade channels..."
        ))

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = asyncio.CancelledError

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."))

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws, _: AsyncMock):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
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
            "channel": CONSTANTS.WS_TRADES_CHANNEL,
            "market": self.ex_trading_pair,
            "type": "update",
            "data": [
                {
                    "price": 10000,
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
            "channel": CONSTANTS.WS_TRADES_CHANNEL,
            "market": self.ex_trading_pair,
            "type": "update",
            "data": [
                {
                    "id": 4442208960,
                    "price": 42219.9,
                    "size": 0.12060306,
                    "side": "buy",
                    "liquidation": False,
                    "time": datetime.fromtimestamp(1640002223.334445, tz=timezone.utc).isoformat()
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
        self.assertEqual(int(trade_event["data"][0]["id"]), msg.trade_id)
        self.assertEqual(1640002223.334445, msg.timestamp)

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
            "channel": CONSTANTS.WS_ORDER_BOOK_CHANNEL,
            "market": self.ex_trading_pair,
            "type": "update",
            "data": {}
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
            "channel": CONSTANTS.WS_ORDER_BOOK_CHANNEL,
            "market": self.ex_trading_pair,
            "type": "update",
            "data": {
                "time": 1640001112.223334,
                "checksum": 329366394,
                "bids": [
                    [20447.0, 0.1901],
                    [20444.0, 0.3037],
                ],
                "asks": [[20460.0, 0.039]],
                "action": "update"
            }
        }
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.DIFF, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(1640001112.223334, msg.timestamp)
        expected_update_id = int(1640001112.223334 * 1e3)
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(2, len(bids))
        self.assertEqual(20447.0, bids[0].price)
        self.assertEqual(0.1901, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(20460.0, asks[0].price)
        self.assertEqual(0.039, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    def test_listen_for_order_book_snapshots_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    @patch("hummingbot.connector.exchange.ftx.ftx_api_order_book_data_source"
           ".FtxAPIOrderBookDataSource._sleep")
    def test_listen_for_order_book_snapshots_log_exception(self, _):
        incomplete_resp = {
            "channel": CONSTANTS.WS_ORDER_BOOK_CHANNEL,
            "market": self.ex_trading_pair,
            "type": "partial",
            "data": {}
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public order book snapshots from exchange"))

    @aioresponses()
    def test_listen_for_order_book_snapshots_successful(self, mock_api):
        msg_queue: asyncio.Queue = asyncio.Queue()
        endpoint = CONSTANTS.ORDER_BOOK_ENDPOINT
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=endpoint, trading_pair=self.trading_pair, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = self.get_rest_snapshot_msg()

        mock_api.get(regex_url, body=json.dumps(resp))

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(float(resp["time_now"]), msg.timestamp)
        expected_update_id = int(float(resp["time_now"]) * 1e6)
        self.assertEqual(expected_update_id, msg.update_id)

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
        del incomplete_resp["type"]

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
        funding_update = funding_info_event["data"]["update"][0]

        self.assertEqual(self.trading_pair, msg.trading_pair)
        expected_index_price = Decimal(str(funding_update["index_price"]))
        self.assertEqual(expected_index_price, msg.index_price)
        expected_mark_price = Decimal(str(funding_update["mark_price"]))
        self.assertEqual(expected_mark_price, msg.mark_price)
        expected_funding_time = int(
            pd.Timestamp(str(funding_update["next_funding_time"]), tz="UTC").timestamp()
        )
        self.assertEqual(expected_funding_time, msg.next_funding_utc_timestamp)
        expected_rate = Decimal(str(funding_update["predicted_funding_rate_e6"])) * Decimal(1e-6)
        self.assertEqual(expected_rate, msg.rate)

    @aioresponses()
    def test_get_funding_info(self, mock_api):
        endpoint = CONSTANTS.LATEST_SYMBOL_INFORMATION_ENDPOINT
        url = web_utils.get_rest_url_for_endpoint(endpoint, self.trading_pair, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_funding_info_rest_msg()
        mock_api.get(regex_url, body=json.dumps(resp))

        funding_info: FundingInfo = self.async_run_with_timeout(
            self.data_source.get_funding_info(self.trading_pair)
        )
        msg_result = resp["result"][0]

        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(Decimal(str(msg_result["index_price"])), funding_info.index_price)
        self.assertEqual(Decimal(str(msg_result["mark_price"])), funding_info.mark_price)
        expected_utc_timestamp = int(pd.Timestamp(msg_result["next_funding_time"]).timestamp())
        self.assertEqual(expected_utc_timestamp, funding_info.next_funding_utc_timestamp)
        self.assertEqual(Decimal(str(msg_result["predicted_funding_rate"])), funding_info.rate)
