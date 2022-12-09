import asyncio
import json
import re
import unittest
from typing import Any, Awaitable, Dict, List
from unittest.mock import AsyncMock, patch

from aioresponses.core import aioresponses
from bidict import bidict

import hummingbot.connector.exchange.bitmex.bitmex_utils as utils
import hummingbot.connector.exchange.bitmex.bitmex_web_utils as web_utils
import hummingbot.connector.exchange.bitmex.constants as CONSTANTS
from hummingbot.connector.exchange.bitmex.bitmex_api_order_book_data_source import BitmexAPIOrderBookDataSource
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class BitmexAPIOrderBookDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "ETH"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}_{cls.quote_asset}"
        cls.domain = "bitmex_testnet"
        utils.TRADING_PAIR_MULTIPLIERS["ETH_USDT"] = utils.TRADING_PAIR_MULTIPLIERS_TUPLE(1000000000, 1000000)
        utils.TRADING_PAIR_INDICES["ETH_USDT"] = utils.TRADING_PAIR_INDEX(954, 0.05)

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.async_tasks: List[asyncio.Task] = []

        self.data_source = BitmexAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            domain=self.domain,
        )
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()
        BitmexAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.domain: bidict({self.ex_trading_pair: self.trading_pair})
        }

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        for task in self.async_tasks:
            task.cancel()
        BitmexAPIOrderBookDataSource._trading_pair_symbol_map = {}
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
            "table": "orderBookL2",
            "action": "insert",
            "data": [{
                "symbol": "ETH_USDT",
                "id": 3333377777,
                "size": 10,
                "side": "Sell"
            }],
        }
        return resp

    def _orderbook_trade_event(self):
        resp = {
            "table": "trade",
            "data": [{
                "symbol": "ETH_USDT",
                "side": "Sell",
                "price": 1000.0,
                "size": 10,
                "timestamp": "2020-02-11T9:30:02.123Z"
            }],
        }
        return resp

    @aioresponses()
    def test_get_last_traded_prices(self, mock_api):
        url = web_utils.rest_url(
            CONSTANTS.TICKER_PRICE_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response: List[Dict[str, Any]] = [{
            "symbol": "ETH_USDT",
            "lastPrice": 100.0
        }]
        mock_api.get(regex_url, body=json.dumps(mock_response))

        result: Dict[str, Any] = self.async_run_with_timeout(
            self.data_source.get_last_traded_prices(trading_pairs=[self.trading_pair], domain=self.domain)
        )
        self.assertTrue(self.trading_pair in result)
        self.assertEqual(100.0, result[self.trading_pair])

    def test_get_throttler_instance(self):
        self.assertTrue(isinstance(self.data_source._get_throttler_instance(), AsyncThrottler))

    @aioresponses()
    def test_init_trading_pair_symbols_failure(self, mock_api):
        BitmexAPIOrderBookDataSource._trading_pair_symbol_map = {}
        url = web_utils.rest_url(
            CONSTANTS.EXCHANGE_INFO_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400, body=json.dumps(["ERROR"]))

        map = self.async_run_with_timeout(self.data_source.trading_pair_symbol_map(domain=self.domain))
        self.assertEqual(0, len(map))

    @aioresponses()
    def test_init_trading_pair_symbols_successful(self, mock_api):
        url = web_utils.rest_url(
            CONSTANTS.EXCHANGE_INFO_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response: List[Dict[str, Any]] = [
            {
                "symbol": "ETH_USDT",
                "rootSymbol": "ETH",
                "quoteCurrency": "USDT"
            },
        ]
        mock_api.get(regex_url, status=200, body=json.dumps(mock_response))
        self.async_run_with_timeout(self.data_source.init_trading_pair_symbols(domain=self.domain))
        self.assertEqual(1, len(self.data_source._trading_pair_symbol_map))

    @aioresponses()
    def test_trading_pair_symbol_map_dictionary_not_initialized(self, mock_api):
        BitmexAPIOrderBookDataSource._trading_pair_symbol_map = {}
        url = web_utils.rest_url(
            CONSTANTS.EXCHANGE_INFO_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response: List[Dict[str, Any]] = [
            {
                "symbol": "ETH_USDT",
                "rootSymbol": "ETH",
                "quoteCurrency": "USDT"
            },
        ]
        mock_api.get(regex_url, status=200, body=json.dumps(mock_response))
        self.async_run_with_timeout(self.data_source.trading_pair_symbol_map(domain=self.domain))
        self.assertEqual(1, len(self.data_source._trading_pair_symbol_map))

    def test_trading_pair_symbol_map_dictionary_initialized(self):
        result = self.async_run_with_timeout(self.data_source.trading_pair_symbol_map(domain=self.domain))
        self.assertEqual(1, len(result))

    def test_convert_from_exchange_trading_pair_not_found(self):
        unknown_pair = "UNKNOWN-PAIR"
        with self.assertRaisesRegex(ValueError, f"There is no symbol mapping for exchange trading pair {unknown_pair}"):
            self.async_run_with_timeout(
                self.data_source.convert_from_exchange_trading_pair(unknown_pair, domain=self.domain))

    def test_convert_from_exchange_trading_pair_successful(self):
        result = self.async_run_with_timeout(
            self.data_source.convert_from_exchange_trading_pair(self.ex_trading_pair, domain=self.domain))
        self.assertEqual(result, self.trading_pair)

    def test_convert_to_exchange_trading_pair_not_found(self):
        unknown_pair = "UNKNOWN-PAIR"
        with self.assertRaisesRegex(ValueError, f"There is no symbol mapping for trading pair {unknown_pair}"):
            self.async_run_with_timeout(
                self.data_source.convert_to_exchange_trading_pair(unknown_pair, domain=self.domain))

    def test_convert_to_exchange_trading_pair_successful(self):
        result = self.async_run_with_timeout(
            self.data_source.convert_to_exchange_trading_pair(self.trading_pair, domain=self.domain))
        self.assertEqual(result, self.ex_trading_pair)

    @aioresponses()
    def test_get_snapshot_exception_raised(self, mock_api):
        url = web_utils.rest_url(
            CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=400, body=json.dumps(["ERROR"]))

        with self.assertRaises(IOError) as context:
            self.async_run_with_timeout(
                self.data_source.get_snapshot(trading_pair=self.trading_pair, domain=self.domain)
            )

        self.assertEqual(str(context.exception), "Error executing request GET /orderBook/L2. HTTP status is 400. Error: [\"ERROR\"]")

    @aioresponses()
    def test_get_snapshot_successful(self, mock_api):
        url = web_utils.rest_url(
            CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response = [{
            'symbol': 'ETH_USDT',
            'side': 'Sell',
            'size': 348,
            'price': 3127.4
        }]
        mock_api.get(regex_url, status=200, body=json.dumps(mock_response))

        result: Dict[str, Any] = self.async_run_with_timeout(
            self.data_source.get_snapshot(trading_pair=self.trading_pair, domain=self.domain)
        )
        self.assertEqual(mock_response, result)

    @aioresponses()
    def test_get_new_order_book(self, mock_api):
        url = web_utils.rest_url(
            CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response = [
            {
                'symbol': 'ETH_USDT',
                'side': 'Sell',
                'size': 348,
                'price': 3127.4,
                'id': 2543
            },
            {
                'symbol': 'ETH_USDT',
                'side': 'Buy',
                'size': 100,
                'price': 3000.1,
                'id': 2555
            }
        ]
        mock_api.get(regex_url, status=200, body=json.dumps(mock_response))
        result = self.async_run_with_timeout(self.data_source.get_new_order_book(trading_pair=self.trading_pair))
        self.assertIsInstance(result, OrderBook)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    def test_listen_for_subscriptions_cancelled_when_connecting(self, _, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)
        self.assertEqual(msg_queue.qsize(), 0)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_successful(self, mock_ws):
        msg_queue_diffs: asyncio.Queue = asyncio.Queue()
        msg_queue_trades: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.close.return_value = None

        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps(self._orderbook_update_event())
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps(self._orderbook_trade_event())
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
        self.listening_task_diffs = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue_diffs)
        )
        self.listening_task_trades = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue_trades)
        )

        result: OrderBookMessage = self.async_run_with_timeout(msg_queue_diffs.get())

        self.assertIsInstance(result, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.DIFF, result.type)
        self.assertTrue(result.has_update_id)
        self.assertEqual(self.trading_pair, result.content["trading_pair"])
        self.assertEqual(0, len(result.content["bids"]))
        self.assertEqual(1, len(result.content["asks"]))

        result: OrderBookMessage = self.async_run_with_timeout(msg_queue_trades.get())

        self.assertIsInstance(result, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.TRADE, result.type)
        self.assertTrue(result.has_trade_id)
        self.assertEqual(self.trading_pair, result.content["trading_pair"])

        self.listening_task.cancel()

    @aioresponses()
    def test_listen_for_order_book_snapshots_cancelled_error_raised(self, mock_api):
        url = web_utils.rest_url(
            CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain
        )
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
        url = web_utils.rest_url(
            CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain
        )
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
        url = web_utils.rest_url(
            CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response = [{
            'symbol': 'ETH_USDT',
            'side': 'Sell',
            'size': 348,
            'price': 3127.4,
            'id': 33337777
        }]
        mock_api.get(regex_url, status=200, body=json.dumps(mock_response))

        msg_queue: asyncio.Queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        result = self.async_run_with_timeout(msg_queue.get())

        self.assertIsInstance(result, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, result.type)
        self.assertTrue(result.has_update_id)
        self.assertEqual(self.trading_pair, result.content["trading_pair"])
