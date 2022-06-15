import asyncio
import json
import re
import unittest
from datetime import datetime
from decimal import Decimal
from typing import Any, Awaitable, Dict, List
from unittest.mock import AsyncMock, patch

from aioresponses.core import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.coinflex_perpetual.constants as CONSTANTS
from hummingbot.connector.derivative.coinflex_perpetual import coinflex_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_api_order_book_data_source import (
    CoinflexPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class CoinflexPerpetualAPIOrderBookDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.domain = "coinflex_perpetual_testnet"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.async_tasks: List[asyncio.Task] = []

        self.data_source = CoinflexPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            domain=self.domain,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()
        CoinflexPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.domain: bidict({self.ex_trading_pair: self.trading_pair})
        }

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        for task in self.async_tasks:
            task.cancel()
        CoinflexPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {}
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

    def _successfully_subscribed_event(self):
        resp = {
            "result": None,
            "id": 1
        }
        return resp

    def _login_message(self):
        resp = {
            "tag": "1234567890",
            "event": "login",
            "success": True,
            "timestamp": "1234567890"
        }
        return resp

    def _trade_update_event(self):
        resp = {
            "table": "trade",
            "data": [{
                "timestamp": 123456789,
                "marketCode": self.ex_trading_pair,
                "tradeId": 12345,
                "side": "BUY",
                "price": "0.001",
                "quantity": "100",
            }]
        }
        return resp

    def _order_diff_event(self):
        resp = {
            "table": "depth",
            "data": [{
                "timestamp": 123456789,
                "instrumentId": self.ex_trading_pair,
                "seqNum": 157,
                "bids": [["0.0024", "10"]],
                "asks": [["0.0026", "100"]]
            }]
        }
        return resp

    def _snapshot_response(self,
                           update_id=1027024):
        resp = {
            "event": "depthL1000",
            "timestamp": update_id,
            "data": [{
                "bids": [
                    [
                        "4.00000000",
                        "431.00000000"
                    ]
                ],
                "asks": [
                    [
                        "4.00000200",
                        "12.00000000"
                    ]
                ],
                "marketCode": self.ex_trading_pair,
                "timestamp": update_id,
            }]
        }
        return resp

    def _ticker_response(self):
        mock_response = [{
            "last": "100.0",
            "open24h": "38719",
            "high24h": "38840",
            "low24h": "36377",
            "volume24h": "3622970.9407847790",
            "currencyVolume24h": "96.986",
            "openInterest": "0",
            "marketCode": "COINALPHA-HBOT",
            "timestamp": "1645546950025",
            "lastQty": "0.086",
            "markPrice": "37645",
            "lastMarkPrice": "37628",
        }]

        return mock_response

    def _funding_info_response(self):
        mock_response = [{
            "instrumentId": self.ex_trading_pair,
            "fundingRate": "0.00010000",
            "timestamp": "2022-04-11 21:00:03",
        }]

        return mock_response

    def _get_regex_url(self,
                       endpoint,
                       return_url=False,
                       endpoint_api_version=None,
                       public=True):
        prv_or_pub = web_utils.public_rest_url if public else web_utils.private_rest_url
        url = prv_or_pub(endpoint, domain=self.domain, endpoint_api_version=endpoint_api_version)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?").replace("{}", r".*"))
        if return_url:
            return url, regex_url
        return regex_url

    @aioresponses()
    def test_get_last_traded_prices(self, mock_api):

        regex_url = self._get_regex_url(CONSTANTS.TICKER_PRICE_CHANGE_URL)
        mock_response = [{
            "last": "10.0",
            "open24h": "38719",
            "high24h": "38840",
            "low24h": "36377",
            "volume24h": "3622970.9407847790",
            "currencyVolume24h": "96.986",
            "openInterest": "0",
            "marketCode": "COINALPHA-HBOT",
            "timestamp": "1645546950025",
            "lastQty": "0.086",
            "markPrice": "37645",
            "lastMarkPrice": "37628",
        }]
        mock_api.get(regex_url, body=json.dumps(mock_response))

        result: Dict[str, Any] = self.async_run_with_timeout(
            self.data_source.get_last_traded_prices(trading_pairs=[self.trading_pair], domain=self.domain)
        )
        self.assertTrue(self.trading_pair in result)
        self.assertEqual(10.0, result[self.trading_pair])

    @aioresponses()
    @patch("hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_web_utils.retry_sleep_time")
    def test_init_trading_pair_symbols_failure(self, mock_api, retry_sleep_time_mock):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0

        CoinflexPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {}
        regex_url = self._get_regex_url(CONSTANTS.EXCHANGE_INFO_URL)

        mock_api.get(regex_url, status=400, body=json.dumps(["ERROR"]))

        map = self.async_run_with_timeout(self.data_source.trading_pair_symbol_map(
            domain=self.domain))
        self.assertEqual(0, len(map))

    @aioresponses()
    def test_init_trading_pair_symbols_successful(self, mock_api):
        regex_url = self._get_regex_url(CONSTANTS.EXCHANGE_INFO_URL)

        mock_response: Dict[str, Any] = {
            "event": "markets",
            "timestamp": "1639598493658",
            "data": [
                {
                    "marketId": "2001000000000",
                    "marketCode": self.ex_trading_pair,
                    "name": f"{self.base_asset}/{self.quote_asset} Perp",
                    "referencePair": f"{self.base_asset}/{self.quote_asset}",
                    "base": self.base_asset,
                    "counter": self.quote_asset,
                    "type": "FUTURE",
                    "tickSize": "1",
                    "qtyIncrement": "0.001",
                    "marginCurrency": self.quote_asset,
                    "contractValCurrency": self.base_asset,
                    "upperPriceBound": "39203",
                    "lowerPriceBound": "36187",
                    "marketPrice": "37695",
                    "markPrice": None,
                    "listingDate": 1593316800000,
                    "endDate": 0,
                    "marketPriceLastUpdated": 1645547473153,
                    "markPriceLastUpdated": 0
                },
                {
                    "marketId": "2001000000000",
                    "marketCode": self.ex_trading_pair,
                    "name": f"{self.base_asset}/{self.quote_asset}",
                    "referencePair": f"{self.base_asset}/{self.quote_asset}",
                    "base": self.base_asset,
                    "counter": self.quote_asset,
                    "type": "SPOT",
                    "tickSize": "1",
                    "qtyIncrement": "0.001",
                    "marginCurrency": self.quote_asset,
                    "contractValCurrency": self.base_asset,
                    "upperPriceBound": "39203",
                    "lowerPriceBound": "36187",
                    "marketPrice": "37695",
                    "markPrice": None,
                    "listingDate": 1593316800000,
                    "endDate": 0,
                    "marketPriceLastUpdated": 1645547473153,
                    "markPriceLastUpdated": 0
                },
            ]
        }
        mock_api.get(regex_url, status=200, body=json.dumps(mock_response))
        self.async_run_with_timeout(self.data_source.init_trading_pair_symbols(
            domain=self.domain))
        self.assertEqual(1, len(self.data_source._trading_pair_symbol_map[self.domain]))

    @aioresponses()
    def test_trading_pair_symbol_map_dictionary_not_initialized(self, mock_api):
        CoinflexPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {}
        regex_url = self._get_regex_url(CONSTANTS.EXCHANGE_INFO_URL)
        mock_response: Dict[str, Any] = {
            "event": "markets",
            "timestamp": "1639598493658",
            "data": [
                {
                    "marketId": "2001000000000",
                    "marketCode": self.ex_trading_pair,
                    "name": f"{self.base_asset}/{self.quote_asset} Perp",
                    "referencePair": f"{self.base_asset}/{self.quote_asset}",
                    "base": self.base_asset,
                    "counter": self.quote_asset,
                    "type": "FUTURE",
                    "tickSize": "1",
                    "qtyIncrement": "0.001",
                    "marginCurrency": self.quote_asset,
                    "contractValCurrency": self.base_asset,
                    "upperPriceBound": "39203",
                    "lowerPriceBound": "36187",
                    "marketPrice": "37695",
                    "markPrice": None,
                    "listingDate": 1593316800000,
                    "endDate": 0,
                    "marketPriceLastUpdated": 1645547473153,
                    "markPriceLastUpdated": 0
                }
            ]
        }
        mock_api.get(regex_url, status=200, body=json.dumps(mock_response))
        self.async_run_with_timeout(self.data_source.trading_pair_symbol_map(
            domain=self.domain))
        self.assertEqual(1, len(self.data_source._trading_pair_symbol_map[self.domain]))

    def test_trading_pair_symbol_map_dictionary_initialized(self):
        result = self.async_run_with_timeout(self.data_source.trading_pair_symbol_map(
            domain=self.domain))
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
    @patch("hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_web_utils.retry_sleep_time")
    def test_get_snapshot_exception_raised(self, mock_api, retry_sleep_time_mock):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0

        regex_url = self._get_regex_url(CONSTANTS.SNAPSHOT_REST_URL)
        for x in range(CONSTANTS.API_MAX_RETRIES):
            mock_api.get(regex_url, status=200, body=json.dumps(["ERROR"]))

        with self.assertRaises(IOError) as context:
            self.async_run_with_timeout(
                self.data_source.get_snapshot(
                    trading_pair=self.trading_pair)
            )

        self.assertEqual(f"Error fetching market snapshot for {self.trading_pair}. Response: ['ERROR'].",
                         str(context.exception))

    @aioresponses()
    def test_get_snapshot_successful(self, mock_api):
        regex_url = self._get_regex_url(CONSTANTS.SNAPSHOT_REST_URL)
        mock_response = self._snapshot_response()
        mock_api.get(regex_url, status=200, body=json.dumps(mock_response))

        result: Dict[str, Any] = self.async_run_with_timeout(
            self.data_source.get_snapshot(
                trading_pair=self.trading_pair)
        )
        self.assertEqual(mock_response['data'][0], result)

    @aioresponses()
    def test_get_new_order_book(self, mock_api):
        regex_url = self._get_regex_url(CONSTANTS.SNAPSHOT_REST_URL)
        mock_response = self._snapshot_response(update_id=1027024)
        mock_api.get(regex_url, status=200, body=json.dumps(mock_response))
        result = self.async_run_with_timeout(self.data_source.get_new_order_book(trading_pair=self.trading_pair))
        self.assertIsInstance(result, OrderBook)
        self.assertEqual(1027024, result.snapshot_uid)

    @aioresponses()
    @patch("hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_web_utils.retry_sleep_time")
    def test_get_funding_info_from_exchange_error_response(self, mock_api, retry_sleep_time_mock):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0

        regex_url = self._get_regex_url(CONSTANTS.TICKER_PRICE_CHANGE_URL)
        mock_response = self._ticker_response()
        mock_api.get(regex_url, status=200, body=json.dumps(mock_response))

        regex_url = self._get_regex_url(CONSTANTS.MARK_PRICE_URL)
        mock_api.get(regex_url, status=400)

        result = self.async_run_with_timeout(self.data_source._get_funding_info_from_exchange(self.trading_pair))
        self.assertIsNone(result)
        self._is_logged("ERROR", f"Unable to fetch FundingInfo for {self.trading_pair}. Error: None")

    @aioresponses()
    def test_get_funding_info_from_exchange_successful(self, mock_api):
        regex_url = self._get_regex_url(CONSTANTS.TICKER_PRICE_CHANGE_URL)
        mock_ticker_resp = self._ticker_response()
        mock_api.get(regex_url, status=200, body=json.dumps(mock_ticker_resp))

        regex_url = self._get_regex_url(CONSTANTS.MARK_PRICE_URL)
        mock_response = self._funding_info_response()
        mock_api.get(regex_url, body=json.dumps(mock_response))

        result = self.async_run_with_timeout(self.data_source._get_funding_info_from_exchange(self.trading_pair))

        next_fund_ts = datetime.strptime(mock_response[0]["timestamp"], "%Y-%m-%d %H:%M:%S").timestamp() + CONSTANTS.ONE_HOUR

        self.assertIsInstance(result, FundingInfo)
        self.assertEqual(result.trading_pair, self.trading_pair)
        self.assertEqual(result.index_price, Decimal(mock_ticker_resp[0]["last"]))
        self.assertEqual(result.mark_price, Decimal(mock_ticker_resp[0]["markPrice"]))
        self.assertEqual(result.next_funding_utc_timestamp, next_fund_ts)
        self.assertEqual(result.rate, Decimal(mock_response[0]["fundingRate"]))

    @aioresponses()
    def test_get_funding_info(self, mock_api):
        self.assertNotIn(self.trading_pair, self.data_source._funding_info)

        regex_url = self._get_regex_url(CONSTANTS.TICKER_PRICE_CHANGE_URL)
        mock_ticker_resp = self._ticker_response()
        mock_api.get(regex_url, status=200, body=json.dumps(mock_ticker_resp))

        regex_url = self._get_regex_url(CONSTANTS.MARK_PRICE_URL)
        mock_response = self._funding_info_response()
        mock_api.get(regex_url, body=json.dumps(mock_response))

        result = self.async_run_with_timeout(self.data_source.get_funding_info(trading_pair=self.trading_pair))

        next_fund_ts = datetime.strptime(mock_response[0]["timestamp"], "%Y-%m-%d %H:%M:%S").timestamp() + CONSTANTS.ONE_HOUR

        self.assertIsInstance(result, FundingInfo)
        self.assertEqual(result.trading_pair, self.trading_pair)
        self.assertEqual(result.index_price, Decimal(mock_ticker_resp[0]["last"]))
        self.assertEqual(result.mark_price, Decimal(mock_ticker_resp[0]["markPrice"]))
        self.assertEqual(result.next_funding_utc_timestamp, next_fund_ts)
        self.assertEqual(result.rate, Decimal(mock_response[0]["fundingRate"]))

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
        incomplete_resp = 1
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, json.dumps(incomplete_resp))
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps(self._order_diff_event())
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.exceptions.TimeoutError:
            pass

        print(self.log_records)

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
            mock_ws.return_value, json.dumps(self._order_diff_event())
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, json.dumps(self._trade_update_event())
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
        self.assertEqual(result.update_id, 123456789)
        self.assertEqual(self.trading_pair, result.content["trading_pair"])
        self.assertEqual(1, len(result.content["bids"]))
        self.assertEqual(1, len(result.content["asks"]))

        result: OrderBookMessage = self.async_run_with_timeout(msg_queue_trades.get())
        self.assertIsInstance(result, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.TRADE, result.type)
        self.assertTrue(result.has_trade_id)
        self.assertEqual(result.trade_id, 12345)
        self.assertEqual(self.trading_pair, result.content["trading_pair"])

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

    @aioresponses()
    def test_listen_for_order_book_snapshots_cancelled_error_raised(self, mock_api):
        regex_url = self._get_regex_url(CONSTANTS.SNAPSHOT_REST_URL)
        mock_api.get(regex_url, exception=asyncio.CancelledError)

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

        self.assertEqual(0, msg_queue.qsize())

    @aioresponses()
    @patch("hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_web_utils.retry_sleep_time")
    def test_listen_for_order_book_snapshots_logs_exception_error_with_response(self, mock_api, retry_sleep_time_mock):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0

        regex_url = self._get_regex_url(CONSTANTS.SNAPSHOT_REST_URL)

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
            self._is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}.")
        )

    @aioresponses()
    def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        regex_url = self._get_regex_url(CONSTANTS.SNAPSHOT_REST_URL.format(self.trading_pair, 1000))

        mock_api.get(regex_url, exception=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, asyncio.Queue())
            )

    @aioresponses()
    @patch("hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_api_order_book_data_source"
           ".CoinflexPerpetualAPIOrderBookDataSource._sleep")
    def test_listen_for_order_book_snapshots_log_outer_exception(self, mock_api, sleep_mock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        sleep_mock.side_effect = lambda _: self._raise_exception_and_unlock_test_with_event(Exception("Dummy"))

        regex_url = self._get_regex_url(CONSTANTS.SNAPSHOT_REST_URL.format(self.trading_pair, 1000))

        mock_api.get(regex_url, body=json.dumps(self._snapshot_response()))

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred fetching orderbook snapshots. Retrying in 5 seconds..."))

    @aioresponses()
    def test_listen_for_order_book_snapshots_successful(self, mock_api):
        regex_url = self._get_regex_url(CONSTANTS.SNAPSHOT_REST_URL.format(self.trading_pair, 1000))
        mock_api.get(regex_url, body=json.dumps(self._snapshot_response()))

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
