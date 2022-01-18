import aiohttp
import asyncio
import gzip
import json
import re
import ujson
import unittest

import hummingbot.connector.exchange.huobi.huobi_constants as CONSTANTS

from aioresponses import aioresponses
from typing import Any, Awaitable, Dict, List
from unittest.mock import AsyncMock, patch

from hummingbot.connector.exchange.huobi.huobi_api_order_book_data_source import HuobiAPIOrderBookDataSource
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class HuobiAPIOrderBookDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}".lower()

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.async_tasks: List[asyncio.Task] = []

        self.data_source = HuobiAPIOrderBookDataSource(trading_pairs=[self.trading_pair])

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        for task in self.async_tasks:
            task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _compress(self, message: Dict[str, Any]) -> bytes:
        return gzip.compress(json.dumps(message).encode())

    @aioresponses()
    def test_last_traded_prices(self, mock_api):
        url = CONSTANTS.REST_URL + CONSTANTS.TICKER_URL
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response: Dict[str, Any] = {
            "data": [
                {
                    "symbol": self.ex_trading_pair,
                    "open": 1.1,
                    "high": 2.0,
                    "low": 0.8,
                    "close": 1.5,
                    "amount": 100,
                    "vol": 100,
                    "count": 100,
                    "bid": 1.3,
                    "bidSize": 10,
                    "ask": 1.4,
                    "askSize": 10,
                },
            ],
            "status": "ok",
            "ts": 1637229769083,
        }

        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        result = self.async_run_with_timeout(self.data_source.get_last_traded_prices(trading_pairs=[self.trading_pair]))

        self.assertEqual(1, len(result))
        self.assertIn(self.trading_pair, result)
        self.assertEqual(1.5, result[self.trading_pair])

    @aioresponses()
    def test_fetch_trading_pairs_failed(self, mock_api):
        url = CONSTANTS.REST_URL + CONSTANTS.API_VERSION + CONSTANTS.SYMBOLS_URL
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400, body=ujson.dumps({}))

        result = self.async_run_with_timeout(self.data_source.fetch_trading_pairs())

        self.assertEqual(0, len(result))

    @aioresponses()
    def test_fetch_trading_pairs_successful(self, mock_api):
        url = CONSTANTS.REST_URL + CONSTANTS.API_VERSION + CONSTANTS.SYMBOLS_URL
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "status": "ok",
            "data": [
                {
                    "base-currency": self.base_asset.lower(),
                    "quote-currency": self.quote_asset.lower(),
                    "price-precision": 4,
                    "amount-precision": 2,
                    "symbol-partition": "innovation",
                    "symbol": self.ex_trading_pair,
                    "state": "online",
                    "value-precision": 8,
                    "min-order-amt": 1,
                    "max-order-amt": 10000000,
                    "min-order-value": 0.1,
                    "limit-order-min-order-amt": 1,
                    "limit-order-max-order-amt": 10000000,
                    "limit-order-max-buy-amt": 10000000,
                    "limit-order-max-sell-amt": 10000000,
                    "sell-market-min-order-amt": 1,
                    "sell-market-max-order-amt": 1000000,
                    "buy-market-max-order-value": 17000,
                    "api-trading": "enabled",
                    "tags": "abnormalmarket",
                }
            ],
        }

        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        result = self.async_run_with_timeout(self.data_source.fetch_trading_pairs())

        self.assertEqual(1, len(result))

    @aioresponses()
    def test_get_snapshot_raises_error(self, mock_api):
        url = CONSTANTS.REST_URL + CONSTANTS.DEPTH_URL
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400, body=ujson.dumps({}))

        expected_error_msg = f"Error fetching Huobi market snapshot for {self.trading_pair}. HTTP status is 400"

        with self.assertRaisesRegex(IOError, expected_error_msg):
            self.async_run_with_timeout(self.data_source.get_snapshot(self.trading_pair))

    @aioresponses()
    def test_get_snapshot_successful(self, mock_api):
        url = CONSTANTS.REST_URL + CONSTANTS.DEPTH_URL
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "ch": f"market.{self.ex_trading_pair}.depth.step0",
            "status": "ok",
            "ts": 1637255180894,
            "tick": {
                "bids": [
                    [57069.57, 0.05],
                ],
                "asks": [
                    [57057.73, 0.007019],
                ],
                "version": 141982962388,
                "ts": 1637255180700,
            },
        }

        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        result = self.async_run_with_timeout(self.data_source.get_snapshot(self.trading_pair))

        self.assertEqual(mock_response["ch"], result["ch"])
        self.assertEqual(mock_response["status"], result["status"])
        self.assertEqual(1, len(result["tick"]["bids"]))
        self.assertEqual(1, len(result["tick"]["asks"]))

    @aioresponses()
    def test_get_new_order_book(self, mock_api):
        url = CONSTANTS.REST_URL + CONSTANTS.DEPTH_URL
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "ch": f"market.{self.ex_trading_pair}.depth.step0",
            "status": "ok",
            "ts": 1637255180894,
            "tick": {
                "bids": [
                    [57069.57, 0.05],
                ],
                "asks": [
                    [57057.73, 0.007019],
                ],
                "version": 141982962388,
                "ts": 1637255180700,
            },
        }

        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        result = self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))

        self.assertIsInstance(result, OrderBook)
        self.assertEqual(1637255180700, result.snapshot_uid)
        self.assertEqual(1, len(list(result.bid_entries())))
        self.assertEqual(1, len(list(result.ask_entries())))
        self.assertEqual(57069.57, list(result.bid_entries())[0].price)
        self.assertEqual(0.05, list(result.bid_entries())[0].amount)
        self.assertEqual(57057.73, list(result.ask_entries())[0].price)
        self.assertEqual(0.007019, list(result.ask_entries())[0].amount)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_when_subscribing_raised_cancelled(self, ws_connect_mock):
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_subscriptions())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.huobi.huobi_api_order_book_data_source.HuobiAPIOrderBookDataSource._sleep")
    def test_listen_for_subscriptions_raises_logs_exception(self, sleep_mock, ws_connect_mock):
        sleep_mock.side_effect = lambda *_: (
            # Allows listen_for_subscriptions to yield control over thread
            self.ev_loop.run_until_complete(asyncio.sleep(0.0))
        )
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.receive.side_effect = lambda *_: self._create_exception_and_unlock_test_with_event(
            Exception("TEST ERROR")
        )
        self.async_tasks.append(self.ev_loop.create_task(self.data_source.listen_for_subscriptions()))

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged(
                "ERROR", "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_successful_subbed(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        subbed_message = {
            "id": self.ex_trading_pair,
            "status": "ok",
            "subbed": f"market.{self.ex_trading_pair}.depth.step0",
            "ts": 1637333566824,
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=self._compress(subbed_message), message_type=aiohttp.WSMsgType.BINARY
        )

        self.async_tasks.append(self.ev_loop.create_task(self.data_source.listen_for_subscriptions()))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(0, self.data_source._message_queue[self.data_source.TRADE_CHANNEL_SUFFIX].qsize())
        self.assertEqual(0, self.data_source._message_queue[self.data_source.ORDERBOOK_CHANNEL_SUFFIX].qsize())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_handle_ping_successful(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        ping_message = {"ping": 1637333569837}
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=self._compress(ping_message), message_type=aiohttp.WSMsgType.BINARY
        )

        # Adds a dummy message to ensure ping message is being handle before breaking from listening task.
        dummy_message = {"msg": "DUMMY MESSAGE"}
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=self._compress(dummy_message), message_type=aiohttp.WSMsgType.BINARY
        )

        self.async_tasks.append(self.ev_loop.create_task(self.data_source.listen_for_subscriptions()))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(0, self.data_source._message_queue[self.data_source.TRADE_CHANNEL_SUFFIX].qsize())
        self.assertEqual(0, self.data_source._message_queue[self.data_source.ORDERBOOK_CHANNEL_SUFFIX].qsize())
        sent_json: List[Dict[str, Any]] = self.mocking_assistant.json_messages_sent_through_websocket(
            ws_connect_mock.return_value
        )

        self.assertTrue(any(["pong" in str(payload) for payload in sent_json]))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_successfully_append_trade_and_orderbook_messages(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        trade_message = {
            "ch": f"market.{self.ex_trading_pair}.trade.detail",
            "ts": 1630994963175,
            "tick": {
                "id": 137005445109,
                "ts": 1630994963173,
                "data": [
                    {
                        "id": 137005445109359286410323766,
                        "ts": 1630994963173,
                        "tradeId": 102523573486,
                        "amount": 0.006754,
                        "price": 52648.62,
                        "direction": "buy",
                    }
                ],
            },
        }
        orderbook_message = {
            "ch": f"market.{self.ex_trading_pair}.depth.step0",
            "ts": 1630983549503,
            "tick": {
                "bids": [[52690.69, 0.36281], [52690.68, 0.2]],
                "asks": [[52690.7, 0.372591], [52691.26, 0.13]],
                "version": 136998124622,
                "ts": 1630983549500,
            },
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=self._compress(trade_message), message_type=aiohttp.WSMsgType.BINARY
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            message=self._compress(orderbook_message),
            message_type=aiohttp.WSMsgType.BINARY,
        )

        self.async_tasks.append(self.ev_loop.create_task(self.data_source.listen_for_subscriptions()))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(1, self.data_source._message_queue[self.data_source.TRADE_CHANNEL_SUFFIX].qsize())
        self.assertEqual(1, self.data_source._message_queue[self.data_source.ORDERBOOK_CHANNEL_SUFFIX].qsize())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_trades_logs_exception(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        trade_message = {"ch": f"market.{self.ex_trading_pair}.trade.detail", "err": "INCOMPLETE MESSAGE"}
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=self._compress(trade_message), message_type=aiohttp.WSMsgType.BINARY
        )
        self.async_tasks.append(self.ev_loop.create_task(self.data_source.listen_for_subscriptions()))
        msg_queue = asyncio.Queue()
        self.async_tasks.append(self.ev_loop.create_task(self.data_source.listen_for_trades(self.ev_loop, msg_queue)))
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(0, msg_queue.qsize())
        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error with WebSocket connection. Retrying after 30 seconds...")
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_trades_successful(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        trade_message = {
            "ch": f"market.{self.ex_trading_pair}.trade.detail",
            "ts": 1630994963175,
            "tick": {
                "id": 137005445109,
                "ts": 1630994963173,
                "data": [
                    {
                        "id": 137005445109359286410323766,
                        "ts": 1630994963173,
                        "tradeId": 102523573486,
                        "amount": 0.006754,
                        "price": 52648.62,
                        "direction": "buy",
                    }
                ],
            },
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message=self._compress(trade_message), message_type=aiohttp.WSMsgType.BINARY
        )
        self.async_tasks.append(self.ev_loop.create_task(self.data_source.listen_for_subscriptions()))

        msg_queue = asyncio.Queue()
        self.async_tasks.append(self.ev_loop.create_task(self.data_source.listen_for_trades(self.ev_loop, msg_queue)))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(1, msg_queue.qsize())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_logs_exception(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        orderbook_message = {"ch": f"market.{self.ex_trading_pair}.depth.step0", "err": "INCOMPLETE MESSAGE"}
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            message=self._compress(orderbook_message),
            message_type=aiohttp.WSMsgType.BINARY,
        )
        self.async_tasks.append(self.ev_loop.create_task(self.data_source.listen_for_subscriptions()))
        msg_queue = asyncio.Queue()
        self.async_tasks.append(
            self.ev_loop.create_task(self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue))
        )
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(0, msg_queue.qsize())
        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error with WebSocket connection. Retrying after 30 seconds...")
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_successful(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        orderbook_message = {
            "ch": f"market.{self.ex_trading_pair}.depth.step0",
            "ts": 1630983549503,
            "tick": {
                "bids": [[52690.69, 0.36281], [52690.68, 0.2]],
                "asks": [[52690.7, 0.372591], [52691.26, 0.13]],
                "version": 136998124622,
                "ts": 1630983549500,
            },
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            message=self._compress(orderbook_message),
            message_type=aiohttp.WSMsgType.BINARY,
        )
        self.async_tasks.append(self.ev_loop.create_task(self.data_source.listen_for_subscriptions()))

        msg_queue = asyncio.Queue()
        self.async_tasks.append(
            self.ev_loop.create_task(self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue))
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(1, msg_queue.qsize())

    @aioresponses()
    @patch("hummingbot.connector.exchange.huobi.huobi_api_order_book_data_source.HuobiAPIOrderBookDataSource._sleep")
    def test_listen_for_order_book_snapshots_successful(self, mock_api, _):
        url = CONSTANTS.REST_URL + CONSTANTS.DEPTH_URL
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "ch": f"market.{self.ex_trading_pair}.depth.step0",
            "status": "ok",
            "ts": 1637255180894,
            "tick": {
                "bids": [
                    [57069.57, 0.05],
                ],
                "asks": [
                    [57057.73, 0.007019],
                ],
                "version": 141982962388,
                "ts": 1637255180700,
            },
        }

        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        mock_api.get(regex_url, exception=asyncio.CancelledError)

        msg_queue = asyncio.Queue()

        # Purposefully raised error to exit task loop
        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue))

        result = self.async_run_with_timeout(coroutine=msg_queue.get())

        self.assertIsInstance(result, OrderBookMessage)
