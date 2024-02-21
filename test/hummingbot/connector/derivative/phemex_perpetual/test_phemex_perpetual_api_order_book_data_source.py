import asyncio
import json
import re
import unittest
from decimal import Decimal
from typing import Any, Awaitable, Dict, List
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
from hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_derivative import PhemexPerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


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
        cls.domain = CONSTANTS.TESTNET_DOMAIN

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.async_tasks: List[asyncio.Task] = []

        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = PhemexPerpetualDerivative(
            client_config_map=client_config_map,
            phemex_perpetual_api_key="",
            phemex_perpetual_api_secret="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
            domain=self.domain,
        )
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
            "orderbook_p": {"asks": [[86775000, 4621]], "bids": []},
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
            "trades_p": [
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
            "data": [
                [
                    self.ex_trading_pair,
                    "1533.72",
                    "1594.17",
                    "1510.05",
                    "1547.52",
                    "545942.34",
                    "848127644.5712",
                    "0",
                    "1548.31694379",
                    "1548.44513153",
                    "0.0001",
                    "0.0001",
                ],
                [
                    "BTCUSDT",
                    "20614.5",
                    "21628.4",
                    "19258.6",
                    "20626.3",
                    "8819.819",
                    "182892627.4297",
                    "0",
                    "20641.8167574",
                    "20643.52572781",
                    "0.0001",
                    "0.0001",
                ],
            ],
            "fields": [
                "symbol",
                "openRp",
                "highRp",
                "lowRp",
                "lastRp",
                "volumeRq",
                "turnoverRv",
                "openInterestRv",
                "indexRp",
                "markRp",
                "fundingRateRr",
                "predFundingRateRr",
            ],
            "method": "perp_market24h_pack_p.update",
            "timestamp": 1666862556850547000,
            "type": "snapshot",
        }
        return resp

    @aioresponses()
    def test_get_snapshot_exception_raised(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=400, body=json.dumps(["ERROR"]))

        with self.assertRaises(IOError) as context:
            self.async_run_with_timeout(self.data_source._order_book_snapshot(trading_pair=self.trading_pair))

        self.assertEqual(
            'Error executing request GET https://testnet-api.phemex.com/md/v2/orderbook. HTTP status is 400. Error: ["ERROR"]',
            str(context.exception),
        )

    @aioresponses()
    def test_get_snapshot_successful(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response = {
            "error": None,
            "id": 0,
            "result": {
                "orderbook_p": {
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
        url = web_utils.public_rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response = {
            "error": None,
            "id": 0,
            "result": {
                "orderbook_p": {
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
        url = web_utils.public_rest_url(CONSTANTS.MARK_PRICE_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "error": None,
            "id": 0,
            "result": {
                "closeRp": "20731",
                "fundingRateRr": "0.0001",
                "highRp": "20818.8",
                "indexPriceRp": "20737.09857143",
                "lowRp": "20425.2",
                "markPriceRp": "20737.788944",
                "openInterestRv": "0",
                "openRp": "20709",
                "predFundingRateRr": "0.0001",
                "symbol": self.ex_trading_pair,
                "timestamp": 1667222412794076700,
                "turnoverRv": "139029311.7517",
                "volumeRq": "6747.727",
            },
        }
        mock_api.get(regex_url, body=json.dumps(mock_response))

        result = self.async_run_with_timeout(self.data_source.get_funding_info(self.trading_pair))

        self.assertIsInstance(result, FundingInfo)
        self.assertEqual(result.trading_pair, self.trading_pair)
        self.assertEqual(result.index_price, Decimal(mock_response["result"]["indexPriceRp"]))
        self.assertEqual(result.mark_price, Decimal(mock_response["result"]["markPriceRp"]))
        self.assertEqual(result.rate, Decimal(mock_response["result"]["fundingRateRr"]))

    def test_listen_for_funding_info_successful(self):
        funding_info_event = {
            "data": [
                [
                    self.ex_trading_pair,
                    "0.6597",
                    "0.6887",
                    "0.6149",
                    "0.6429",
                    "8416322",
                    "5502514.8318",
                    "291407",
                    "0.6418",
                    "0.642054889",
                    "0.0001",
                    "0.0001",
                ]
            ],
            "fields": [
                "symbol",
                "openRp",
                "highRp",
                "lowRp",
                "lastRp",
                "volumeRq",
                "turnoverRv",
                "openInterestRv",
                "indexRp",
                "markRp",
                "fundingRateRr",
                "predFundingRateRr",
            ],
            "method": "perp_market24h_pack_p.update",
            "timestamp": 1681507081332818939,
            "type": "snapshot",
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [funding_info_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._funding_info_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_funding_info(msg_queue))

        msg: FundingInfoUpdate = self.async_run_with_timeout(msg_queue.get())
        funding_update = funding_info_event["data"][0]

        self.assertEqual(self.trading_pair, msg.trading_pair)
        expected_index_price = Decimal(str(funding_update[8]))
        self.assertEqual(expected_index_price, msg.index_price)
        expected_mark_price = Decimal(str(funding_update[9]))
        self.assertEqual(expected_mark_price, msg.mark_price)
        expected_rate = Decimal(funding_update[10])
        self.assertEqual(expected_rate, msg.rate)

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
        self.async_tasks.extend([self.listening_task, self.listening_task_diffs, self.listening_task_trades, self.listening_task_funding_info])

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
        url = web_utils.public_rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
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
        url = web_utils.public_rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
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
        url = web_utils.public_rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "error": None,
            "id": 0,
            "result": {
                "orderbook_p": {
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
        self.data_source._message_queue[self.data_source._funding_info_messages_queue_key] = mock_queue

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_funding_info(mock_queue))
