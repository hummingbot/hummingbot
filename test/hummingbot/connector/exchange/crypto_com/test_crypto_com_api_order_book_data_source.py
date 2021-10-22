import asyncio
import re
import ujson
import unittest

from aioresponses import aioresponses
from typing import Awaitable, Optional
from unittest.mock import AsyncMock, patch

from hummingbot.connector.exchange.crypto_com import crypto_com_constants as CONSTANTS
from hummingbot.connector.exchange.crypto_com import crypto_com_utils
from hummingbot.connector.exchange.crypto_com.crypto_com_api_order_book_data_source import (
    CryptoComAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.crypto_com.crypto_com_websocket import CryptoComWebsocket
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class CryptoComAPIOrderBookDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = crypto_com_utils.convert_to_exchange_trading_pair(cls.trading_pair)

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []
        self.async_task: Optional[asyncio.Task] = None

        self.data_source = CryptoComAPIOrderBookDataSource(trading_pairs=[self.trading_pair])

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_get_throttler_instance(self):
        self.assertIsInstance(self.data_source._get_throttler_instance(), AsyncThrottler)

    @aioresponses()
    def test_get_last_trade_prices(self, mock_api):
        url = crypto_com_utils.get_rest_url(path_url=CONSTANTS.GET_TICKER_PATH_URL)
        regex_url = re.compile(f"^{url}")

        expected_last_traded_price = 1.0

        mock_responses = {
            "code": 0,
            "method": "public/get-ticker",
            "result": {
                "data": [
                    {  # Truncated Response
                        "i": self.ex_trading_pair,
                        "a": expected_last_traded_price,
                    }
                ]
            },
        }
        mock_api.get(regex_url, body=ujson.dumps(mock_responses))

        result = self.async_run_with_timeout(self.data_source.get_last_traded_prices(trading_pairs=[self.trading_pair]))

        self.assertEqual(result[self.trading_pair], expected_last_traded_price)

    @aioresponses()
    def test_fetch_trading_pairs(self, mock_api):
        url = crypto_com_utils.get_rest_url(path_url=CONSTANTS.GET_TICKER_PATH_URL)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "code": 0,
            "method": "public/get-ticker",
            "result": {
                "data": [
                    {  # Truncated Response
                        "i": self.ex_trading_pair,
                        "a": 1.0,
                    }
                ]
            },
        }

        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        result = self.async_run_with_timeout(self.data_source.fetch_trading_pairs())

        self.assertTrue(self.trading_pair in result)

    @aioresponses()
    def test_get_order_book_data(self, mock_api):
        url = crypto_com_utils.get_rest_url(path_url=CONSTANTS.GET_ORDER_BOOK_PATH_URL)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "code": 0,
            "method": "public/get-book",
            "result": {
                "instrument_name": self.ex_trading_pair,
                "depth": 150,
                "data": [
                    {
                        "bids": [
                            [999.00, 1.0, 1],
                        ],
                        "asks": [
                            [1000.00, 1.0, 1],
                        ],
                        "t": 1634731570152,
                    }
                ],
            },
        }

        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        result = self.async_run_with_timeout(self.data_source.get_order_book_data(self.trading_pair))

        self.assertIsInstance(result, dict)

    @aioresponses()
    def test_get_new_order_book(self, mock_api):
        url = crypto_com_utils.get_rest_url(path_url=CONSTANTS.GET_ORDER_BOOK_PATH_URL)
        regex_url = re.compile(f"^{url}")

        snapshot_timestamp = 1634731570152
        mock_response = {
            "code": 0,
            "method": "public/get-book",
            "result": {
                "instrument_name": self.ex_trading_pair,
                "depth": 150,
                "data": [
                    {
                        "bids": [
                            [999.00, 1.0, 1],
                        ],
                        "asks": [
                            [1000.00, 1.0, 1],
                        ],
                        "t": snapshot_timestamp,
                    }
                ],
            },
        }

        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        result = self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))

        self.assertIsInstance(result, OrderBook)
        self.assertEqual(snapshot_timestamp, result.snapshot_uid)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_create_websocket_connection_raised_cancelled(self, ws_connect_mock):
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source._create_websocket_connection())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_create_websocket_connection_logs_exception(self, ws_connect_mock):
        ws_connect_mock.side_effect = Exception("TEST ERROR")

        with self.assertRaisesRegex(Exception, "TEST ERROR"):
            self.async_run_with_timeout(self.data_source._create_websocket_connection())

        self.assertTrue(self._is_logged(
            "NETWORK", "Unexpected error occured connecting to crypto_com WebSocket API. (TEST ERROR)"
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_exception_raised_cancelled_when_connecting(self, ws_connect_mock):
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_subscriptions())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.crypto_com.crypto_com_websocket.CryptoComWebsocket._sleep")
    def test_listen_for_subscriptions_exception_raised_cancelled_when_subscribing(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.send_json.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_subscriptions())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.crypto_com.crypto_com_websocket.CryptoComWebsocket._sleep")
    def test_listen_for_subscriptions_exception_raised_cancelled_when_listening(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.receive.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_subscriptions())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.crypto_com.crypto_com_websocket.CryptoComWebsocket._sleep")
    def test_listen_for_subscription_logs_exception(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.receive.side_effect = lambda: self._create_exception_and_unlock_test_with_event(
            Exception("TEST ERROR")
        )
        self.async_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged(
                "ERROR", "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.crypto_com.crypto_com_websocket.CryptoComWebsocket._sleep")
    def test_listen_for_subscriptions_enqueues_diff_and_trade_messages(self, _, ws_connect_mock):
        diffs_queue = self.data_source._message_queue[CryptoComWebsocket.DIFF_CHANNEL_ID]
        trade_queue = self.data_source._message_queue[CryptoComWebsocket.TRADE_CHANNEL_ID]

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        # Add diff event message be processed
        diff_response = {
            "method": "subscribe",
            "result": {
                "instrument_name": self.ex_trading_pair,
                "subscription": f"book.{self.ex_trading_pair}.150",
                "channel": "book",
                "depth": 150,
                "data": [{"bids": [[11746.488, 128, 8]], "asks": [[11747.488, 201, 12]], "t": 1587523078844}],
            },
        }

        # Add trade event message be processed
        trade_response = {
            "method": "subscribe",
            "result": {
                "instrument_name": self.ex_trading_pair,
                "subscription": f"trade.{self.ex_trading_pair}",
                "channel": "trade",
                "data": [
                    {
                        "p": 162.12,
                        "q": 11.085,
                        "s": "buy",
                        "d": 1210447366,
                        "t": 1587523078844,
                        "dataTime": 0,
                        "i": f"{self.ex_trading_pair}",
                    }
                ],
            },
        }

        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, ujson.dumps(diff_response))
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, ujson.dumps(trade_response))

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(1, diffs_queue.qsize())
        self.assertEqual(1, trade_queue.qsize())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.crypto_com.crypto_com_websocket.CryptoComWebsocket._sleep")
    def test_listen_for_order_book_diff_raises_cancel_exceptions(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(ev_loop=self.ev_loop, output=queue)
        )

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task.cancel()
            self.ev_loop.run_until_complete(self.listening_task)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.crypto_com.crypto_com_websocket.CryptoComWebsocket._sleep")
    @patch(
        "hummingbot.connector.exchange.crypto_com.crypto_com_api_order_book_data_source.CryptoComAPIOrderBookDataSource._sleep"
    )
    def test_listen_for_order_book_diff_logs_exception_parsing_message(self, _, __, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        # Add incomplete diff event message be processed
        incomplete_diff_response = {
            "method": "subscribe",
            "result": {"channel": "book", "INCOMPLETE": "PAYLOAD"},
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, ujson.dumps(incomplete_diff_response)
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        output_queue = asyncio.Queue()
        self.async_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(ev_loop=self.ev_loop, output=output_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        self.assertTrue(
            self._is_logged(
                "ERROR",
                f"Unexpected error parsing order book diff payload. Payload: {incomplete_diff_response['result']}",
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.crypto_com.crypto_com_websocket.CryptoComWebsocket._sleep")
    def test_listen_for_order_book_diff_successful(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        # Add diff event message be processed
        diff_response = {
            "method": "subscribe",
            "result": {
                "instrument_name": self.ex_trading_pair,
                "subscription": f"book.{self.ex_trading_pair}.150",
                "channel": "book",
                "depth": 150,
                "data": [{"bids": [[11746.488, 128, 8]], "asks": [[11747.488, 201, 12]], "t": 1587523078844}],
            },
        }
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, ujson.dumps(diff_response))

        diffs_queue = self.data_source._message_queue[CryptoComWebsocket.DIFF_CHANNEL_ID]
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        output_queue = asyncio.Queue()
        self.async_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(ev_loop=self.ev_loop, output=output_queue)
        )

        order_book_message = self.async_run_with_timeout(output_queue.get())

        self.assertTrue(diffs_queue.empty())
        self.assertEqual(1587523078844, order_book_message.update_id)
        self.assertEqual(1587523078844, order_book_message.timestamp)
        self.assertEqual(11746.488, order_book_message.bids[0].price)
        self.assertEqual(11747.488, order_book_message.asks[0].price)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.crypto_com.crypto_com_websocket.CryptoComWebsocket._sleep")
    def test_listen_for_trades_raises_cancel_exceptions(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(ev_loop=self.ev_loop, output=queue)
        )

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task.cancel()
            self.ev_loop.run_until_complete(self.listening_task)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.crypto_com.crypto_com_websocket.CryptoComWebsocket._sleep")
    @patch(
        "hummingbot.connector.exchange.crypto_com.crypto_com_api_order_book_data_source.CryptoComAPIOrderBookDataSource._sleep"
    )
    def test_listen_for_trades_logs_exception_parsing_message(self, _, __, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        # Add incomplete trade event message be processed
        incomplete_trade_response = {
            "method": "subscribe",
            "result": {"channel": "trade", "INCOMPLETE": "PAYLOAD"},
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, ujson.dumps(incomplete_trade_response)
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        output_queue = asyncio.Queue()
        self.async_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(ev_loop=self.ev_loop, output=output_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        self.assertTrue(
            self._is_logged(
                "ERROR",
                f"Unexpected error parsing order book trade payload. Payload: {incomplete_trade_response['result']}",
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.crypto_com.crypto_com_websocket.CryptoComWebsocket._sleep")
    def test_listen_for_trades_successful(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        # Add trade event message be processed
        trade_response = {
            "method": "subscribe",
            "result": {
                "instrument_name": self.ex_trading_pair,
                "subscription": f"trade.{self.ex_trading_pair}",
                "channel": "trade",
                "data": [
                    {
                        "p": 162.12,
                        "q": 11.085,
                        "s": "buy",
                        "d": 1210447366,
                        "t": 1587523078844,
                        "dataTime": 0,
                        "i": f"{self.ex_trading_pair}",
                    }
                ],
            },
        }
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, ujson.dumps(trade_response))

        trades_queue = self.data_source._message_queue[CryptoComWebsocket.TRADE_CHANNEL_ID]
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        output_queue = asyncio.Queue()
        self.async_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(ev_loop=self.ev_loop, output=output_queue)
        )

        first_trade_message = self.async_run_with_timeout(output_queue.get())

        self.assertTrue(trades_queue.empty())
        self.assertEqual(1587523078844, first_trade_message.timestamp)

    @aioresponses()
    def test_listen_for_order_book_snapshots_successful(self, mock_api):
        url = crypto_com_utils.get_rest_url(path_url=CONSTANTS.GET_ORDER_BOOK_PATH_URL)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "code": 0,
            "method": "public/get-book",
            "result": {
                "instrument_name": self.ex_trading_pair,
                "depth": 150,
                "data": [
                    {
                        "bids": [
                            [999.00, 1.0, 1],
                        ],
                        "asks": [
                            [1000.00, 1.0, 1],
                        ],
                        "t": 1634731570152,
                    }
                ],
            },
        }

        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        order_book_messages = asyncio.Queue()

        self.async_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(ev_loop=self.ev_loop, output=order_book_messages)
        )

        order_book_message = self.async_run_with_timeout(order_book_messages.get())

        self.assertTrue(order_book_messages.empty())
        self.assertEqual(1634731570152, order_book_message.update_id)
        self.assertEqual(1634731570152, order_book_message.timestamp)
        self.assertEqual(999.00, order_book_message.bids[0].price)
        self.assertEqual(1000.00, order_book_message.asks[0].price)
