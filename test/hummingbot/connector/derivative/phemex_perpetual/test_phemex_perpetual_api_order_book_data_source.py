import asyncio
import json
import re
import unittest
from decimal import Decimal
from typing import Any, Awaitable, Dict, List, Mapping, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses.core import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_constants as CONSTANTS
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.phemex_perpetual import phemex_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_api_order_book_data_source import (
    PhemexPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_web_utils import build_api_factory

# from hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_derivative import PhemexPerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.web_assistant.connections.data_types import RESTMethod


# To-do: cleanup when main exchage class is done
class MockExchange:
    client_config_map = ClientConfigAdapter(ClientConfigMap())
    _time_synchronizer = TimeSynchronizer()
    _throttler = AsyncThrottler(
        rate_limits=CONSTANTS.RATE_LIMITS, limits_share_percentage=client_config_map.rate_limits_share_pct
    )

    def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return {"COINALPHA-HBOT": 123.456}

    _web_assistants_factory = build_api_factory(
        throttler=_throttler,
        time_synchronizer=_time_synchronizer,
    )

    def _set_trading_pair_symbol_map(self, trading_pair_and_symbol_map: Optional[Mapping[str, str]]):
        self._trading_pair_symbol_map = trading_pair_and_symbol_map
        self._trading_pair_symbol_map["COINALPHAHBOT"] = "COINALPHA-HBOT"

    async def exchange_symbol_associated_to_pair(self, trading_pair: str) -> str:
        return "COINALPHAHBOT"

    async def trading_pair_associated_to_exchange_symbol(
        self,
        symbol: str,
    ) -> str:
        return "COINALPHA-HBOT"

    async def _api_get(self, *args, **kwargs):
        kwargs["method"] = RESTMethod.GET
        return await self._api_request(*args, **kwargs)

    async def _api_request(
        self,
        path_url,
        overwrite_url: Optional[str] = None,
        method: RESTMethod = RESTMethod.GET,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        is_auth_required: bool = False,
        return_err: bool = False,
        limit_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:

        last_exception = None
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()

        url = overwrite_url or await self._api_request_url(path_url=path_url, is_auth_required=is_auth_required)

        for _ in range(2):
            try:
                request_result = await rest_assistant.execute_request(
                    url=url,
                    params=params,
                    data=data,
                    method=method,
                    is_auth_required=is_auth_required,
                    return_err=return_err,
                    throttler_limit_id=limit_id if limit_id else path_url,
                )

                return request_result
            except IOError:
                raise

        # Failed even after the last retry
        raise last_exception

    async def _api_request_url(self, path_url: str, is_auth_required: bool = False) -> str:
        return (
            CONSTANTS.TESTNET_BASE_URL + path_url
            if path_url != "/public/time"
            else "https://api.phemex.com/public/time"
        )


class PhemexPerpetualAPIOrderBookDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source loggelates
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"
        cls.domain = "phemex_perpetual_testnet"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.async_tasks: List[asyncio.Task] = []

        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)
        # client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = MockExchange(
            # client_config_map,
            # phemex_perpetual_api_key="",
            # phemex_perpetual_api_secret="",
            # trading_pairs=[self.trading_pair],
            # trading_required=False,
            # domain=self.domain,
        )
        # self.connector.ready = True
        self.data_source = PhemexPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=self.domain,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()
        PhemexPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.domain: bidict({self.ex_trading_pair: self.trading_pair})
        }

        self.connector._set_trading_pair_symbol_map(bidict({f"{self.base_asset}{self.quote_asset}": self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        for task in self.async_tasks:
            task.cancel()
        PhemexPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {}
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

    def _orderbook_update_event(self):
        resp = {
            "book": {"asks": [[86775000, 4621]], "bids": []},
            "depth": 30,
            "sequence": 1191905,
            "symbol": self.ex_trading_pair,
            "type": "incremental",
        }
        return resp

    def _orderbook_trade_event(self):
        resp = {
            "sequence": 1167852,
            "symbol": self.ex_trading_pair,
            "trades": [
                [1573716998128563500, "Buy", 86735000, 56],
                [1573716995033683000, "Buy", 86735000, 52],
                [1573716991485286000, "Buy", 86735000, 51],
                [1573716988636291300, "Buy", 86735000, 12],
            ],
            "type": "snapshot",
        }
        return resp

    def _funding_info_event(self):
        resp = {
            "market24h": {
                "close": 87425000,
                "fundingRate": 10000,
                "high": 92080000,
                "indexPrice": 87450676,
                "low": 87130000,
                "markPrice": 87453092,
                "open": 90710000,
                "openInterest": 7821141,
                "predFundingRate": 7609,
                "symbol": self.ex_trading_pair,
                "timestamp": 1583646442444219017,
                "turnover": 1399362834123,
                "volume": 125287131,
            },
            "timestamp": 1576490244024818000,
        }
        return resp

    @aioresponses()
    def test_get_snapshot_exception_raised(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=400, body=json.dumps(["ERROR"]))

        with self.assertRaises(IOError) as context:
            self.async_run_with_timeout(self.data_source._order_book_snapshot(trading_pair=self.trading_pair))

        self.assertEqual(
            'Error executing request GET https://testnet-api.phemex.com/md/fullbook. HTTP status is 400. Error: ["ERROR"]',
            str(context.exception),
        )

    @aioresponses()
    def test_get_snapshot_successful(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response = {
            "error": None,
            "id": 0,
            "result": {
                "book": {
                    "asks": [[87705000, 1000000], [87710000, 200000]],
                    "bids": [[87700000, 2000000], [87695000, 200000]],
                },
                "depth": 30,
                "sequence": 455476965,
                "timestamp": 1583555482434235628,
                "symbol": self.ex_trading_pair,
                "type": "snapshot",
            },
        }
        mock_api.get(regex_url, status=200, body=json.dumps(mock_response))

        result: Dict[str, Any] = self.async_run_with_timeout(
            self.data_source._request_order_book_snapshot(trading_pair=self.trading_pair)
        )
        self.assertEqual(mock_response, result)

    @aioresponses()
    def test_get_new_order_book(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response = {
            "error": None,
            "id": 0,
            "result": {
                "book": {
                    "asks": [[87705000, 1000000], [87710000, 200000]],
                    "bids": [[87700000, 2000000], [87695000, 200000]],
                },
                "depth": 30,
                "sequence": 455476965,
                "timestamp": 1583555482434235628,
                "symbol": self.ex_trading_pair,
                "type": "snapshot",
            },
        }
        mock_api.get(regex_url, status=200, body=json.dumps(mock_response))
        result = self.async_run_with_timeout(self.data_source.get_new_order_book(trading_pair=self.trading_pair))
        self.assertIsInstance(result, OrderBook)
        self.assertEqual(455476965, result.snapshot_uid)

    @aioresponses()
    def test_get_funding_info_from_exchange_successful(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.MARK_PRICE_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "error": None,
            "id": 0,
            "result": {
                "close": 87425000,
                "fundingRate": 10000,
                "high": 92080000,
                "indexPrice": 87450676,
                "low": 87130000,
                "markPrice": 87453092,
                "open": 90710000,
                "openInterest": 7821141,
                "predFundingRate": 7609,
                "symbol": self.ex_trading_pair,
                "timestamp": 1583646442444219017,
                "turnover": 1399362834123,
                "volume": 125287131,
            },
        }
        mock_api.get(regex_url, body=json.dumps(mock_response))

        result = self.async_run_with_timeout(self.data_source.get_funding_info(self.trading_pair))

        self.assertIsInstance(result, FundingInfo)
        self.assertEqual(result.trading_pair, self.trading_pair)
        self.assertEqual(result.index_price, Decimal(mock_response["result"]["indexPrice"]))
        self.assertEqual(result.mark_price, Decimal(mock_response["result"]["markPrice"]))
        self.assertEqual(result.rate, Decimal(mock_response["result"]["fundingRate"]))

    @aioresponses()
    def test_get_funding_info(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.MARK_PRICE_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "error": None,
            "id": 0,
            "result": {
                "close": 87425000,
                "fundingRate": 10000,
                "high": 92080000,
                "indexPrice": 87450676,
                "low": 87130000,
                "markPrice": 87453092,
                "open": 90710000,
                "openInterest": 7821141,
                "predFundingRate": 7609,
                "symbol": self.ex_trading_pair,
                "timestamp": 1583646442444219017,
                "turnover": 1399362834123,
                "volume": 125287131,
            },
        }
        mock_api.get(regex_url, body=json.dumps(mock_response))

        result = self.async_run_with_timeout(self.data_source.get_funding_info(trading_pair=self.trading_pair))

        self.assertIsInstance(result, FundingInfo)
        self.assertEqual(result.trading_pair, self.trading_pair)
        self.assertEqual(result.index_price, Decimal(mock_response["result"]["indexPrice"]))
        self.assertEqual(result.mark_price, Decimal(mock_response["result"]["markPrice"]))
        self.assertEqual(result.rate, Decimal(mock_response["result"]["fundingRate"]))

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
            self._is_logged(
                "ERROR", "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."
            )
        )

    def test_subscribe_to_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

    def test_subscribe_to_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            self.listening_task = self.ev_loop.create_task(self.data_source._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred subscribing to order book trading and delta streams...")
        )

    def test_channel_originating_message_returns_correct(self):
        event_type = self._orderbook_update_event()
        event_message = self.data_source._channel_originating_message(event_type)
        self.assertEqual(self.data_source._diff_messages_queue_key, event_message)

        event_type = self._funding_info_event()
        event_message = self.data_source._channel_originating_message(event_type)
        self.assertEqual(self.data_source._funding_info_messages_queue_key, event_message)

        event_type = self._orderbook_trade_event()
        event_message = self.data_source._channel_originating_message(event_type)
        self.assertEqual(self.data_source._trade_messages_queue_key, event_message)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_successful(self, mock_ws):
        msg_queue_diffs: asyncio.Queue = asyncio.Queue()
        msg_queue_trades: asyncio.Queue = asyncio.Queue()
        msg_queue_funding: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.close.return_value = None

        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps(self._orderbook_update_event())
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps(self._orderbook_trade_event())
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps(self._funding_info_event())
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
        self.listening_task_diffs = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue_diffs)
        )
        self.listening_task_trades = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue_trades)
        )
        self.listening_task_funding_info = self.ev_loop.create_task(
            self.data_source.listen_for_funding_info(msg_queue_funding)
        )

        result: OrderBookMessage = self.async_run_with_timeout(msg_queue_diffs.get())
        self.assertIsInstance(result, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.DIFF, result.type)
        self.assertTrue(result.has_update_id)
        self.assertEqual(result.update_id, 1191905)
        self.assertEqual(self.trading_pair, result.content["trading_pair"])
        self.assertEqual(0, len(result.content["bids"]))
        self.assertEqual(1, len(result.content["asks"]))

        result: OrderBookMessage = self.async_run_with_timeout(msg_queue_trades.get())
        self.assertIsInstance(result, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.TRADE, result.type)
        self.assertTrue(result.has_trade_id)
        self.assertEqual(result.trade_id, 1573716998128563500)
        self.assertEqual(self.trading_pair, result.content["trading_pair"])

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

    @aioresponses()
    def test_listen_for_order_book_snapshots_cancelled_error_raised(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=asyncio.CancelledError)

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

        self.assertEqual(0, msg_queue.qsize())

    @aioresponses()
    def test_listen_for_order_book_snapshots_logs_exception_error_with_response(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "m": 1,
            "i": 2,
        }
        mock_api.get(regex_url, body=json.dumps(mock_response), callback=self.resume_test_callback)

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred fetching orderbook snapshots. Retrying in 5 seconds...")
        )

    @aioresponses()
    def test_listen_for_order_book_snapshots_successful(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "error": None,
            "id": 0,
            "result": {
                "book": {
                    "asks": [[87705000, 1000000], [87710000, 200000]],
                    "bids": [[87700000, 2000000], [87695000, 200000]],
                },
                "depth": 30,
                "sequence": 455476965,
                "timestamp": 1583555482434235628,
                "symbol": self.ex_trading_pair,
                "type": "snapshot",
            },
        }
        mock_api.get(regex_url, body=json.dumps(mock_response))

        msg_queue: asyncio.Queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        result = self.async_run_with_timeout(msg_queue.get())

        self.assertIsInstance(result, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, result.type)
        self.assertTrue(result.has_update_id)
        self.assertEqual(result.update_id, 455476965)
        self.assertEqual(self.trading_pair, result.content["trading_pair"])

    def test_listen_for_funding_info_cancelled_error_raised(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError
        self.data_source._message_queue[CONSTANTS.FUNDING_INFO_STREAM_METHOD] = mock_queue

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_funding_info(mock_queue))
