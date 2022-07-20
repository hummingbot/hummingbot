import asyncio
import json
import re
from typing import Awaitable, Optional
from unittest import TestCase
from unittest.mock import AsyncMock, patch

import aiohttp
from aioresponses import aioresponses
from bidict import bidict

from hummingbot.connector.exchange.southxchange import southxchange_constants as CONSTANTS
from hummingbot.connector.exchange.southxchange.southxchange_api_order_book_data_source import SouthxchangeAPIOrderBookDataSource
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.utils import build_api_factory
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.connector.exchange.southxchange.southxchange_exchange import SouthxchangeExchange
from test.connector.exchange.southxchange.test_fixture_southxchange import Fixturesouthxchange
from hummingbot.connector.exchange.southxchange.southxchange_utils import convert_to_exchange_trading_pair
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
API_BASE_URL = "https://www.southxchange.com"


class SouthxchangeAPIOrderBookDataSourceTests(TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "LTC2"
        cls.quote_asset = "USD2"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}/{cls.quote_asset}"
        cls.api_key = "someKey"
        cls.api_secret_key = "someSecretKey"
        cls.client_config_map = ClientConfigAdapter(ClientConfigMap())

        cls.exchange = SouthxchangeExchange(
            client_config_map=cls.client_config_map,
            southxchange_api_key=cls.api_key,
            southxchange_secret_key=cls.api_secret_key,
            trading_pairs=[cls.trading_pair])

    def setUp(self) -> None:
        super().setUp()

        self._connector = SouthxchangeAPIOrderBookDataSourceTests.exchange
        self.ev_loop = asyncio.get_event_loop()

        self.base_asset = "LTC2"
        self.quote_asset = "BTC2"
        self.trading_pair = f"{self.base_asset}-{self.quote_asset}"
        self.ex_trading_pair = f"{self.base_asset}/{self.quote_asset}"

        self.log_records = []
        self.listening_task = None
        self.async_task: Optional[asyncio.Task] = None

        self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self.api_factory = build_api_factory(throttler=self.throttler)

        self.data_source = SouthxchangeAPIOrderBookDataSource(
            connector=self.exchange, api_factory=self.api_factory, throttler=self.throttler, trading_pairs=[self.trading_pair]
        )
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

        SouthxchangeAPIOrderBookDataSource._trading_pair_symbol_map = bidict(
            {self.ex_trading_pair: f"{self.base_asset}-{self.quote_asset}"}
        )

    def tearDown(self) -> None:
        self.async_task and self.async_task.cancel()
        self.listening_task and self.listening_task.cancel()
        SouthxchangeAPIOrderBookDataSource._trading_pair_symbol_map = None
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
        SouthxchangeAPIOrderBookDataSource._trading_pair_symbol_map = None

        url = f"{API_BASE_URL}/{'api/v4/markets'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        api_mock.get(regex_url, body=json.dumps(Fixturesouthxchange.MARKETS))

        trading_pairs = self.async_run_with_timeout(
            self.data_source.fetch_trading_pairs()
        )

        self.assertEqual(5, len(trading_pairs))
        self.assertEqual("LTC2-BTC2", trading_pairs[1])

    @aioresponses()
    def test_get_last_traded_prices_requests_rest_api_price(self, api_mock):

        self.data_source._trading_pairs = ["LTC2-BTC2"]

        url = f"{API_BASE_URL}/{'api/v4/trades'}/{convert_to_exchange_trading_pair('LTC2-BTC2')}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        api_mock.get(regex_url, body=json.dumps(Fixturesouthxchange.TRADES))

        results = self.ev_loop.run_until_complete(
            self.data_source.get_last_traded_prices(
                trading_pairs=[self.trading_pair], api_factory=self.data_source._api_factory, throttler=self.throttler
            )
        )

        self.assertEqual(results[self.trading_pair], Fixturesouthxchange.TRADES[1]['Price'])

    @aioresponses()
    def test_get_order_book_http_error_raises_exception(self, api_mock):
        mock_response = "ERROR WITH REQUEST"
        url = f"{API_BASE_URL}/{'api/v4/book'}/{convert_to_exchange_trading_pair('LTC2-BTC2')}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        api_mock.get(regex_url, status=400, body=mock_response)

        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                self.data_source.get_order_book_data(trading_pair=self.trading_pair, throttler=self.throttler)
            )

    @aioresponses()
    def test_get_order_book_resp_code_error_raises_exception(self, api_mock):
        url = f"{API_BASE_URL}/{'api/v4/book'}/{convert_to_exchange_trading_pair('LTC2-BTC2')}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        api_mock.get(regex_url, status=400, body=json.dumps(Fixturesouthxchange.OPEN_ORDERS))

        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                self.data_source.get_order_book_data(trading_pair=self.trading_pair, throttler=self.throttler)
            )

    @aioresponses()
    def test_get_order_book_data_successful(self, api_mock):
        url = f"{API_BASE_URL}/{'api/v4/book'}/{convert_to_exchange_trading_pair('LTC2-BTC2')}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        api_mock.get(regex_url, body=json.dumps(Fixturesouthxchange.ORDERS_BOOK))

        result = self.async_run_with_timeout(
            self.data_source.get_order_book_data(trading_pair=self.trading_pair, throttler=self.throttler)
        )

        self.assertTrue(len(result) == 2)

    @aioresponses()
    def test_get_new_order_book(self, api_mock):
        self.data_source._trading_pairs = ["LTC2-BTC2"]

        url = f"{API_BASE_URL}/{'api/v4/book'}/{convert_to_exchange_trading_pair('LTC2-BTC2')}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        api_mock.get(regex_url, body=json.dumps(Fixturesouthxchange.ORDERS_BOOK))

        self.listening_task = self.ev_loop.create_task(self.data_source.get_new_order_book(self.trading_pair))
        order_book = self.ev_loop.run_until_complete(self.listening_task)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())

        self.assertEqual(2, len(bids))
        self.assertEqual(93.6, round(bids[0].price, 1))
        self.assertEqual(0.011, round(bids[0].amount, 3))
        self.assertEqual(2, len(asks))
        self.assertEqual(93.6, round(asks[0].price, 1))
        self.assertEqual(0.99, round(asks[0].amount, 2))

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
        self.assertEqual("subscribe", sent_messages[0]['k'])
        self.assertEqual(self.ex_trading_pair, sent_messages[0]['v'])

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

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscription_logs_exception(self, ws_connect_mock, sleep_mock):
        ws_connect_mock.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."))

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_enqueues_diff_and_trade_messages(self, ws_connect_mock):
        diffs_queue = self.data_source._message_queue['bookdelta']
        trade_queue = self.data_source._message_queue['trade']

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(Fixturesouthxchange.WS_BOOKDELTA))
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(Fixturesouthxchange.WS_TRADE))

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(1, diffs_queue.qsize())
        self.assertEqual(1, trade_queue.qsize())

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

        self.assertTrue(any(["subscribe" in str(payload) for payload in sent_json]))

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.southxchange.southxchange_api_order_book_data_source.SouthxchangeAPIOrderBookDataSource._sleep")
    def test_listen_for_order_book_diff_logs_exception_parsing_message(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        # Add incomplete diff event message be processed
        diff_response = {
            "k": "bookdelta",
            "v": "incomplete response"
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
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(Fixturesouthxchange.WS_BOOKDELTA))

        diffs_queue = self.data_source._message_queue['bookdelta']
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        output_queue = asyncio.Queue()
        self.async_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(ev_loop=self.ev_loop, output=output_queue)
        )

        order_book_message = self.async_run_with_timeout(output_queue.get())

        self.assertTrue(diffs_queue.empty())
        self.assertEqual(118.75, order_book_message.bids[0].price)
        self.assertEqual(1.0, order_book_message.bids[0].amount)
        self.assertEqual(120, order_book_message.asks[0].price)
        self.assertEqual(0.9, order_book_message.asks[0].amount)

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
    @patch("hummingbot.connector.exchange.southxchange.southxchange_api_order_book_data_source.SouthxchangeAPIOrderBookDataSource._sleep")
    def test_listen_for_trades_logs_exception_parsing_message(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        # Add incomplete diff event message be processed
        diff_response = {
            "k": "trade",
            "v": "incomplete response"
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
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(Fixturesouthxchange.WS_TRADE))

        trades_queue = self.data_source._message_queue['trade']
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        output_queue = asyncio.Queue()
        self.async_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(ev_loop=self.ev_loop, output=output_queue)
        )

        first_trade_message = self.async_run_with_timeout(output_queue.get())
        second_trade_message = self.async_run_with_timeout(output_queue.get())

        self.assertTrue(trades_queue.empty())
        self.assertEqual(1657923640, first_trade_message.timestamp)
        self.assertEqual(1657923426, second_trade_message.timestamp)

    @aioresponses()
    def test_listen_for_order_book_snapshot_event(self, api_mock):
        self.data_source._trading_pairs = ["LTC2-BTC2"]

        url = f"{API_BASE_URL}/{'api/v4/book'}/{convert_to_exchange_trading_pair('LTC2-BTC2')}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        api_mock.get(regex_url, body=json.dumps(Fixturesouthxchange.ORDERS_BOOK))

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
        self.assertEqual(93.6, order_book_message.bids[0].price)
        self.assertEqual(101.0, order_book_message.asks[1].price)
