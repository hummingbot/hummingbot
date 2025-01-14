import asyncio
import json
import re
import unittest
from decimal import Decimal
from typing import Any, Awaitable, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses.core import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_constants as CONSTANTS
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.bitmart_perpetual import bitmart_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_api_order_book_data_source import (
    BitmartPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_derivative import BitmartPerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class BitmartPerpetualAPIOrderBookDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"
        cls.domain = "bitmart_perpetual"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.async_tasks: List[asyncio.Task] = []

        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = BitmartPerpetualDerivative(
            client_config_map,
            bitmart_perpetual_api_key="",
            bitmart_perpetual_api_secret="",
            bitmart_perpetual_memo="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
            domain=self.domain,
        )
        self.data_source = BitmartPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=self.domain,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()
        BitmartPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.domain: bidict({self.ex_trading_pair: self.trading_pair})
        }

        self.connector._set_trading_pair_symbol_map(
            bidict({f"{self.base_asset}{self.quote_asset}": self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        for task in self.async_tasks:
            task.cancel()
        BitmartPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def resume_test_callback(self, *_, **__):
        self.resume_test_event.set()
        return None

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _raise_exception(self, exception_class):
        raise exception_class

    def _raise_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _order_book_snapshot_rest_data(self):
        resp = {
            "code": 1000,
            "message": "Ok",
            "trace": "b9bff62d-9ac8-4815-8808-8f745673c096",
            "data": {
                "asks": [["23935.4", "65", "65"]],
                "bids": [["23935.4", "65", "65"]],
                "timestamp": 1660285421287,
                "symbol": self.ex_trading_pair
            }
        }
        return resp

    def _funding_info_rest_data(self):
        resp = {
            "code": 1000,
            "message": "Ok",
            "data": {
                "timestamp": 1662518172178,
                "symbol": self.ex_trading_pair,
                "rate_value": "0.000164",
                "expected_rate": "0.000164",
                "funding_time": 1709971200000,
                "funding_upper_limit": "0.0375",
                "funding_lower_limit": "-0.0375"
            },
            "trace": "13f7fda9-9543-4e11-a0ba-cbe117989988"
        }
        return resp

    def _exchange_info_rest_data(self):
        resp = {
            "code": 1000,
            "message": "Ok",
            "trace": "9b92a999-9463-4c96-91a4-93ad1cad0d72",
            "data": {
                "symbols": [
                    {
                        "symbol": self.ex_trading_pair,
                        "product_type": 1,
                        "open_timestamp": 1594080000123,
                        "expire_timestamp": 0,
                        "settle_timestamp": 0,
                        "base_currency": "BTC",
                        "quote_currency": "USDT",
                        "last_price": "23920",
                        "volume_24h": "18969368",
                        "turnover_24h": "458933659.7858",
                        "index_price": "23945.25191635",
                        "index_name": self.ex_trading_pair,
                        "contract_size": "0.001",
                        "min_leverage": "1",
                        "max_leverage": "100",
                        "price_precision": "0.1",
                        "vol_precision": "1",
                        "max_volume": "500000",
                        "market_max_volume": "500000",
                        "min_volume": "1",
                        "funding_rate": "0.0001",
                        "expected_funding_rate": "0.00011",
                        "open_interest": "4134180870",
                        "open_interest_value": "94100888927.0433258",
                        "high_24h": "23900",
                        "low_24h": "23100",
                        "change_24h": "0.004",
                        "funding_interval_hours": 8
                    },
                ]
            }
        }
        return resp

    def _orderbook_update_event(self, update_type: str = "update"):
        resp = {
            "data": {
                "symbol": self.ex_trading_pair,
                "asks": [
                    {
                        "price": "70391.6",
                        "vol": "3550"
                    }
                ],
                "bids": [
                    {
                        "price": "70391.2",
                        "vol": "1335"
                    }
                ],
                "ms_t": 1730400086184,
                "version": 980361,
                "type": update_type
            },
            "group": "futures/depthIncrease50:BTCUSDT@200ms"
        }
        return resp

    def _trade_event(self):
        resp = {
            "group": f"futures/trade:{self.ex_trading_pair}",
            "data": [
                {
                    "trade_id": 1409495322,
                    "symbol": self.ex_trading_pair,
                    "deal_price": "117387.58",
                    "way": 1,
                    "deal_vol": "1445",
                    "created_at": "2023-02-24T07:54:11.124940968Z"
                }
            ]
        }

        return resp

    def _funding_info_event(self):
        resp = {
            "data": {
                "symbol": self.ex_trading_pair,
                "fundingRate": "0.000098800809",
                "fundingTime": 1732525864000,
                "nextFundingRate": "0.0000947",
                "nextFundingTime": 1732550400000,
                "funding_upper_limit": "0.0375",
                "funding_lower_limit": "-0.0375",
                "ts": 1732525864601
            },
            "group": "futures/fundingRate:BTCUSDT"
        }
        return resp

    def _ticker_event(self):
        resp = {
            "group": "futures/ticker",
            "data": {
                "symbol": self.ex_trading_pair,
                "volume_24": "117387.58",
                "fair_price": "146.24",
                "last_price": "146.24",
                "range": "147.17",
                "ask_price": "147.11",
                "ask_vol": "1",
                "bid_price": "142.11",
                "bid_vol": "1"
            }
        }
        return resp

    @aioresponses()
    def test_get_snapshot_exception_raised(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=400, body=json.dumps(["ERROR"]))

        with self.assertRaises(IOError) as context:
            self.async_run_with_timeout(
                self.data_source._order_book_snapshot(
                    trading_pair=self.trading_pair)
            )

        self.assertIn("HTTP status is 400. Error: [\"ERROR\"]",
                      str(context.exception))

    @aioresponses()
    def test_get_snapshot_successful(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response = self._order_book_snapshot_rest_data()
        mock_api.get(regex_url, status=200, body=json.dumps(mock_response))

        result: Dict[str, Any] = self.async_run_with_timeout(
            self.data_source._request_order_book_snapshot(
                trading_pair=self.trading_pair)
        )
        self.assertEqual(mock_response, result)

    @aioresponses()
    def test_get_new_order_book(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=200, body=json.dumps(self._order_book_snapshot_rest_data()))
        result = self.async_run_with_timeout(self.data_source.get_new_order_book(trading_pair=self.trading_pair))
        self.assertIsInstance(result, OrderBook)
        self.assertEqual(1, result.snapshot_uid)

    @aioresponses()
    def test_get_funding_info_from_exchange_successful(self, mock_api):
        funding_url = web_utils.public_rest_url(CONSTANTS.FUNDING_INFO_URL, self.domain)
        funding_regex_url = re.compile(f"^{funding_url}".replace(".", r"\.").replace("?", r"\?"))
        funding_info_resp = self._funding_info_rest_data()
        mock_api.get(funding_regex_url, body=json.dumps(funding_info_resp))

        exchange_info_url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_URL, self.domain)
        exchange_info_regex_url = re.compile(f"^{exchange_info_url}".replace(".", r"\.").replace("?", r"\?"))
        exchange_info_resp = self._exchange_info_rest_data()
        mock_api.get(exchange_info_regex_url, body=json.dumps(exchange_info_resp))

        funding_info: FundingInfo = self.async_run_with_timeout(
            self.data_source.get_funding_info(self.trading_pair)
        )

        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(Decimal(exchange_info_resp["data"]["symbols"][0]["index_price"]), funding_info.index_price)
        self.assertEqual(Decimal(exchange_info_resp["data"]["symbols"][0]["last_price"]), funding_info.mark_price)
        self.assertEqual(int(float(funding_info_resp["data"]["funding_time"]) * 1e-3), funding_info.next_funding_utc_timestamp)
        self.assertEqual(Decimal(funding_info_resp["data"]["expected_rate"]), funding_info.rate)

    # @aioresponses()
    # def test_get_funding_info(self, mock_api):
    #     url = web_utils.public_rest_url(CONSTANTS.MARK_PRICE_URL, domain=self.domain)
    #     regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
    #
    #     mock_response = {
    #         "symbol": self.ex_trading_pair,
    #         "markPrice": "46382.32704603",
    #         "indexPrice": "46385.80064948",
    #         "estimatedSettlePrice": "46510.13598963",
    #         "lastFundingRate": "0.00010000",
    #         "interestRate": "0.00010000",
    #         "nextFundingTime": 1641312000000,
    #         "time": 1641288825000,
    #     }
    #     mock_api.get(regex_url, body=json.dumps(mock_response))
    #
    #     result = self.async_run_with_timeout(self.data_source.get_funding_info(trading_pair=self.trading_pair))
    #
    #     self.assertIsInstance(result, FundingInfo)
    #     self.assertEqual(result.trading_pair, self.trading_pair)
    #     self.assertEqual(result.index_price, Decimal(mock_response["indexPrice"]))
    #     self.assertEqual(result.mark_price, Decimal(mock_response["markPrice"]))
    #     self.assertEqual(result.next_funding_utc_timestamp, int(mock_response["nextFundingTime"] * 1e-3))
    #     self.assertEqual(result.rate, Decimal(mock_response["lastFundingRate"]))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    def test_listen_for_subscriptions_cancelled_when_connecting(self, _, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)
        self.assertEqual(msg_queue.qsize(), 0)

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock):
        sleep_mock.side_effect = asyncio.CancelledError
        mock_ws.side_effect = Exception("TEST ERROR.")

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)

        self.assertTrue(
            self._is_logged("ERROR",
                            "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds...")
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
            self._is_logged("ERROR", "Unexpected error occurred subscribing to order book trading and delta streams...")
        )

    def test_channel_originating_message_returns_correct(self):
        event_type = self._orderbook_update_event(update_type="snapshot")
        event_message = self.data_source._channel_originating_message(event_type)
        self.assertEqual(self.data_source._snapshot_messages_queue_key, event_message)

        event_type = self._orderbook_update_event(update_type="update")
        event_message = self.data_source._channel_originating_message(event_type)
        self.assertEqual(self.data_source._diff_messages_queue_key, event_message)

        event_type = self._funding_info_event()
        event_message = self.data_source._channel_originating_message(event_type)
        self.assertEqual(self.data_source._funding_info_messages_queue_key, event_message)

        event_type = self._trade_event()
        event_message = self.data_source._channel_originating_message(event_type)
        self.assertEqual(self.data_source._trade_messages_queue_key, event_message)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_successful(self, mock_ws):
        msg_queue_diffs: asyncio.Queue = asyncio.Queue()
        msg_queue_snapshots: asyncio.Queue = asyncio.Queue()
        msg_queue_trades: asyncio.Queue = asyncio.Queue()
        msg_queue_funding: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.close.return_value = None

        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps(self._orderbook_update_event(update_type="snapshot"))
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps(self._orderbook_update_event(update_type="update"))
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps(self._trade_event())
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps(self._funding_info_event())
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps(self._exchange_info_rest_data())
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
        self.listening_task_diffs = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue_diffs)
        )
        self.listening_task_snapshots = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue_snapshots)
        )
        self.listening_task_trades = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue_trades)
        )
        self.listening_task_funding_info = self.ev_loop.create_task(
            self.data_source.listen_for_funding_info(msg_queue_funding)
        )
        self.listening_task_exchange_info = self.ev_loop.create_task(
            self.data_source.listen_for_exchange_info(self.ev_loop)
        )

        result: OrderBookMessage = self.async_run_with_timeout(msg_queue_diffs.get())
        self.assertIsInstance(result, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.DIFF, result.type)
        self.assertTrue(result.has_update_id)
        self.assertEqual(result.update_id, 980361)
        self.assertEqual(self.trading_pair, result.content["trading_pair"])
        self.assertEqual(1, len(result.content["bids"]))
        self.assertEqual(1, len(result.content["asks"]))

        result: OrderBookMessage = self.async_run_with_timeout(msg_queue_snapshots.get())
        self.assertIsInstance(result, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, result.type)
        self.assertTrue(result.has_update_id)
        self.assertEqual(result.update_id, 980361)
        self.assertEqual(self.trading_pair, result.content["trading_pair"])
        self.assertEqual(1, len(result.content["bids"]))
        self.assertEqual(1, len(result.content["asks"]))

        result: OrderBookMessage = self.async_run_with_timeout(msg_queue_trades.get())
        self.assertIsInstance(result, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.TRADE, result.type)
        self.assertTrue(result.has_trade_id)
        self.assertEqual(result.trade_id, 1409495322)
        self.assertEqual(self.trading_pair, result.content["trading_pair"])

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

    # @aioresponses()
    # def test_listen_for_order_book_snapshots_logs_exception_error_with_response(self, mock_api):
    #     url = web_utils.public_rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
    #     regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
    #
    #     mock_api.get(regex_url, body=json.dumps(self._order_book_snapshot_rest_data()), callback=self.resume_test_callback)
    #
    #     msg_queue: asyncio.Queue = asyncio.Queue()
    #
    #     self.listening_task = self.ev_loop.create_task(
    #         self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
    #     )
    #
    #     self.async_run_with_timeout(self.resume_test_event.wait())
    #
    #     self.assertTrue(
    #         self._is_logged("ERROR", "Unexpected error when processing public order book snapshots from exchange")
    #     )

    # @aioresponses()
    # def test_listen_for_order_book_snapshots_successful(self, mock_api):
    #     url = web_utils.public_rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
    #     regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
    #
    #     mock_api.get(regex_url, body=json.dumps(self._orderbook_update_event(update_type="snapshot")))
    #
    #     msg_queue: asyncio.Queue = asyncio.Queue()
    #     self.listening_task = self.ev_loop.create_task(
    #         self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
    #     )
    #
    #     result = self.async_run_with_timeout(msg_queue.get())
    #
    #     self.assertIsInstance(result, OrderBookMessage)
    #     self.assertEqual(OrderBookMessageType.SNAPSHOT, result.type)
    #     self.assertTrue(result.has_update_id)
    #     self.assertEqual(result.update_id, 980361)
    #     self.assertEqual(self.trading_pair, result.content["trading_pair"])
    #
    # def test_listen_for_funding_info_cancelled_error_raised(self):
    #     mock_queue = AsyncMock()
    #     mock_queue.get.side_effect = asyncio.CancelledError
    #     self.data_source._message_queue[CONSTANTS.FUNDING_INFO_STREAM_ID] = mock_queue
    #
    #     with self.assertRaises(asyncio.CancelledError):
    #         self.async_run_with_timeout(self.data_source.listen_for_funding_info(mock_queue))
