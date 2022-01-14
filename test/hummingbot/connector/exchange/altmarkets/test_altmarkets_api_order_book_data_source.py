import asyncio
import json
import re
from collections import deque
from decimal import Decimal
from typing import Awaitable
from unittest.mock import patch, AsyncMock

from aioresponses import aioresponses
from unittest import TestCase

from hummingbot.connector.exchange.altmarkets.altmarkets_api_order_book_data_source import AltmarketsAPIOrderBookDataSource
from hummingbot.connector.exchange.altmarkets.altmarkets_constants import Constants
from hummingbot.connector.exchange.altmarkets.altmarkets_order_book import AltmarketsOrderBook
from hummingbot.connector.exchange.altmarkets.altmarkets_utils import convert_to_exchange_trading_pair
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class AltmarketsAPIOrderBookDataSourceTests(TestCase):
    # logging.Level required to receive logs from the exchange
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "HBOT"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.exchange_trading_pair = convert_to_exchange_trading_pair(cls.trading_pair)
        cls.api_key = "testKey"
        cls.api_secret_key = "testSecretKey"
        cls.username = "testUsername"
        cls.throttler = AsyncThrottler(Constants.RATE_LIMITS)

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.data_source = AltmarketsAPIOrderBookDataSource(
            throttler=self.throttler,
            trading_pairs=[self.trading_pair])
        self.mocking_assistant = NetworkMockingAssistant()

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @aioresponses()
    def test_get_last_traded_prices(self, mock_api):
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['TICKER_SINGLE'].format(trading_pair=self.exchange_trading_pair)}"
        resp = {"ticker": {"last": 51234.56}}
        mock_api.get(url, body=json.dumps(resp))

        results = self.async_run_with_timeout(AltmarketsAPIOrderBookDataSource.get_last_traded_prices(
            trading_pairs=[self.trading_pair],
            throttler=self.throttler))

        self.assertIn(self.trading_pair, results)
        self.assertEqual(Decimal("51234.56"), results[self.trading_pair])

    @aioresponses()
    def test_fetch_trading_pairs(self, mock_api):
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['SYMBOL']}"
        resp = [
            {
                "name": f"{self.base_asset}/{self.quote_asset}",
                "state": "enabled"
            },
            {
                "name": "ROGER/BTC",
                "state": "enabled"
            }
        ]
        mock_api.get(url, body=json.dumps(resp))

        results = self.async_run_with_timeout(AltmarketsAPIOrderBookDataSource.fetch_trading_pairs(
            throttler=self.throttler))

        self.assertIn(self.trading_pair, results)
        self.assertIn("ROGER-BTC", results)

    @patch("hummingbot.connector.exchange.altmarkets.altmarkets_api_order_book_data_source.AltmarketsAPIOrderBookDataSource._time")
    @aioresponses()
    def test_get_new_order_book(self, time_mock, mock_api):
        time_mock.return_value = 1234567899
        url = f"{Constants.REST_URL}/" \
              f"{Constants.ENDPOINT['ORDER_BOOK'].format(trading_pair=self.exchange_trading_pair)}" \
              "?limit=300"
        resp = {"timestamp": 1234567899,
                "bids": [],
                "asks": []}
        mock_api.get(url, body=json.dumps(resp))

        order_book: AltmarketsOrderBook = self.async_run_with_timeout(
            self.data_source.get_new_order_book(self.trading_pair))

        self.assertEqual(1234567899 * 1e3, order_book.snapshot_uid)

    def test_listen_for_snapshots_cancelled_when_fetching_snapshot(self):
        trades_queue = asyncio.Queue()
        task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(ev_loop=self.ev_loop, output=trades_queue))

        with self.assertRaises(asyncio.CancelledError):
            task.cancel()
            self.ev_loop.run_until_complete(task)

    @aioresponses()
    @patch(
        "hummingbot.connector.exchange.altmarkets.altmarkets_api_order_book_data_source.AltmarketsAPIOrderBookDataSource._sleep",
        new_callable=AsyncMock)
    def test_listen_for_snapshots_logs_exception_when_fetching_snapshot(self, mock_get, mock_sleep):
        # the queue and the division by zero error are used just to synchronize the test
        sync_queue = deque()
        sync_queue.append(1)

        endpoint = Constants.ENDPOINT['ORDER_BOOK'].format(trading_pair=r'[\w]+')
        re_url = f"{Constants.REST_URL}/{endpoint}"
        regex_url = re.compile(re_url)
        for x in range(2):
            mock_get.get(regex_url, body=json.dumps({}))

        mock_sleep.side_effect = lambda delay: 1 / 0 if len(sync_queue) == 0 else sync_queue.pop()

        msg_queue: asyncio.Queue = asyncio.Queue()
        with self.assertRaises(ZeroDivisionError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue))
            self.ev_loop.run_until_complete(self.listening_task)

        self.assertEqual(0, msg_queue.qsize())

        self.assertTrue(self._is_logged("ERROR",
                                        "Unexpected error occurred listening for orderbook snapshots. Retrying in 5 secs..."))

    @aioresponses()
    @patch(
        "hummingbot.connector.exchange.altmarkets.altmarkets_api_order_book_data_source.AltmarketsAPIOrderBookDataSource._sleep",
        new_callable=AsyncMock)
    def test_listen_for_snapshots_successful(self, mock_get, mock_sleep):
        # the queue and the division by zero error are used just to synchronize the test
        sync_queue = deque()
        sync_queue.append(1)

        mock_response = {
            "timestamp": 1234567890,
            "asks": [
                [7221.08, 6.92321326],
                [7220.08, 6.92321326],
                [7222.08, 6.92321326],
                [7219.2, 0.69259752]],
            "bids": [
                [7199.27, 6.95094164],
                [7192.27, 6.95094164],
                [7193.27, 6.95094164],
                [7196.15, 0.69481598]]
        }
        endpoint = Constants.ENDPOINT['ORDER_BOOK'].format(trading_pair=r'[\w]+')
        regex_url = re.compile(f"{Constants.REST_URL}/{endpoint}")
        for x in range(2):
            mock_get.get(regex_url, body=json.dumps(mock_response))

        mock_sleep.side_effect = lambda delay: 1 / 0 if len(sync_queue) == 0 else sync_queue.pop()

        msg_queue: asyncio.Queue = asyncio.Queue()
        with self.assertRaises(ZeroDivisionError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue))
            self.ev_loop.run_until_complete(self.listening_task)

        self.assertEqual(msg_queue.qsize(), 2)

        snapshot_msg: OrderBookMessage = msg_queue.get_nowait()
        self.assertEqual(snapshot_msg.update_id, mock_response["timestamp"] * 1e3)

    @patch("websockets.connect", new_callable=AsyncMock)
    def test_listen_for_trades(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        received_messages = asyncio.Queue()

        message = {
            "hbotusdt.trades": {
                "trades": [
                    {
                        "date": 1234567899,
                        "tid": '3333',
                        "taker_type": "buy",
                        "price": 8772.05,
                        "amount": 0.1,
                    }
                ]
            }
        }

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(ev_loop=self.ev_loop, output=received_messages))

        self.mocking_assistant.add_websocket_text_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(message))
        trade_message = self.async_run_with_timeout(received_messages.get())

        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual(1234567899, trade_message.timestamp)
        self.assertEqual('3333', trade_message.trade_id)
        self.assertEqual(self.trading_pair, trade_message.trading_pair)

    @patch("hummingbot.connector.exchange.altmarkets.altmarkets_api_order_book_data_source.AltmarketsAPIOrderBookDataSource._time")
    @patch("websockets.connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diff(self, ws_connect_mock, time_mock):
        time_mock.return_value = 1234567890
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        received_messages = asyncio.Queue()

        message = {
            "hbotusdt.ob-inc": {
                "timestamp": 1234567890,
                "asks": [
                    ["2", 0],
                    ["1", 0],
                    ["4", 7222.08, 6.92321326],
                    ["6", 7219.2, 0.69259752]],
                "bids": [
                    ["9", 0],
                    ["5", 0],
                    ["7", 7193.27, 6.95094164],
                    ["8", 7196.15, 0.69481598]]
            }
        }

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(ev_loop=self.ev_loop, output=received_messages))

        self.mocking_assistant.add_websocket_text_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(message))
        diff_message = self.async_run_with_timeout(received_messages.get())

        self.assertEqual(OrderBookMessageType.DIFF, diff_message.type)
        self.assertEqual(4, len(diff_message.content.get("bids")))
        self.assertEqual(4, len(diff_message.content.get("asks")))
        self.assertEqual(1234567890, diff_message.timestamp)
        self.assertEqual(int(1234567890 * 1e3), diff_message.update_id)
        self.assertEqual(-1, diff_message.trade_id)
        self.assertEqual(self.trading_pair, diff_message.trading_pair)
