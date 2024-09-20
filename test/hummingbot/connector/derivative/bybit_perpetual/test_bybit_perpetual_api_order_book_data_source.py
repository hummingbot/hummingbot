import asyncio
import json
import re
from decimal import Decimal
from typing import Awaitable, Dict
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.bybit_perpetual import bybit_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_api_order_book_data_source import (
    BybitPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_derivative import BybitPerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class BybitPerpetualAPIOrderBookDataSourceTests(TestCase):
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
        cls.domain = "bybit_perpetual_testnet"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = BybitPerpetualDerivative(
            client_config_map,
            bybit_perpetual_api_key="",
            bybit_perpetual_secret_key="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
            domain=self.domain,
        )
        self.data_source = BybitPerpetualAPIOrderBookDataSource(
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
            bidict({f"{self.base_asset}{self.quote_asset}": self.trading_pair}))

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
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "s": self.ex_trading_pair,
                "a": [
                    [
                        "65557.7",
                        "16.606555"
                    ]
                ],
                "b": [
                    [
                        "65485.47",
                        "47.081829"
                    ]
                ],
                "ts": 1716863719031,
                "u": 230704,
                "seq": 1432604333,
                "cts": 1716863718905
            },
            "retExtInfo": {},
            "time": 1716863719382
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
            "topic": f"orderbook.50.{self.ex_trading_pair}",
            "type": "delta",
            "ts": 1672304484978,
            "data": {
                "s": f"{self.ex_trading_pair}",
                "b": [
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
                ],
                "u": 18521288,
                "seq": 7961638724
            },
            "cts": 1672304484976
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
            "topic": f"tickers.{self.ex_trading_pair}",
            "type": "delta",
            "data": {
                "symbol": f"{self.ex_trading_pair}",
                "tickDirection": "PlusTick",
                "price24hPcnt": "0.017103",
                "lastPrice": "17216.00",
                "prevPrice24h": "16926.50",
                "highPrice24h": "17281.50",
                "lowPrice24h": "16915.00",
                "prevPrice1h": "17238.00",
                "markPrice": "17217.33",
                "indexPrice": "17227.36",
                "openInterest": "68744.761",
                "openInterestValue": "1183601235.91",
                "turnover24h": "1570383121.943499",
                "volume24h": "91705.276",
                "nextFundingTime": "1673280000000",
                "fundingRate": "-0.000212",
                "bid1Price": "17215.50",
                "bid1Size": "84.489",
                "ask1Price": "17216.00",
                "ask1Size": "83.020"
            },
            "cs": 24987956059,
            "ts": 1673272861686
        }

    def get_general_info_rest_msg(self):
        return {
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "category": "inverse",
                "list": [
                    {
                        "symbol": self.ex_trading_pair,
                        "lastPrice": "16597.00",
                        "indexPrice": "16598.54",
                        "markPrice": "16596.00",
                        "prevPrice24h": "16464.50",
                        "price24hPcnt": "0.008047",
                        "highPrice24h": "30912.50",
                        "lowPrice24h": "15700.00",
                        "prevPrice1h": "16595.50",
                        "openInterest": "373504107",
                        "openInterestValue": "22505.67",
                        "turnover24h": "2352.94950046",
                        "volume24h": "49337318",
                        "fundingRate": "-0.001034",
                        "nextFundingTime": "1672387200000",
                        "predictedDeliveryPrice": "",
                        "basisRate": "",
                        "deliveryFeeRate": "",
                        "deliveryTime": "0",
                        "ask1Size": "1",
                        "bid1Price": "16596.00",
                        "ask1Price": "16597.50",
                        "bid1Size": "1",
                        "basis": ""
                    }
                ]
            },
            "retExtInfo": {},
            "time": 1672376496682
        }

    def get_predicted_funding_info(self):
        return {
            "ret_code": 0,
            "ret_msg": "ok",
            "ext_code": "",
            "result": {
                "predicted_funding_rate": 0.0001,
                "predicted_funding_fee": 0
            },
            "ext_info": None,
            "time_now": "1577447415.583259",
            "rate_limit_status": 118,
            "rate_limit_reset_ms": 1577447415590,
            "rate_limit": 120
        }

    @aioresponses()
    def test_get_new_order_book_successful(self, mock_api):
        endpoint = CONSTANTS.ORDER_BOOK_ENDPOINT
        url = web_utils.get_rest_url_for_endpoint(endpoint, self.trading_pair, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_rest_snapshot_msg()
        snapshot_data = resp["result"]
        mock_api.get(regex_url, body=json.dumps(resp))

        order_book = self.async_run_with_timeout(
            self.data_source.get_new_order_book(self.trading_pair)
        )

        expected_update_id = float(snapshot_data["ts"] * 1e6)

        self.assertEqual(expected_update_id, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(1, len(bids))
        self.assertEqual(65485.47, bids[0].price)
        self.assertEqual(47.081829, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(65557.7, asks[0].price)
        self.assertEqual(16.606555, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @aioresponses()
    def test_get_new_order_book_raises_exception(self, mock_api):
        endpoint = CONSTANTS.ORDER_BOOK_ENDPOINT
        url = web_utils.get_rest_url_for_endpoint(endpoint, self.trading_pair, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                self.data_source.get_new_order_book(self.trading_pair)
            )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_trades_diffs_and_funding_info(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_diffs = self.get_ws_snapshot_msg()
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

        self.assertEqual(3, len(sent_subscription_messages))
        expected_trade_subscription = {
            "op": "subscribe",
            "args": [f"publicTrade.{self.ex_trading_pair}"],
        }
        self.assertEqual(expected_trade_subscription, sent_subscription_messages[0])
        expected_diff_subscription = {
            "op": "subscribe",
            "args": [f"orderbook.200.{self.ex_trading_pair}"],
        }
        self.assertEqual(expected_diff_subscription, sent_subscription_messages[1])
        expected_funding_info_subscription = {
            "op": "subscribe",
            "args": [f"tickers.{self.ex_trading_pair}"],
        }
        self.assertEqual(expected_funding_info_subscription, sent_subscription_messages[2])

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
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.async_run_with_timeout(self.resume_test_event.wait())
        trading_type = "linear" if "USDT" in self.trading_pair else "inverse"
        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams"
                f" wss://stream-testnet.bybit.com/v5/public/{trading_type}. Retrying in 5 seconds...",
            )
        )

    def test_subscribe_to_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source._subscribe_to_channels(mock_ws, [self.trading_pair])
            )
            self.async_run_with_timeout(self.listening_task)

    def test_subscribe_to_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            self.listening_task = self.ev_loop.create_task(
                self.data_source._subscribe_to_channels(mock_ws, [self.trading_pair])
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
        incomplete_resp = {
            "topic": f"trade.{self.ex_trading_pair}",
            "data": [
                {
                    "timestamp": "2020-01-12T16:59:59.000Z",
                    "symbol": self.ex_trading_pair,
                    "side": "Sell",
                    "size": 328,
                    "price": 8098,
                    "tick_direction": "MinusTick",
                    "trade_id": "00c706e1-ba52-5bb0-98d0-bf694bdc69f7",
                    "cross_seq": 1052816407
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
            "topic": f"publicTrade.{self.ex_trading_pair}",
            "type": "snapshot",
            "ts": 1672304486868,
            "data": [
                {
                    "T": 1672304486865,
                    "s": self.ex_trading_pair,
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
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.TRADE, msg.type)
        self.assertEqual(trade_event["data"][0]["i"], msg.trade_id)
        self.assertEqual(trade_event["data"][0]["T"] * 1e-3, msg.timestamp)

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
        del incomplete_resp["ts"]

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
        self.assertEqual(diff_event["ts"] * 1e-3, msg.timestamp)
        expected_update_id = diff_event["ts"] * 1000
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(2, len(bids))
        self.assertEqual(16493.5, bids[0].price)
        self.assertEqual(0.006, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(2, len(asks))
        self.assertEqual(16611.0, asks[0].price)
        self.assertEqual(0.029, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @aioresponses()
    def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        endpoint = CONSTANTS.ORDER_BOOK_ENDPOINT
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=endpoint, trading_pair=self.trading_pair, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

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

        endpoint = CONSTANTS.ORDER_BOOK_ENDPOINT
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=endpoint, trading_pair=self.trading_pair, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

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
        self.assertEqual(float(resp["result"]["ts"]), msg.timestamp)
        expected_update_id = float(resp["result"]["ts"]) * 1e6
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(1, len(bids))
        self.assertEqual(65485.47, bids[0].price)
        self.assertEqual(47.081829, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(65557.7, asks[0].price)
        self.assertEqual(16.606555, asks[0].amount)
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
        funding_update = funding_info_event["data"]

        self.assertEqual(self.trading_pair, msg.trading_pair)
        expected_index_price = Decimal(str(funding_update["indexPrice"]))
        self.assertEqual(expected_index_price, msg.index_price)
        expected_mark_price = Decimal(str(funding_update["markPrice"]))
        self.assertEqual(expected_mark_price, msg.mark_price)
        expected_funding_time = int(funding_update["nextFundingTime"]) // 1e3
        self.assertEqual(expected_funding_time, msg.next_funding_utc_timestamp)

    @aioresponses()
    def test_get_funding_info(self, mock_api):
        endpoint = CONSTANTS.LATEST_SYMBOL_INFORMATION_ENDPOINT
        url = web_utils.get_rest_url_for_endpoint(endpoint, self.trading_pair, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        general_resp = self.get_general_info_rest_msg()
        mock_api.get(regex_url, body=json.dumps(general_resp))

        funding_info: FundingInfo = self.async_run_with_timeout(
            self.data_source.get_funding_info(self.trading_pair)
        )
        general_info_result = general_resp["result"]["list"][0]

        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(Decimal(str(general_info_result["indexPrice"])), funding_info.index_price)
        self.assertEqual(Decimal(str(general_info_result["markPrice"])), funding_info.mark_price)
        expected_utc_timestamp = int(general_info_result["nextFundingTime"]) // 1e3
        self.assertEqual(expected_utc_timestamp, funding_info.next_funding_utc_timestamp)
