import asyncio
import json
import re
import unittest
from typing import Any, Awaitable, Dict
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses.core import aioresponses
from bidict import bidict

import hummingbot.connector.exchange.coinflex.coinflex_constants as CONSTANTS
import hummingbot.connector.exchange.coinflex.coinflex_web_utils as web_utils
from hummingbot.connector.exchange.coinflex.coinflex_api_order_book_data_source import CoinflexAPIOrderBookDataSource
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage


class CoinflexAPIOrderBookDataSourceUnitTests(unittest.TestCase):
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
        cls.domain = CONSTANTS.DEFAULT_DOMAIN

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.data_source = CoinflexAPIOrderBookDataSource(trading_pairs=[self.trading_pair],
                                                          throttler=self.throttler,
                                                          domain=self.domain)
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

        CoinflexAPIOrderBookDataSource._trading_pair_symbol_map = {
            "coinflex": bidict(
                {f"{self.ex_trading_pair}": self.trading_pair})
        }

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        CoinflexAPIOrderBookDataSource._trading_pair_symbol_map = {}
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

    def _get_regex_url(self,
                       endpoint,
                       return_url=False,
                       endpoint_api_version=None,
                       public=True):
        prv_or_pub = web_utils.public_rest_url if public else web_utils.private_rest_url
        url = prv_or_pub(endpoint, domain=self.domain, endpoint_api_version=endpoint_api_version)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        if return_url:
            return url, regex_url
        return regex_url

    @aioresponses()
    def test_get_last_trade_prices(self, mock_api):
        url, regex_url = self._get_regex_url(CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, return_url=True)

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

        mock_api.get(regex_url, body=json.dumps(mock_response))

        result: Dict[str, float] = self.async_run_with_timeout(
            self.data_source.get_last_traded_prices(trading_pairs=[self.trading_pair],
                                                    throttler=self.throttler)
        )

        self.assertEqual(1, len(result))
        self.assertEqual(100, result[self.trading_pair])

    @aioresponses()
    def test_get_last_trade_prices_exception_raised(self, mock_api):
        url, regex_url = self._get_regex_url(CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, return_url=True)

        mock_api.get(regex_url, body=json.dumps([{"marketCode": "COINALPHA-HBOT"}]))

        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                self.data_source.get_last_traded_prices(trading_pairs=[self.trading_pair],
                                                        throttler=self.throttler)
            )

    @aioresponses()
    def test_fetch_trading_pairs(self, mock_api):
        CoinflexAPIOrderBookDataSource._trading_pair_symbol_map = {}
        url = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.domain)

        mock_response: Dict[str, Any] = {
            "event": "markets",
            "timestamp": "1639598493658",
            "data": [
                {
                    "marketId": "2001000000000",
                    "marketCode": "BTC-USD",
                    "name": "BTC/USD",
                    "referencePair": "BTC/USD",
                    "base": "BTC",
                    "counter": "USD",
                    "type": "MARGIN",
                    "tickSize": "1",
                    "qtyIncrement": "0.001",
                    "marginCurrency": "USD",
                    "contractValCurrency": "BTC",
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
                    "marketId": "34001000000000",
                    "marketCode": "LTC-USD",
                    "name": "LTC/USD",
                    "referencePair": "LTC/USD",
                    "base": "LTC",
                    "counter": "USD",
                    "type": "SPOT",
                    "tickSize": "0.1",
                    "qtyIncrement": "0.01",
                    "marginCurrency": "USD",
                    "contractValCurrency": "LTC",
                    "upperPriceBound": "114.2",
                    "lowerPriceBound": "97.2",
                    "marketPrice": "105.7",
                    "markPrice": None,
                    "listingDate": 1609765200000,
                    "endDate": 0,
                    "marketPriceLastUpdated": 1645547512308,
                    "markPriceLastUpdated": 0
                },
                {
                    "marketId": "4001000000000",
                    "marketCode": "ETH-USD",
                    "name": "ETH/USD",
                    "referencePair": "ETH/USD",
                    "base": "ETH",
                    "counter": "USD",
                    "type": "SPOT",
                    "tickSize": "0.1",
                    "qtyIncrement": "0.01",
                    "marginCurrency": "USD",
                    "contractValCurrency": "ETH",
                    "upperPriceBound": "2704.3",
                    "lowerPriceBound": "2496.1",
                    "marketPrice": "2600.2",
                    "markPrice": None,
                    "listingDate": 0,
                    "endDate": 0,
                    "marketPriceLastUpdated": 1645547505166,
                    "markPriceLastUpdated": 0
                },
            ]
        }

        mock_api.get(url, body=json.dumps(mock_response))

        result: Dict[str] = self.async_run_with_timeout(
            self.data_source.fetch_trading_pairs()
        )

        self.assertEqual(2, len(result))
        self.assertIn("ETH-USD", result)
        self.assertIn("LTC-USD", result)
        self.assertNotIn("BTC-USD", result)

    @aioresponses()
    @patch("hummingbot.connector.exchange.coinflex.coinflex_web_utils.retry_sleep_time")
    def test_fetch_trading_pairs_exception_raised(self, mock_api, retry_sleep_time_mock):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
        CoinflexAPIOrderBookDataSource._trading_pair_symbol_map = {}

        url, regex_url = self._get_regex_url(CONSTANTS.EXCHANGE_INFO_PATH_URL, return_url=True)

        mock_api.get(regex_url, exception=Exception)

        result: Dict[str] = self.async_run_with_timeout(
            self.data_source.fetch_trading_pairs()
        )

        self.assertEqual(0, len(result))

    @aioresponses()
    def test_get_snapshot_successful(self, mock_api):
        url, regex_url = self._get_regex_url(CONSTANTS.SNAPSHOT_PATH_URL.format(self.trading_pair, 1000), return_url=True)

        mock_api.get(regex_url, body=json.dumps(self._snapshot_response()))

        result: Dict[str, Any] = self.async_run_with_timeout(
            self.data_source.get_snapshot(self.trading_pair)
        )

        self.assertEqual(self._snapshot_response()["data"][0], result)

    @aioresponses()
    @patch("hummingbot.connector.exchange.coinflex.coinflex_web_utils.retry_sleep_time")
    def test_get_snapshot_catch_exception(self, mock_api, retry_sleep_time_mock):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
        url, regex_url = self._get_regex_url(CONSTANTS.SNAPSHOT_PATH_URL.format(self.trading_pair, 1000), return_url=True)

        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                self.data_source.get_snapshot(self.trading_pair)
            )

        mock_api.get(regex_url, body=json.dumps({}))
        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                self.data_source.get_snapshot(self.trading_pair)
            )

    @aioresponses()
    def test_get_new_order_book(self, mock_api):
        url, regex_url = self._get_regex_url(CONSTANTS.SNAPSHOT_PATH_URL.format(self.trading_pair, 1000), return_url=True)

        mock_api.get(regex_url, body=json.dumps(self._snapshot_response(update_id=1)))

        result: OrderBook = self.async_run_with_timeout(
            self.data_source.get_new_order_book(self.trading_pair)
        )

        self.assertEqual(1, result.snapshot_uid)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(self._login_message()))

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(1, len(sent_subscription_messages))
        expected_subscription = {
            "op": "subscribe",
            "args": [
                f"trade:{self.ex_trading_pair}",
                f"depth:{self.ex_trading_pair}",
            ],
        }
        self.assertEqual(expected_subscription, sent_subscription_messages[0])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to public order book and trade channels..."
        ))

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

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."))

    def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source._subscribe_channels(mock_ws))
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
        self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_trades_logs_exception(self):
        incomplete_resp = {
            "data": [{
                "m": 1,
                "i": 2,
            }],
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

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
        mock_queue.get.side_effect = [self._login_message(), self._trade_update_event(), asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
        except asyncio.CancelledError:
            pass

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(-1, msg.update_id)

    def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[CONSTANTS.DIFF_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_order_book_diffs_logs_exception(self):
        incomplete_resp = {
            "data": [{
                "m": 1,
                "i": 2,
            }],
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.DIFF_EVENT_TYPE] = mock_queue

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

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_successful(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(self._login_message()))

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(self._order_diff_event()))

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [self._login_message(), self._order_diff_event(), asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.DIFF_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
        except asyncio.CancelledError:
            pass

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(123456789, msg.update_id)

    @aioresponses()
    def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        url, regex_url = self._get_regex_url(CONSTANTS.SNAPSHOT_PATH_URL.format(self.trading_pair, 1000), return_url=True)

        mock_api.get(regex_url, exception=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, asyncio.Queue())
            )

    @aioresponses()
    @patch("hummingbot.connector.exchange.coinflex.coinflex_api_order_book_data_source"
           ".CoinflexAPIOrderBookDataSource._sleep")
    @patch("hummingbot.connector.exchange.coinflex.coinflex_web_utils.retry_sleep_time")
    def test_listen_for_order_book_snapshots_log_exception(self, mock_api, retry_sleep_time_mock, sleep_mock):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
        msg_queue: asyncio.Queue = asyncio.Queue()
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        url, regex_url = self._get_regex_url(CONSTANTS.SNAPSHOT_PATH_URL.format(self.trading_pair, 1000), return_url=True)

        mock_api.get(regex_url, exception=Exception)

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}."))

    @aioresponses()
    @patch("hummingbot.connector.exchange.coinflex.coinflex_api_order_book_data_source"
           ".CoinflexAPIOrderBookDataSource._sleep")
    def test_listen_for_order_book_snapshots_log_outer_exception(self, mock_api, sleep_mock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(Exception("Dummy"))

        url, regex_url = self._get_regex_url(CONSTANTS.SNAPSHOT_PATH_URL.format(self.trading_pair, 1000), return_url=True)

        mock_api.get(regex_url, body=json.dumps(self._snapshot_response()))

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error."))

    @aioresponses()
    def test_listen_for_order_book_snapshots_successful(self, mock_api, ):
        msg_queue: asyncio.Queue = asyncio.Queue()
        url, regex_url = self._get_regex_url(CONSTANTS.SNAPSHOT_PATH_URL.format(self.trading_pair, 1000), return_url=True)

        mock_api.get(regex_url, body=json.dumps(self._snapshot_response()))

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(1027024, msg.update_id)
