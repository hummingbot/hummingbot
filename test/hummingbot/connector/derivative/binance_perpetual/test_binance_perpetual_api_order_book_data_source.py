import asyncio
import json
import re
import unittest

from decimal import Decimal
from typing import Any, Awaitable, Dict, List
from unittest.mock import AsyncMock, patch

from aioresponses.core import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.binance_perpetual.constants as CONSTANTS

from hummingbot.connector.derivative.binance_perpetual import binance_perpetual_utils as utils
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_api_order_book_data_source import (
    BinancePerpetualAPIOrderBookDataSource,
)
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class BinancePerpetualAPIOrderBookDataSourceUnitTests(unittest.TestCase):
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
        cls.domain = "binance_perpetual_testnet"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.async_tasks: List[asyncio.Task] = []

        self.data_source = BinancePerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            domain=self.domain,
        )
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()
        BinancePerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.domain: bidict({self.ex_trading_pair: self.trading_pair})
        }

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        for task in self.async_tasks:
            task.cancel()
        BinancePerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {}
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
            "stream": f"{self.ex_trading_pair.lower()}@depth",
            "data": {
                "e": "depthUpdate",
                "E": 1631591424198,
                "T": 1631591424189,
                "s": self.ex_trading_pair,
                "U": 752409354963,
                "u": 752409360466,
                "pu": 752409354901,
                "b": [
                    ["43614.31", "0.000"],
                ],
                "a": [
                    ["45277.14", "0.257"],
                ],
            },
        }
        return resp

    def _orderbook_trade_event(self):
        resp = {
            "stream": f"{self.ex_trading_pair.lower()}@aggTrade",
            "data": {
                "e": "aggTrade",
                "E": 1631594403486,
                "a": 817295132,
                "s": self.ex_trading_pair,
                "p": "45266.16",
                "q": "2.206",
                "f": 1437689393,
                "l": 1437689407,
                "T": 1631594403330,
                "m": False,
            },
        }
        return resp

    def _funding_info_event(self):
        resp = {
            "stream": f"{self.ex_trading_pair.lower()}@markPrice",
            "data": {
                "e": "markPriceUpdate",
                "E": 1641288864000,
                "s": self.ex_trading_pair,
                "p": "46353.99600757",
                "P": "46507.47845460",
                "i": "46358.63622407",
                "r": "0.00010000",
                "T": 1641312000000,
            },
        }
        return resp

    @aioresponses()
    def test_get_last_traded_prices(self, mock_api):
        url = utils.rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response: Dict[str, Any] = {
            # Truncated responses
            "lastPrice": "10.0",
        }
        mock_api.get(regex_url, body=json.dumps(mock_response))

        result: Dict[str, Any] = self.async_run_with_timeout(
            self.data_source.get_last_traded_prices(trading_pairs=[self.trading_pair], domain=self.domain)
        )
        self.assertTrue(self.trading_pair in result)
        self.assertEqual(10.0, result[self.trading_pair])

    def test_get_throttler_instance(self):
        self.assertTrue(isinstance(self.data_source._get_throttler_instance(), AsyncThrottler))

    @aioresponses()
    def test_init_trading_pair_symbols_failure(self, mock_api):
        BinancePerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {}
        url = utils.rest_url(path_url=CONSTANTS.EXCHANGE_INFO_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400, body=json.dumps(["ERROR"]))

        map = self.async_run_with_timeout(self.data_source.trading_pair_symbol_map(domain=self.domain))
        self.assertEqual(0, len(map))

    @aioresponses()
    def test_init_trading_pair_symbols_successful(self, mock_api):
        url = utils.rest_url(path_url=CONSTANTS.EXCHANGE_INFO_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response: Dict[str, Any] = {
            # Truncated Responses
            "symbols": [
                {
                    "symbol": self.ex_trading_pair,
                    "pair": self.ex_trading_pair,
                    "baseAsset": self.base_asset,
                    "quoteAsset": self.quote_asset,
                    "status": "TRADING",
                },
                {"symbol": "INACTIVEMARKET", "status": "INACTIVE"},
            ],
        }
        mock_api.get(regex_url, status=200, body=json.dumps(mock_response))
        self.async_run_with_timeout(self.data_source.init_trading_pair_symbols(domain=self.domain))
        self.assertEqual(1, len(self.data_source._trading_pair_symbol_map))

    @aioresponses()
    def test_trading_pair_symbol_map_dictionary_not_initialized(self, mock_api):
        BinancePerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {}
        url = utils.rest_url(path_url=CONSTANTS.EXCHANGE_INFO_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response: Dict[str, Any] = {
            # Truncated Responses
            "symbols": [
                {
                    "symbol": self.ex_trading_pair,
                    "pair": self.ex_trading_pair,
                    "baseAsset": self.base_asset,
                    "quoteAsset": self.quote_asset,
                    "status": "TRADING",
                },
            ]
        }
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
        url = utils.rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=400, body=json.dumps(["ERROR"]))

        with self.assertRaises(IOError) as context:
            self.async_run_with_timeout(
                self.data_source.get_snapshot(trading_pair=self.trading_pair, domain=self.domain)
            )

        self.assertEqual(str(context.exception), f"Error fetching Binance market snapshot for {self.trading_pair}.")

    @aioresponses()
    def test_get_snapshot_successful(self, mock_api):
        url = utils.rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response = {
            "lastUpdateId": 1027024,
            "E": 1589436922972,
            "T": 1589436922959,
            "bids": [["10", "1"]],
            "asks": [["11", "1"]],
        }
        mock_api.get(regex_url, status=200, body=json.dumps(mock_response))

        result: Dict[str, Any] = self.async_run_with_timeout(
            self.data_source.get_snapshot(trading_pair=self.trading_pair, domain=self.domain)
        )
        self.assertEqual(mock_response, result)

    @aioresponses()
    def test_get_new_order_book(self, mock_api):
        url = utils.rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response = {
            "lastUpdateId": 1027024,
            "E": 1589436922972,
            "T": 1589436922959,
            "bids": [["10", "1"]],
            "asks": [["11", "1"]],
        }
        mock_api.get(regex_url, status=200, body=json.dumps(mock_response))
        result = self.async_run_with_timeout(self.data_source.get_new_order_book(trading_pair=self.trading_pair))
        self.assertIsInstance(result, OrderBook)
        self.assertEqual(1027024, result.snapshot_uid)

    @aioresponses()
    def test_get_funding_info_from_exchange_error_response(self, mock_api):
        url = utils.rest_url(CONSTANTS.MARK_PRICE_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400)

        result = self.async_run_with_timeout(self.data_source._get_funding_info_from_exchange(self.trading_pair))
        self.assertIsNone(result)
        self._is_logged("ERROR", f"Unable to fetch FundingInfo for {self.trading_pair}. Error: None")

    @aioresponses()
    def test_get_funding_info_from_exchange_successful(self, mock_api):
        url = utils.rest_url(CONSTANTS.MARK_PRICE_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "symbol": self.ex_trading_pair,
            "markPrice": "46382.32704603",
            "indexPrice": "46385.80064948",
            "estimatedSettlePrice": "46510.13598963",
            "lastFundingRate": "0.00010000",
            "interestRate": "0.00010000",
            "nextFundingTime": 1641312000000,
            "time": 1641288825000,
        }
        mock_api.get(regex_url, body=json.dumps(mock_response))

        result = self.async_run_with_timeout(self.data_source._get_funding_info_from_exchange(self.trading_pair))

        self.assertIsInstance(result, FundingInfo)
        self.assertEqual(result.trading_pair, self.trading_pair)
        self.assertEqual(result.index_price, Decimal(mock_response["indexPrice"]))
        self.assertEqual(result.mark_price, Decimal(mock_response["markPrice"]))
        self.assertEqual(result.next_funding_utc_timestamp, mock_response["nextFundingTime"])
        self.assertEqual(result.rate, Decimal(mock_response["lastFundingRate"]))

    @aioresponses()
    def test_get_funding_info(self, mock_api):
        self.assertNotIn(self.trading_pair, self.data_source._funding_info)

        url = utils.rest_url(CONSTANTS.MARK_PRICE_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "symbol": self.ex_trading_pair,
            "markPrice": "46382.32704603",
            "indexPrice": "46385.80064948",
            "estimatedSettlePrice": "46510.13598963",
            "lastFundingRate": "0.00010000",
            "interestRate": "0.00010000",
            "nextFundingTime": 1641312000000,
            "time": 1641288825000,
        }
        mock_api.get(regex_url, body=json.dumps(mock_response))

        result = self.async_run_with_timeout(self.data_source.get_funding_info(trading_pair=self.trading_pair))

        self.assertIsInstance(result, FundingInfo)
        self.assertEqual(result.trading_pair, self.trading_pair)
        self.assertEqual(result.index_price, Decimal(mock_response["indexPrice"]))
        self.assertEqual(result.mark_price, Decimal(mock_response["markPrice"]))
        self.assertEqual(result.next_funding_utc_timestamp, mock_response["nextFundingTime"])
        self.assertEqual(result.rate, Decimal(mock_response["lastFundingRate"]))

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
    def test_listen_for_subscriptions_logs_exception(self, mock_ws, *_):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.close.return_value = None
        incomplete_resp = {
            "m": 1,
            "i": 2,
        }
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, json.dumps(incomplete_resp))
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps(self._orderbook_update_event())
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.exceptions.TimeoutError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error with Websocket connection. Retrying after 30 seconds...")
        )

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
        self.listening_task_funding_info = self.ev_loop.create_task(self.data_source.listen_for_funding_info())

        result: OrderBookMessage = self.async_run_with_timeout(msg_queue_diffs.get())
        self.assertIsInstance(result, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.DIFF, result.type)
        self.assertTrue(result.has_update_id)
        self.assertEqual(result.update_id, 752409360466)
        self.assertEqual(self.trading_pair, result.content["trading_pair"])
        self.assertEqual(1, len(result.content["bids"]))
        self.assertEqual(1, len(result.content["asks"]))

        result: OrderBookMessage = self.async_run_with_timeout(msg_queue_trades.get())
        self.assertIsInstance(result, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.TRADE, result.type)
        self.assertTrue(result.has_trade_id)
        self.assertEqual(result.trade_id, 817295132)
        self.assertEqual(self.trading_pair, result.content["trading_pair"])

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertIn(self.trading_pair, self.data_source.funding_info)

        funding_info: FundingInfo = self.data_source.funding_info[self.trading_pair]
        self.assertTrue(self.data_source.is_funding_info_initialized)
        self.assertEqual(funding_info.trading_pair, self.trading_pair)
        self.assertEqual(funding_info.index_price, Decimal(self._funding_info_event()["data"]["i"]))
        self.assertEqual(funding_info.mark_price, Decimal(self._funding_info_event()["data"]["p"]))
        self.assertEqual(funding_info.next_funding_utc_timestamp, int(self._funding_info_event()["data"]["T"]))
        self.assertEqual(funding_info.rate, Decimal(self._funding_info_event()["data"]["r"]))

    @aioresponses()
    def test_listen_for_order_book_snapshots_cancelled_error_raised(self, mock_api):
        url = utils.rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
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
        url = utils.rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
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
        url = utils.rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "lastUpdateId": 1027024,
            "E": 1589436922972,
            "T": 1589436922959,
            "bids": [["10", "1"]],
            "asks": [["11", "1"]],
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
        self.assertEqual(result.update_id, 1027024)
        self.assertEqual(self.trading_pair, result.content["trading_pair"])

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_funding_info_invalid_trading_pair(self, mock_ws):

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.close.return_value = None

        mock_response = {
            "stream": "unknown_pair@markPrice",
            "data": {
                "e": "markPriceUpdate",
                "E": 1641288864000,
                "s": "unknown_pair",
                "p": "46353.99600757",
                "P": "46507.47845460",
                "i": "46358.63622407",
                "r": "0.00010000",
                "T": 1641312000000,
            },
        }

        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, json.dumps(mock_response))

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.listening_task_funding_info = self.ev_loop.create_task(self.data_source.listen_for_funding_info())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertNotIn(self.trading_pair, self.data_source.funding_info)

    def test_listen_for_funding_info_cancelled_error_raised(self):

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError
        self.data_source._message_queue[CONSTANTS.FUNDING_INFO_STREAM_ID] = mock_queue

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_funding_info())

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    def test_listen_for_funding_info_logs_exception(self, mock_sleep):

        mock_sleep.side_effect = lambda _: (self.ev_loop.run_until_complete(asyncio.sleep(0.5)))

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = lambda: (self._raise_exception_and_unlock_test_with_event(Exception("TEST ERROR")))
        self.data_source._message_queue[CONSTANTS.FUNDING_INFO_STREAM_ID] = mock_queue

        self.listening_task_funding_info = self.ev_loop.create_task(self.data_source.listen_for_funding_info())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self._is_logged(
            "ERROR", "Unexpected error occured updating funding information. Retrying in 5 seconds... Error: TEST ERROR"
        )
