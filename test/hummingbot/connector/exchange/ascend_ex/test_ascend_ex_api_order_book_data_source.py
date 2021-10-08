import asyncio
import json
import re

from aioresponses import aioresponses
from unittest import TestCase
from unittest.mock import patch

from hummingbot.connector.exchange.ascend_ex.ascend_ex_api_order_book_data_source import AscendExAPIOrderBookDataSource
from hummingbot.connector.exchange.ascend_ex import ascend_ex_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class AscendExAPIOrderBookDataSourceTests(TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    def setUp(self) -> None:
        super().setUp()

        self.ev_loop = asyncio.get_event_loop()

        self.base_asset = "BTC"
        self.quote_asset = "USDT"
        self.trading_pair = f"{self.base_asset}-{self.quote_asset}"

        self.log_records = []
        self.listening_task = None

        self.shared_client = None
        self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)

        self.data_source = AscendExAPIOrderBookDataSource(shared_client=self.shared_client, throttler=self.throttler, trading_pairs=[self.trading_pair])
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)
        self.data_source._trading_pair_symbol_map = {}

        self.mocking_assistant = NetworkMockingAssistant()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _raise_exception(self, exception_class):
        raise exception_class

    @aioresponses()
    def test_fetch_trading_pairs(self, api_mock):
        mock_response = {
            "code": 0,
            "data": [{
                "symbol": "ASD/USDT",
                "open": "0.06777",
                "close": "0.06809",
                "high": "0.06899",
                "low": "0.06708",
                "volume": "19823722",
                "ask": [
                    "0.0681",
                    "43641"
                ],
                "bid": [
                    "0.0676",
                    "443"
                ]
            }, {
                "symbol": "BTC/USDT",
                "open": "0.06777",
                "close": "0.06809",
                "high": "0.06899",
                "low": "0.06708",
                "volume": "19823722",
                "ask": [
                    "0.0681",
                    "43641"
                ],
                "bid": [
                    "0.0676",
                    "443"
                ]
            }, {
                "symbol": "ETH/USDT",
                "open": "0.06777",
                "close": "0.06809",
                "high": "0.06899",
                "low": "0.06708",
                "volume": "19823722",
                "ask": [
                    "0.0681",
                    "43641"
                ],
                "bid": [
                    "0.0676",
                    "443"
                ]
            }]
        }

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.TICKER_PATH_URL}"
        api_mock.get(url, body=json.dumps(mock_response))

        trading_pairs = self.ev_loop.run_until_complete(self.data_source.fetch_trading_pairs(client=self.data_source._shared_client, throttler=self.throttler))

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
                    {
                        "seqnum": 144115191800016553,
                        "p": "0.06762",
                        "q": "400",
                        "ts": 1573165890854,
                        "bm": False
                    },
                    {
                        "seqnum": 144115191800070421,
                        "p": "0.06797",
                        "q": "341",
                        "ts": 1573166037845,
                        "bm": True
                    }
                ]
            }
        }

        self.data_source._trading_pairs = ["BTC-USDT"]

        url = re.escape(f"{CONSTANTS.REST_URL}/{CONSTANTS.TRADES_PATH_URL}?symbol=")
        regex_url = re.compile(f"^{url}")
        api_mock.get(regex_url, body=json.dumps(mock_response))

        results = self.ev_loop.run_until_complete(self.data_source.get_last_traded_prices(trading_pairs=[self.trading_pair], client=self.data_source._shared_client, throttler=self.throttler))

        self.assertEqual(results[self.trading_pair], float(mock_response["data"]["data"][1]["p"]))

    @patch("aiohttp.client.ClientSession.ws_connect")
    def test_listen_for_subscriptions_registers_to_orders_trades_and_instruments(self, ws_connect_mock):
        self.data_source._trading_pairs = ["BTC-USDT"]

        websocket_mock = self.mocking_assistant.create_websocket_mock()
        websocket_mock.receive.side_effect = asyncio.CancelledError()
        ws_connect_mock.return_value = websocket_mock

        queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_trades(ev_loop=self.ev_loop, output=queue))
        try:
            self.ev_loop.run_until_complete(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_order_book_diffs(ev_loop=self.ev_loop, output=queue))
        try:
            self.ev_loop.run_until_complete(self.listening_task)
        except asyncio.CancelledError:
            pass

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(ws_connect_mock.return_value)

        self.assertEqual(2, len(sent_messages))
        expected_trades_subscription = {'op': 'sub', 'ch': 'trades:BTC/USDT'}
        expected_depth_subscription = {'op': 'sub', 'ch': 'depth:BTC/USDT'}
        self.assertEqual(expected_trades_subscription, sent_messages[0])
        self.assertEqual(expected_depth_subscription, sent_messages[1])

    @patch("aiohttp.client.ClientSession.ws_connect")
    def test_listen_for_order_book_diff_raises_cancel_exceptions(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_order_book_diffs(ev_loop=self.ev_loop, output=queue))

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task.cancel()
            self.ev_loop.run_until_complete(self.listening_task)

    @patch("aiohttp.client.ClientSession.ws_connect")
    def test_listen_for_order_book_diff_raises_cancel_exception_when_canceled_during_ws_connection(self, ws_connect_mock):
        ws_connect_mock.side_effect = asyncio.CancelledError()

        queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_order_book_diffs(ev_loop=self.ev_loop, output=queue))

        with self.assertRaises(asyncio.CancelledError):
            self.ev_loop.run_until_complete(self.listening_task)

    @patch('hummingbot.connector.exchange.ascend_ex.ascend_ex_api_order_book_data_source.AscendExAPIOrderBookDataSource._sleep')
    @patch("aiohttp.client.ClientSession.ws_connect")
    def test_listen_for_order_book_diff_ws_connection_exception_details_are_logged(self, ws_connect_mock, sleep_mock):
        ws_connect_mock.side_effect = Exception
        sleep_mock.side_effect = asyncio.CancelledError

        queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_order_book_diffs(ev_loop=self.ev_loop, output=queue))

        with self.assertRaises(asyncio.CancelledError):
            self.ev_loop.run_until_complete(self.listening_task)

        self.assertTrue(self._is_logged("ERROR", "Unexpected error with WebSocket connection. Retrying after 30 seconds..."))

    @patch('hummingbot.connector.exchange.ascend_ex.ascend_ex_api_order_book_data_source.AscendExAPIOrderBookDataSource._sleep')
    @patch("aiohttp.client.ClientSession.ws_connect")
    def test_listen_for_order_book_diff_logs_exceptions_details(self, ws_connect_mock, sleep_mock):
        ws_connect_mock.side_effect = Exception
        sleep_mock.side_effect = asyncio.CancelledError

        sync_queue = asyncio.Queue()

        self.data_source._trading_pairs = ["BTC-USDT"]
        websocket_mock = self.mocking_assistant.create_websocket_mock()
        websocket_mock.receive.side_effect = Exception()
        websocket_mock.close.side_effect = lambda: sync_queue.put_nowait(1)
        ws_connect_mock.return_value = websocket_mock

        queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_order_book_diffs(ev_loop=self.ev_loop, output=queue))

        with self.assertRaises(asyncio.CancelledError):
            self.ev_loop.run_until_complete(self.listening_task)

        self.assertTrue(self._is_logged("ERROR", "Unexpected error with WebSocket connection. Retrying after 30 seconds..."))

    @patch("aiohttp.client.ClientSession.ws_connect")
    async def test_listen_for_trades(self, ws_connect_mock):
        # Add trade event message be processed
        mock_response = {
            "m": "trades",
            "symbol": "BTC/USDT",
            "data": [
                {
                    "seqnum": 144115191800016553,
                    "p": "0.06762",
                    "q": "400",
                    "ts": 1573165890854,
                    "bm": False
                },
                {
                    "seqnum": 144115191800070421,
                    "p": "0.06797",
                    "q": "341",
                    "ts": 1573166037845,
                    "bm": True
                }
            ]
        }

        self.data_source._trading_pairs = ["BTC-USDT"]
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        trades_queue = asyncio.Queue()

        task = self.ev_loop.create_task(self.data_source.listen_for_trades(ev_loop=self.ev_loop, output=trades_queue))

        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(mock_response))

        first_trade = self.ev_loop.run_until_complete(trades_queue.get())
        second_trade = self.ev_loop.run_until_complete(trades_queue.get())

        try:
            task.cancel()
            self.ev_loop.run_until_complete(task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass

        self.assertTrue(trades_queue.empty())
        self.assertEqual(1573165890854, first_trade.timestamp)
        self.assertEqual(1573166037845, second_trade.timestamp)

    @patch("aiohttp.client.ClientSession.ws_connect")
    def test_listen_for_trades_raises_cancel_exceptions(self, ws_connect_mock):
        trades_queue = asyncio.Queue()
        task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(ev_loop=self.ev_loop, output=trades_queue))

        with self.assertRaises(asyncio.CancelledError):
            task.cancel()
            self.ev_loop.run_until_complete(task)

    @patch("aiohttp.client.ClientSession.ws_connect")
    async def test_listen_for_trades_logs_exceptions_details(self, ws_connect_mock):
        sync_queue = asyncio.Queue()

        self.data_source._trading_pairs = ["BTC-USDT"]
        websocket_mock = self.mocking_assistant.create_websocket_mock()
        websocket_mock.receive.side_effect = Exception()
        websocket_mock.close.side_effect = lambda: sync_queue.put_nowait(1)
        ws_connect_mock.return_value = websocket_mock

        queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_trades(ev_loop=self.ev_loop, output=queue))

        self.assertTrue(self._is_logged("ERROR", "Unexpected error with WebSocket connection. Retrying after 30 seconds..."))

    @aioresponses()
    def test_listen_for_order_book_snapshot_event(self, api_mock):
        mock_response = {
            "code": 0,
            "data": {
                "m": "depth-snapshot",
                "symbol": "ASD/USDT",
                "data": {
                    "seqnum": 5068757,
                    "ts": 1573165838976,
                    "asks": [
                        [
                            "0.06848",
                            "4084.2"
                        ],
                        [
                            "0.0696",
                            "15890.6"
                        ]
                    ],
                    "bids": [
                        [
                            "0.06703",
                            "13500"
                        ],
                        [
                            "0.06615",
                            "24036.9"
                        ]
                    ]
                }
            }
        }

        self.data_source._trading_pairs = ["BTC-USDT"]

        # Add trade event message be processed
        url = re.escape(f"{CONSTANTS.REST_URL}/{CONSTANTS.DEPTH_PATH_URL}?symbol=")
        regex_url = re.compile(f"^{url}")
        api_mock.get(regex_url, body=json.dumps(mock_response))

        order_book_messages = asyncio.Queue()

        task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(ev_loop=self.ev_loop, output=order_book_messages))

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

    @patch("aiohttp.client.ClientSession.ws_connect")
    def test_listen_for_order_book_diff_event(self, ws_connect_mock):
        mock_response = {
            "m": "depth",
            "symbol": "ASD/USDT",
            "data": {
                "ts": 1573069021376,
                "seqnum": 2097965,
                "asks": [
                    [
                        "0.06844",
                        "10760"
                    ]
                ],
                "bids": [
                    [
                        "0.06777",
                        "562.4"
                    ],
                    [
                        "0.05",
                        "221760.6"
                    ]
                ]
            }
        }

        self.data_source._trading_pairs = ["BTC-USD"]
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        # Add a response
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(mock_response))

        order_book_messages = asyncio.Queue()

        task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(ev_loop=self.ev_loop, output=order_book_messages))

        order_book_message = self.ev_loop.run_until_complete(order_book_messages.get())

        try:
            task.cancel()
            self.ev_loop.run_until_complete(task)
        except asyncio.CancelledError:
            # The exception will happen when cancelling the task
            pass

        self.assertTrue(order_book_messages.empty())
        self.assertEqual(1573069021376, order_book_message.update_id)
        self.assertEqual(1573069021376, order_book_message.timestamp)
        self.assertEqual(0.06777, order_book_message.bids[0].price)
        self.assertEqual(0.05, order_book_message.bids[1].price)
        self.assertEqual(0.06844, order_book_message.asks[0].price)

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
                    "asks": [
                        [
                            "0.06848",
                            "4084.2"
                        ],
                        [
                            "0.0696",
                            "15890.6"
                        ]
                    ],
                    "bids": [
                        [
                            "0.06703",
                            "13500"
                        ],
                        [
                            "0.06615",
                            "24036.9"
                        ]
                    ]
                }
            }
        }

        self.data_source._trading_pairs = ["BTC-USDT"]

        # path_url = ascend_ex_utils.rest_api_path_for_endpoint(CONSTANTS.ORDER_BOOK_ENDPOINT, self.trading_pair)
        url = re.escape(f"{CONSTANTS.REST_URL}/{CONSTANTS.DEPTH_PATH_URL}?symbol=")
        regex_url = re.compile(f"^{url}")
        api_mock.get(regex_url, body=json.dumps(mock_response))

        self.listening_task = self.ev_loop.create_task(
            self.data_source.get_new_order_book(self.trading_pair))
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
