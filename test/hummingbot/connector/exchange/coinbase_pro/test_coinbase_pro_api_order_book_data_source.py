import asyncio
import json
import unittest
from decimal import Decimal
from typing import Awaitable, Dict, List, Optional
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses

from hummingbot.connector.exchange.coinbase_pro import coinbase_pro_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_api_order_book_data_source import (
    CoinbaseProAPIOrderBookDataSource
)
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_auth import CoinbaseProAuth
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_order_book_tracker_entry import (
    CoinbaseProOrderBookTrackerEntry
)
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_utils import build_coinbase_pro_web_assistant_factory
from hummingbot.core.data_type.order_book import OrderBook
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class CoinbaseProAPIOrderBookDataSourceTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant = NetworkMockingAssistant()
        auth = CoinbaseProAuth(api_key="SomeAPIKey", secret_key="SomeSecretKey", passphrase="SomePassPhrase")
        web_assistants_factory = build_coinbase_pro_web_assistant_factory(auth)
        self.data_source = CoinbaseProAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair], web_assistants_factory=web_assistants_factory
        )
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.log_records = []
        self.async_tasks: List[asyncio.Task] = []

    def tearDown(self) -> None:
        for task in self.async_tasks:
            task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @staticmethod
    def get_products_ticker_response_mock(price: float) -> Dict:
        products_ticker_mock = {
            "trade_id": 86326522,
            "price": str(price),
            "size": "0.00698254",
            "time": "2020-03-20T00:22:57.833897Z",
            "bid": "6265.15",
            "ask": "6267.71",
            "volume": "53602.03940154"
        }
        return products_ticker_mock

    def get_products_response_mock(self, other_pair: str) -> List:
        products_mock = [
            {
                "id": self.trading_pair,
                "base_currency": self.base_asset,
                "quote_currency": self.quote_asset,
                "base_min_size": "0.00100000",
                "base_max_size": "280.00000000",
                "quote_increment": "0.01000000",
                "base_increment": "0.00000001",
                "display_name": f"{self.base_asset}/{self.quote_asset}",
                "min_market_funds": "10",
                "max_market_funds": "1000000",
                "margin_enabled": False,
                "post_only": False,
                "limit_only": False,
                "cancel_only": False,
                "status": "online",
                "status_message": "",
                "auction_mode": True,
            },
            {
                "id": other_pair,
                "base_currency": other_pair.split("-")[0],
                "quote_currency": other_pair.split("-")[1],
                "base_min_size": "0.00100000",
                "base_max_size": "280.00000000",
                "quote_increment": "0.01000000",
                "base_increment": "0.00000001",
                "display_name": other_pair.replace("-", "/"),
                "min_market_funds": "10",
                "max_market_funds": "1000000",
                "margin_enabled": False,
                "post_only": False,
                "limit_only": False,
                "cancel_only": False,
                "status": "online",
                "status_message": "",
                "auction_mode": True,
            }
        ]
        return products_mock

    @staticmethod
    def get_products_book_response_mock(
        bids: Optional[List[List[str]]] = None, asks: Optional[List[List[str]]] = None
    ) -> Dict:
        bids = bids or [["1", "2", "3"]]
        asks = asks or [["4", "5", "6"]]
        products_book_mock = {
            "sequence": 13051505638,
            "bids": bids,
            "asks": asks,
        }
        return products_book_mock

    def get_ws_open_message_mock(self) -> Dict:
        message = {
            "type": "open",
            "time": "2014-11-07T08:19:27.028459Z",
            "product_id": self.trading_pair,
            "sequence": 10,
            "order_id": "d50ec984-77a8-460a-b958-66f114b0de9b",
            "price": "200.2",
            "remaining_size": "1.00",
            "side": "sell"
        }
        return message

    def get_ws_match_message_mock(self) -> Dict:
        message = {
            "type": "match",
            "trade_id": 10,
            "sequence": 50,
            "maker_order_id": "ac928c66-ca53-498f-9c13-a110027a60e8",
            "taker_order_id": "132fb6ae-456b-4654-b4e0-d681ac05cea1",
            "time": "2014-11-07T08:19:27.028459Z",
            "product_id": self.trading_pair,
            "size": "5.23512",
            "price": "400.23",
            "side": "sell"
        }
        return message

    def get_ws_change_message_mock(self) -> Dict:
        message = {
            "type": "change",
            "time": "2014-11-07T08:19:27.028459Z",
            "sequence": 80,
            "order_id": "ac928c66-ca53-498f-9c13-a110027a60e8",
            "product_id": self.trading_pair,
            "new_size": "5.23512",
            "old_size": "12.234412",
            "price": "400.23",
            "side": "sell"
        }
        return message

    def get_ws_done_message_mock(self) -> Dict:
        message = {
            "type": "done",
            "time": "2014-11-07T08:19:27.028459Z",
            "product_id": self.trading_pair,
            "sequence": 10,
            "price": "200.2",
            "order_id": "d50ec984-77a8-460a-b958-66f114b0de9b",
            "reason": "filled",
            "side": "sell",
            "remaining_size": "0"
        }
        return message

    @aioresponses()
    def test_get_last_traded_prices(self, mock_api):
        alt_pair = "BTC-USDT"
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.PRODUCTS_PATH_URL}/{self.trading_pair}/ticker"
        alt_url = f"{CONSTANTS.REST_URL}{CONSTANTS.PRODUCTS_PATH_URL}/{alt_pair}/ticker"
        price = 10.0
        alt_price = 15.0
        resp = self.get_products_ticker_response_mock(price=price)
        alt_resp = self.get_products_ticker_response_mock(price=alt_price)
        mock_api.get(url, body=json.dumps(resp))
        mock_api.get(alt_url, body=json.dumps(alt_resp))

        trading_pairs = [self.trading_pair, alt_pair]
        ret = self.async_run_with_timeout(
            coroutine=CoinbaseProAPIOrderBookDataSource.get_last_traded_prices(trading_pairs)
        )

        self.assertEqual(ret[self.trading_pair], Decimal(resp["price"]))
        self.assertEqual(ret[alt_pair], Decimal(alt_resp["price"]))

    @aioresponses()
    def test_fetch_trading_pairs(self, mock_api):
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.PRODUCTS_PATH_URL}"
        alt_pair = "BTC-USDT"
        resp = self.get_products_response_mock(alt_pair)
        mock_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=CoinbaseProAPIOrderBookDataSource.fetch_trading_pairs())

        self.assertIn(self.trading_pair, ret)
        self.assertIn(alt_pair, ret)

    @aioresponses()
    def test_get_snapshot(self, mock_api):
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.PRODUCTS_PATH_URL}/{self.trading_pair}/book?level=3"
        resp = self.get_products_book_response_mock()
        mock_api.get(url, body=json.dumps(resp))

        rest_assistant = self.ev_loop.run_until_complete(
            build_coinbase_pro_web_assistant_factory().get_rest_assistant()
        )
        ret = self.async_run_with_timeout(
            coroutine=CoinbaseProAPIOrderBookDataSource.get_snapshot(rest_assistant, self.trading_pair)
        )

        self.assertEqual(resp, ret)  # shallow comparison ok

    @aioresponses()
    def test_get_snapshot_raises_on_status_code(self, mock_api):
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.PRODUCTS_PATH_URL}/{self.trading_pair}/book?level=3"
        resp = self.get_products_book_response_mock()
        mock_api.get(url, body=json.dumps(resp), status=401)

        rest_assistant = self.ev_loop.run_until_complete(
            build_coinbase_pro_web_assistant_factory().get_rest_assistant()
        )
        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                coroutine=CoinbaseProAPIOrderBookDataSource.get_snapshot(rest_assistant, self.trading_pair)
            )

    @aioresponses()
    def test_get_new_order_book(self, mock_api):
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.PRODUCTS_PATH_URL}/{self.trading_pair}/book?level=3"
        resp = self.get_products_book_response_mock(bids=[["1", "2", "3"]], asks=[["4", "5", "6"]])
        mock_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))

        self.assertIsInstance(ret, OrderBook)

        bid_entries = list(ret.bid_entries())
        ask_entries = list(ret.ask_entries())

        self.assertEqual(1, len(bid_entries))
        self.assertEqual(1, len(ask_entries))

        bid_entry = bid_entries[0]
        ask_entry = ask_entries[0]

        self.assertEqual(1, bid_entry.price)
        self.assertEqual(4, ask_entry.price)

    @aioresponses()
    def test_get_tracking_pairs(self, mock_api):
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.PRODUCTS_PATH_URL}/{self.trading_pair}/book?level=3"
        resp = self.get_products_book_response_mock(bids=[["1", "2", "3"]])
        mock_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(self.data_source.get_tracking_pairs())

        self.assertEqual(1, len(ret))

        tracker_entry = ret[self.trading_pair]

        self.assertIsInstance(tracker_entry, CoinbaseProOrderBookTrackerEntry)
        self.assertEqual(1, list(tracker_entry.order_book.bid_entries())[0].price)

    @aioresponses()
    def test_get_tracking_pairs_logs_io_error(self, mock_api):
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.PRODUCTS_PATH_URL}/{self.trading_pair}/book?level=3"
        mock_api.get(url, exception=IOError)

        ret = self.async_run_with_timeout(self.data_source.get_tracking_pairs())

        self.assertEqual(0, len(ret))
        self.assertTrue(self._is_logged(
            log_level="NETWORK", message=f"Error getting snapshot for {self.trading_pair}.")
        )

    @aioresponses()
    def test_get_tracking_pairs_logs_other_exceptions(self, mock_api):
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.PRODUCTS_PATH_URL}/{self.trading_pair}/book?level=3"
        mock_api.get(url, exception=RuntimeError)

        ret = self.async_run_with_timeout(self.data_source.get_tracking_pairs())

        self.assertEqual(0, len(ret))
        self.assertTrue(self._is_logged(
            log_level="ERROR", message=f"Error initializing order book for {self.trading_pair}. ")
        )

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_processes_open_message(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        resp = self.get_ws_open_message_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp)
        )
        output_queue = asyncio.Queue()

        t = self.ev_loop.create_task(self.data_source.listen_for_order_book_diffs(self.ev_loop, output_queue))
        self.async_tasks.append(t)

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertFalse(output_queue.empty())

        ob_message = output_queue.get_nowait()

        self.assertEqual(resp, ob_message.content)  # shallow comparison is ok

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_processes_match_message(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        resp = self.get_ws_match_message_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp)
        )
        output_queue = asyncio.Queue()

        t = self.ev_loop.create_task(self.data_source.listen_for_order_book_diffs(self.ev_loop, output_queue))
        self.async_tasks.append(t)

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertFalse(output_queue.empty())

        ob_message = output_queue.get_nowait()

        self.assertEqual(resp, ob_message.content)  # shallow comparison is ok

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_processes_change_message(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        resp = self.get_ws_change_message_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp)
        )
        output_queue = asyncio.Queue()

        t = self.ev_loop.create_task(self.data_source.listen_for_order_book_diffs(self.ev_loop, output_queue))
        self.async_tasks.append(t)

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertFalse(output_queue.empty())

        ob_message = output_queue.get_nowait()

        self.assertEqual(resp, ob_message.content)  # shallow comparison is ok

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_processes_done_message(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        resp = self.get_ws_done_message_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp)
        )
        output_queue = asyncio.Queue()

        t = self.ev_loop.create_task(self.data_source.listen_for_order_book_diffs(self.ev_loop, output_queue))
        self.async_tasks.append(t)

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertFalse(output_queue.empty())

        ob_message = output_queue.get_nowait()

        self.assertEqual(resp, ob_message.content)  # shallow comparison is ok

    @patch(
        "hummingbot.connector.exchange.coinbase_pro"
        ".coinbase_pro_api_order_book_data_source.CoinbaseProAPIOrderBookDataSource._sleep"
    )
    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_raises_on_no_type(self, ws_connect_mock, _):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        resp = {}
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp)
        )
        output_queue = asyncio.Queue()

        t = self.ev_loop.create_task(self.data_source.listen_for_order_book_diffs(self.ev_loop, output_queue))
        self.async_tasks.append(t)

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(
            self._is_logged(log_level="NETWORK", message="Unexpected error with WebSocket connection.")
        )
        self.assertTrue(output_queue.empty())

    @patch(
        "hummingbot.connector.exchange.coinbase_pro"
        ".coinbase_pro_api_order_book_data_source.CoinbaseProAPIOrderBookDataSource._sleep"
    )
    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_raises_on_error_msg(self, ws_connect_mock, _):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        resp = {"type": "error", "message": "some error"}
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp)
        )
        output_queue = asyncio.Queue()

        t = self.ev_loop.create_task(self.data_source.listen_for_order_book_diffs(self.ev_loop, output_queue))
        self.async_tasks.append(t)

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(
            self._is_logged(log_level="NETWORK", message="Unexpected error with WebSocket connection.")
        )
        self.assertTrue(output_queue.empty())

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_ignores_irrelevant_messages(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps({"type": "received"})
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps({"type": "activate"})
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps({"type": "subscriptions"})
        )
        output_queue = asyncio.Queue()

        t = self.ev_loop.create_task(self.data_source.listen_for_order_book_diffs(self.ev_loop, output_queue))
        self.async_tasks.append(t)

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(output_queue.empty())

    @patch(
        "hummingbot.connector.exchange.coinbase_pro"
        ".coinbase_pro_api_order_book_data_source.CoinbaseProAPIOrderBookDataSource._sleep"
    )
    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_raises_on_unrecognized_message(self, ws_connect_mock, _):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        resp = {"type": "some-new-message-type"}
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp)
        )
        output_queue = asyncio.Queue()

        t = self.ev_loop.create_task(self.data_source.listen_for_order_book_diffs(self.ev_loop, output_queue))
        self.async_tasks.append(t)

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(
            self._is_logged(log_level="NETWORK", message="Unexpected error with WebSocket connection.")
        )
        self.assertTrue(output_queue.empty())
