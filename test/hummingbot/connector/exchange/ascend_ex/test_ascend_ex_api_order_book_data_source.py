import asyncio
import json
import re
from typing import Awaitable, Optional
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant
from unittest import TestCase
from unittest.mock import AsyncMock, patch

import aiohttp
from aioresponses import aioresponses
from hummingbot.connector.exchange.ascend_ex import ascend_ex_constants as CONSTANTS
from hummingbot.connector.exchange.ascend_ex.ascend_ex_api_order_book_data_source import AscendExAPIOrderBookDataSource
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class AscendExAPIOrderBookDataSourceTests(TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    def setUp(self) -> None:
        super().setUp()

        self.ev_loop = asyncio.get_event_loop()

        self.base_asset = "BTC"
        self.quote_asset = "USDT"
        self.trading_pair = f"{self.base_asset}-{self.quote_asset}"
        self.ex_trading_pair = f"{self.base_asset}/{self.quote_asset}"

        self.log_records = []
        self.listening_task = None
        self.async_task: Optional[asyncio.Task] = None

        self.shared_client = None
        self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)

        self.data_source = AscendExAPIOrderBookDataSource(
            shared_client=self.shared_client, throttler=self.throttler, trading_pairs=[self.trading_pair]
        )
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)
        self.data_source._trading_pair_symbol_map = {}

        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        self.async_task and self.async_task.cancel()
        self.listening_task and self.listening_task.cancel()
        self.data_source._shared_client and self.data_source._shared_client.close()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _raise_exception(self, exception_class):
        raise exception_class

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @aioresponses()
    def test_fetch_trading_pairs(self, api_mock):
        mock_response = {
            "code": 0,
            "data": [
                {
                    "symbol": self.ex_trading_pair,
                    "open": "0.06777",
                    "close": "0.06809",
                    "high": "0.06899",
                    "low": "0.06708",
                    "volume": "19823722",
                    "ask": ["0.0681", "43641"],
                    "bid": ["0.0676", "443"],
                },
                {
                    "symbol": "BTC/USDT",
                    "open": "0.06777",
                    "close": "0.06809",
                    "high": "0.06899",
                    "low": "0.06708",
                    "volume": "19823722",
                    "ask": ["0.0681", "43641"],
                    "bid": ["0.0676", "443"],
                },
                {
                    "symbol": "ETH/USDT",
                    "open": "0.06777",
                    "close": "0.06809",
                    "high": "0.06899",
                    "low": "0.06708",
                    "volume": "19823722",
                    "ask": ["0.0681", "43641"],
                    "bid": ["0.0676", "443"],
                },
            ],
        }

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.TICKER_PATH_URL}"
        api_mock.get(url, body=json.dumps(mock_response))

        trading_pairs = self.async_run_with_timeout(
            self.data_source.fetch_trading_pairs(client=self.data_source._shared_client, throttler=self.throttler)
        )

        self.assertEqual(3, len(trading_pairs))
        self.assertEqual("BTC-USDT", trading_pairs[1])

    @aioresponses()
    def test_get_last_traded_prices_requests_rest_api_price_when_subscription_price_not_available(self, api_mock):
        mock_response = {
            "code": 0,
            "data": {
                "m": "trades",
                "symbol": "BTC/USDT",
                "data": [
                    {"seqnum": 144115191800016553, "p": "0.06762", "q": "400", "ts": 1573165890854, "bm": False},
                    {"seqnum": 144115191800070421, "p": "0.06797", "q": "341", "ts": 1573166037845, "bm": True},
                ],
            },
        }

        self.data_source._trading_pairs = ["BTC-USDT"]

        url = re.escape(f"{CONSTANTS.REST_URL}/{CONSTANTS.TRADES_PATH_URL}?symbol=")
        regex_url = re.compile(f"^{url}")
        api_mock.get(regex_url, body=json.dumps(mock_response))

        results = self.ev_loop.run_until_complete(
            self.data_source.get_last_traded_prices(
                trading_pairs=[self.trading_pair], client=self.data_source._shared_client, throttler=self.throttler
            )
        )

        self.assertEqual(results[self.trading_pair], float(mock_response["data"]["data"][1]["p"]))

    @aioresponses()
    def test_get_order_book_http_error_raises_exception(self, api_mock):
        mock_response = "ERROR WITH REQUEST"
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.DEPTH_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        api_mock.get(regex_url, status=400, body=mock_response)

        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                self.data_source.get_order_book_data(trading_pair=self.trading_pair, throttler=self.throttler)
            )

    @aioresponses()
    def test_get_order_book_resp_code_erro_raises_exception(self, api_mock):
        mock_response = {"code": 100001, "reason": "INVALID_HTTP_INPUT", "message": "Http request is invalid"}
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.DEPTH_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        api_mock.get(regex_url, body=json.dumps(mock_response))

        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                self.data_source.get_order_book_data(trading_pair=self.trading_pair, throttler=self.throttler)
            )

    @aioresponses()
    def test_get_order_book_data_successful(self, api_mock):
        mock_response = {
            "code": 0,
            "data": {
                "m": "depth-snapshot",
                "symbol": self.ex_trading_pair,
                "data": {
                    "seqnum": 5068757,
                    "ts": 1573165838976,
                    "asks": [["0.06848", "4084.2"], ["0.0696", "15890.6"]],
                    "bids": [["0.06703", "13500"], ["0.06615", "24036.9"]],
                },
            },
        }
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.DEPTH_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        api_mock.get(regex_url, body=json.dumps(mock_response))

        result = self.async_run_with_timeout(
            self.data_source.get_order_book_data(trading_pair=self.trading_pair, throttler=self.throttler)
        )

        self.assertTrue(result.get("symbol") == self.ex_trading_pair)

    @aioresponses()
    def test_get_new_order_book(self, api_mock):
        mock_response = {
            "code": 0,
            "data": {
                "m": "depth-snapshot",
                "symbol": "BTC/USDT",
                "data": {
                    "seqnum": 5068757,
                    "ts": 1573165838976,
                    "asks": [["0.06848", "4084.2"], ["0.0696", "15890.6"]],
                    "bids": [["0.06703", "13500"], ["0.06615", "24036.9"]],
                },
            },
        }

        self.data_source._trading_pairs = ["BTC-USDT"]

        # path_url = ascend_ex_utils.rest_api_path_for_endpoint(CONSTANTS.ORDER_BOOK_ENDPOINT, self.trading_pair)
        url = re.escape(f"{CONSTANTS.REST_URL}/{CONSTANTS.DEPTH_PATH_URL}?symbol=")
        regex_url = re.compile(f"^{url}")
        api_mock.get(regex_url, body=json.dumps(mock_response))

        self.listening_task = self.ev_loop.create_task(self.data_source.get_new_order_book(self.trading_pair))
        order_book = self.ev_loop.run_until_complete(self.listening_task)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())

        self.assertEqual(2, len(bids))
        self.assertEqual(0.06703, round(bids[0].price, 5))
        self.assertEqual(13500, round(bids[0].amount, 1))
        self.assertEqual(1573165838976, bids[0].update_id)
        self.assertEqual(2, len(asks))
        self.assertEqual(0.06848, round(asks[0].price, 5))
        self.assertEqual(4084.2, round(asks[0].amount, 1))
        self.assertEqual(1573165838976, asks[0].update_id)

    @patch("aiohttp.client.ClientSession.ws_connect")
    def test_subscribe_to_order_book_streams_raises_exception(self, ws_connect_mock):
        ws_connect_mock.side_effect = Exception("TEST ERROR")

        with self.assertRaisesRegex(Exception, "TEST ERROR"):
            self.async_run_with_timeout(self.data_source._subscribe_to_order_book_streams())

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred subscribing to order book trading and delta streams...")
        )

    @patch("aiohttp.client.ClientSession.ws_connect")
    def test_subscribe_to_order_book_streams_raises_cancel_exception(self, ws_connect_mock):
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source._subscribe_to_order_book_streams())

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_subscribe_to_order_book_streams_successful(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.async_run_with_timeout(self.data_source._subscribe_to_order_book_streams())

        self.assertTrue(
            self._is_logged("INFO", f"Subscribed to ['{self.trading_pair}'] orderbook trading and delta streams...")
        )

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(ws_connect_mock.return_value)
        stream_topics = [payload["ch"] for payload in sent_messages]
        self.assertEqual(2, len(stream_topics))
        self.assertTrue(f"{self.data_source.DIFF_TOPIC_ID}:{self.ex_trading_pair}" in stream_topics)
        self.assertTrue(f"{self.data_source.TRADE_TOPIC_ID}:{self.ex_trading_pair}" in stream_topics)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_exception_raised_cancelled_when_connecting(self, ws_connect_mock):
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_subscriptions())

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_exception_raised_cancelled_when_subscribing(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.send_json.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_subscriptions())

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_exception_raised_cancelled_when_listening(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.receive.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_subscriptions())

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.ascend_ex.ascend_ex_api_order_book_data_source.AscendExAPIOrderBookDataSource._sleep")
    def test_listen_for_subscription_logs_exception(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.receive.side_effect = lambda: self._create_exception_and_unlock_test_with_event(
            Exception("TEST ERROR")
        )
        self.async_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(self._is_logged("ERROR", "Unexpected error occurred iterating through websocket messages."))
        self.assertTrue(
            self._is_logged(
                "ERROR", "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."
            )
        )

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_enqueues_diff_and_trade_messages(self, ws_connect_mock):
        diffs_queue = self.data_source._message_queue[self.data_source.DIFF_TOPIC_ID]
        trade_queue = self.data_source._message_queue[self.data_source.TRADE_TOPIC_ID]

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        # Add diff event message be processed
        diff_response = {
            "m": "depth",
            "symbol": self.ex_trading_pair,
            "data": {
                "ts": 1573069021376,
                "seqnum": 2097965,
                "asks": [["0.06844", "10760"]],
                "bids": [["0.06777", "562.4"], ["0.05", "221760.6"]],
            },
        }
        # Add trade event message be processed
        trade_response = {
            "m": "trades",
            "symbol": "BTC/USDT",
            "data": [
                {"seqnum": 144115191800016553, "p": "0.06762", "q": "400", "ts": 1573165890854, "bm": False},
                {"seqnum": 144115191800070421, "p": "0.06797", "q": "341", "ts": 1573166037845, "bm": True},
            ],
        }
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(diff_response))
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(trade_response))

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(1, diffs_queue.qsize())
        self.assertEqual(1, trade_queue.qsize())

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_handle_ping_message(self, ws_connect_mock):
        # In AscendEx Ping message is sent as a aiohttp.WSMsgType.TEXT message
        mock_response = {"m": "ping", "hp": 3}
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(mock_response),
            message_type=aiohttp.WSMsgType.TEXT,
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        sent_json = self.mocking_assistant.json_messages_sent_through_websocket(ws_connect_mock.return_value)

        self.assertTrue(any(["pong" in str(payload) for payload in sent_json]))

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diff_raises_cancel_exceptions(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(ev_loop=self.ev_loop, output=queue)
        )

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task.cancel()
            self.ev_loop.run_until_complete(self.listening_task)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.ascend_ex.ascend_ex_api_order_book_data_source.AscendExAPIOrderBookDataSource._sleep")
    def test_listen_for_order_book_diff_logs_exception_parsing_message(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        # Add incomplete diff event message be processed
        diff_response = {
            "m": "depth",
            "symbol": "incomplete response"
        }
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(diff_response))

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        output_queue = asyncio.Queue()
        self.async_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(ev_loop=self.ev_loop, output=output_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error with WebSocket connection. Retrying after 30 seconds...")
        )

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diff_successful(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        # Add diff event message be processed
        diff_response = {
            "m": "depth",
            "symbol": self.ex_trading_pair,
            "data": {
                "ts": 1573069021376,
                "seqnum": 2097965,
                "asks": [["0.06844", "10760"]],
                "bids": [["0.06777", "562.4"], ["0.05", "221760.6"]],
            },
        }
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(diff_response))

        diffs_queue = self.data_source._message_queue[self.data_source.DIFF_TOPIC_ID]
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        output_queue = asyncio.Queue()
        self.async_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(ev_loop=self.ev_loop, output=output_queue)
        )

        order_book_message = self.async_run_with_timeout(output_queue.get())

        self.assertTrue(diffs_queue.empty())
        self.assertEqual(1573069021376, order_book_message.update_id)
        self.assertEqual(1573069021376, order_book_message.timestamp)
        self.assertEqual(0.06777, order_book_message.bids[0].price)
        self.assertEqual(0.05, order_book_message.bids[1].price)
        self.assertEqual(0.06844, order_book_message.asks[0].price)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_trades_raises_cancel_exceptions(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(ev_loop=self.ev_loop, output=queue)
        )

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task.cancel()
            self.ev_loop.run_until_complete(self.listening_task)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.ascend_ex.ascend_ex_api_order_book_data_source.AscendExAPIOrderBookDataSource._sleep")
    def test_listen_for_trades_logs_exception_parsing_message(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        # Add incomplete diff event message be processed
        diff_response = {
            "m": "trades",
            "symbol": "incomplete response"
        }
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(diff_response))

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        output_queue = asyncio.Queue()
        self.async_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(ev_loop=self.ev_loop, output=output_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error with WebSocket connection. Retrying after 30 seconds...")
        )

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_trades_successful(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        # Add trade event message be processed
        trade_response = {
            "m": "trades",
            "symbol": "BTC/USDT",
            "data": [
                {"seqnum": 144115191800016553, "p": "0.06762", "q": "400", "ts": 1573165890854, "bm": False},
                {"seqnum": 144115191800070421, "p": "0.06797", "q": "341", "ts": 1573166037845, "bm": True},
            ],
        }
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(trade_response))

        trades_queue = self.data_source._message_queue[self.data_source.DIFF_TOPIC_ID]
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        output_queue = asyncio.Queue()
        self.async_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(ev_loop=self.ev_loop, output=output_queue)
        )

        first_trade_message = self.async_run_with_timeout(output_queue.get())
        second_trade_message = self.async_run_with_timeout(output_queue.get())

        self.assertTrue(trades_queue.empty())
        self.assertEqual(1573165890854, first_trade_message.timestamp)
        self.assertEqual(1573166037845, second_trade_message.timestamp)

    @aioresponses()
    def test_listen_for_order_book_snapshot_event(self, api_mock):
        mock_response = {
            "code": 0,
            "data": {
                "m": "depth-snapshot",
                "symbol": self.ex_trading_pair,
                "data": {
                    "seqnum": 5068757,
                    "ts": 1573165838976,
                    "asks": [["0.06848", "4084.2"], ["0.0696", "15890.6"]],
                    "bids": [["0.06703", "13500"], ["0.06615", "24036.9"]],
                },
            },
        }

        self.data_source._trading_pairs = ["BTC-USDT"]

        # Add trade event message be processed
        url = re.escape(f"{CONSTANTS.REST_URL}/{CONSTANTS.DEPTH_PATH_URL}?symbol=")
        regex_url = re.compile(f"^{url}")
        api_mock.get(regex_url, body=json.dumps(mock_response))

        order_book_messages = asyncio.Queue()

        task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(ev_loop=self.ev_loop, output=order_book_messages)
        )

        order_book_message = self.ev_loop.run_until_complete(order_book_messages.get())

        try:
            task.cancel()
            self.ev_loop.run_until_complete(task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass

        self.assertTrue(order_book_messages.empty())
        self.assertEqual(1573165838976, order_book_message.update_id)
        self.assertEqual(1573165838976, order_book_message.timestamp)
        self.assertEqual(0.06703, order_book_message.bids[0].price)
        self.assertEqual(0.06848, order_book_message.asks[0].price)
