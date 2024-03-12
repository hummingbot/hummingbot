import asyncio
import json
import unittest
from decimal import Decimal
from test.hummingbot.connector.derivative.vega_perpetual import mock_orderbook, mock_requests
from typing import Awaitable, List
from unittest.mock import AsyncMock, patch

from aioresponses.core import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.vega_perpetual.vega_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.vega_perpetual.vega_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.vega_perpetual.vega_perpetual_api_order_book_data_source import (
    VegaPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.vega_perpetual.vega_perpetual_derivative import VegaPerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class VegaPerpetualAPIOrderBookDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}-{cls.quote_asset}"
        cls.domain = "vega_perpetual_testnet"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.async_tasks: List[asyncio.Task] = []

        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = VegaPerpetualDerivative(
            client_config_map,
            vega_perpetual_public_key="",
            vega_perpetual_seed_phrase="",
            trading_pairs=[self.ex_trading_pair],
            trading_required=False,
            domain=self.domain,
        )
        self.data_source = VegaPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.ex_trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=self.domain,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()
        VegaPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.domain: bidict({self.ex_trading_pair: self.ex_trading_pair})
        }

        self.connector._set_trading_pair_symbol_map(
            bidict({f"{self.base_asset}{self.quote_asset}": self.ex_trading_pair}))

    @property
    def all_symbols_url(self):
        url = web_utils.rest_url(path_url=CONSTANTS.EXCHANGE_INFO_URL, domain=self.domain)
        return url

    @property
    def symbols_url(self) -> str:
        url = web_utils.rest_url(path_url=CONSTANTS.SYMBOLS_URL, domain=self.domain)
        return url

    def funding_info_url(self, market_id: str) -> str:
        url = web_utils.rest_url(f"{CONSTANTS.MARK_PRICE_URL}/{market_id}/{CONSTANTS.RECENT_SUFFIX}", domain=self.domain)
        return url

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        for task in self.async_tasks:
            task.cancel()
        VegaPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {}
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

    def _setup_markets(self, mock_api):
        mock_api.get(self.symbols_url,
                     body=json.dumps(mock_requests._get_exchange_symbols_rest_mock()),
                     headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        mock_api.get(self.all_symbols_url,
                     body=json.dumps(mock_requests._get_exchange_info_rest_mock()),
                     headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"})

        task = self.ev_loop.create_task(self.connector._populate_exchange_info())
        self.async_run_with_timeout(task)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    def test_listen_for_subscriptions_cancelled_when_connecting(self, _, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.side_effect = asyncio.CancelledError

        self.data_source._connector._best_connection_endpoint = "wss://test.com"

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)
        self.assertEqual(msg_queue.qsize(), 0)

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock):
        sleep_mock.side_effect = asyncio.CancelledError
        mock_ws.side_effect = Exception("TEST ERROR.")

        self.data_source._connector._best_connection_endpoint = "wss://test.com"

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_ws_ob_diff(self, mock_api, mock_ws):

        self._setup_markets(mock_api)
        msg_queue_diffs: asyncio.Queue = asyncio.Queue()

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.close.return_value = None

        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps(mock_orderbook._get_order_book_diff_mock())
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
        self.listening_task_diffs = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue_diffs)
        )

        result: OrderBookMessage = self.async_run_with_timeout(msg_queue_diffs.get())
        self.assertIsInstance(result, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.DIFF, result.type)
        self.assertTrue(result.has_update_id)
        self.assertEqual(result.update_id, 1697590646276860086)
        self.assertEqual(self.ex_trading_pair, result.content["trading_pair"])
        self.assertEqual(0, len(result.content["bids"]))
        self.assertEqual(4, len(result.content["asks"]))

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_ws_ob_snapshot(self, mock_api, mock_ws):

        self._setup_markets(mock_api)
        msg_queue: asyncio.Queue = asyncio.Queue()

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.close.return_value = None

        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps(mock_orderbook._get_order_book_snapshot_mock())
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
        self.listening_task_diffs = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        result: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())
        self.assertIsInstance(result, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, result.type)
        self.assertTrue(result.has_update_id)
        self.assertEqual(result.update_id, 1697590437480112072)
        self.assertEqual(self.ex_trading_pair, result.content["trading_pair"])
        self.assertEqual(26, len(result.content["bids"]))
        self.assertEqual(25, len(result.content["asks"]))

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_ws_trades(self, mock_api, mock_ws):

        self._setup_markets(mock_api)
        msg_queue: asyncio.Queue = asyncio.Queue()

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.close.return_value = None

        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps(mock_orderbook._get_trades_mock())
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
        self.listening_task_diffs = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue)
        )

        result: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())
        self.assertIsInstance(result, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.TRADE, result.type)
        self.assertTrue(result.has_trade_id)
        self.assertEqual(result.trade_id, '374eefc4c872845df70d5302fe3953b35004371ca42364d962e804ff063be817')  # noqa: mock
        self.assertEqual(self.ex_trading_pair, result.content["trading_pair"])

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_ws_funding_info(self, mock_api, mock_ws):

        self._setup_markets(mock_api)
        msg_queue: asyncio.Queue = asyncio.Queue()

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.close.return_value = None

        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps(mock_orderbook._get_market_data_mock())
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
        self.listening_task_diffs = self.ev_loop.create_task(
            self.data_source.listen_for_funding_info(msg_queue)
        )

        result: FundingInfoUpdate = self.async_run_with_timeout(msg_queue.get())
        self.assertIsInstance(result, FundingInfoUpdate)
        self.assertTrue(result.index_price)
        self.assertEqual(result.mark_price, Decimal('29.04342'))
        self.assertEqual(result.rate, Decimal("0.0005338755797842"))

    @aioresponses()
    def test_get_funding_info(self, mock_api):
        self._setup_markets(mock_api)

        # https://api.n07.testnet.vega.rocks/api/v2/market/data/COINALPHAHBOT/latest
        market_id = "COINALPHAHBOT"
        path_url = f"{CONSTANTS.MARK_PRICE_URL}/{market_id}/{CONSTANTS.RECENT_SUFFIX}"
        mock_api.get(
            web_utils.rest_url(path_url=path_url, domain=self.domain),
            body=json.dumps(mock_orderbook._get_latest_market_data_rest_mock()),
            headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"},
        )

        task = self.ev_loop.create_task(self.data_source.get_funding_info(self.ex_trading_pair))
        info = self.async_run_with_timeout(task)

        self.assertEqual(info.trading_pair, self.ex_trading_pair)
        self.assertIsInstance(info, FundingInfo)
        self.assertEqual(info.index_price, Decimal("28432.23000"))

    @aioresponses()
    def test_get_ob_snapshot(self, mock_api):
        self._setup_markets(mock_api)

        # https://api.n07.testnet.vega.rocks/api/v2/market/data/COINALPHAHBOT/latest
        market_id = "COINALPHAHBOT"

        path_url = f"{CONSTANTS.SNAPSHOT_REST_URL}/{market_id}/{CONSTANTS.RECENT_SUFFIX}"
        mock_api.get(
            web_utils.rest_url(path_url=path_url, domain=self.domain),
            body=json.dumps(mock_orderbook._get_order_book_snapshot_rest_mock()),
            headers={"Ratelimit-Limit": "100", "Ratelimit-Reset": "1"},
        )

        task = self.ev_loop.create_task(self.data_source._order_book_snapshot(self.ex_trading_pair))
        result: OrderBookMessage = self.async_run_with_timeout(task)
        self.assertIsInstance(result, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, result.type)
        self.assertTrue(result.has_update_id)
        self.assertEqual(result.update_id, 1697591562856384102)
        self.assertEqual(self.ex_trading_pair, result.content["trading_pair"])
        self.assertEqual(20, len(result.content["bids"]))
        self.assertEqual(21, len(result.content["asks"]))
