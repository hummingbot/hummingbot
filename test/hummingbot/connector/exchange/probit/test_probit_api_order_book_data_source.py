import asyncio
import json
import re
import unittest
from typing import Optional, Awaitable, Dict, List, Tuple
from unittest.mock import patch, AsyncMock

from aiohttp import WSMsgType
from aioresponses import aioresponses

from hummingbot.connector.exchange.probit.probit_api_order_book_data_source import (
    ProbitAPIOrderBookDataSource
)
from hummingbot.connector.exchange.probit import probit_constants as CONSTANTS
from hummingbot.core.data_type.order_book import OrderBook, OrderBookMessage
from test.hummingbot.connector.network_mocking_assistant import (
    NetworkMockingAssistant
)


class ProbitAPIOrderBookDataSourceTest(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.domain = "com"

    def setUp(self) -> None:
        super().setUp()

        self.ev_loop = asyncio.get_event_loop()

        self.api_key = "someKey"
        self.api_secret = "someSecret"
        self.data_source = ProbitAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair], domain=self.domain
        )
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.log_records = []
        self.mocking_assistant = NetworkMockingAssistant()

        self.async_tasks: List[asyncio.Task] = []

    def tearDown(self) -> None:
        for task in self.async_tasks:
            task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def check_is_logged(self, log_level: str, message: str) -> bool:
        return any(
            record.levelname == log_level and record.getMessage() == message
            for record in self.log_records
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(
            asyncio.wait_for(coroutine, timeout))
        return ret

    def get_ticker_resp_mock(self, last_price: float) -> Dict[str, List[Dict[str, str]]]:
        ticker_resp_mock = {
            "data": [
                {
                    "last": str(last_price),
                    "low": "3235",
                    "high": "3273.8",
                    "change": "-23.4",
                    "base_volume": "0.16690818",
                    "quote_volume": "543.142095541",
                    "market_id": self.trading_pair,
                    "time": "2018-12-17T06:49:08.000Z"
                }
            ]
        }
        return ticker_resp_mock

    @staticmethod
    def get_market_resp_mock(trading_pairs: List[str]) -> Dict[str, List[Dict[str, str]]]:
        market_resp_mock = {
            "data": [
                {
                    "id": trading_pair,
                    "base_currency_id": trading_pair.split("-")[0],
                    "quote_currency_id": trading_pair.split("-")[1],
                    "closed": False,
                } for trading_pair in trading_pairs
            ]
        }
        return market_resp_mock

    def get_order_book_resp_mock(
        self,
        ask_price_quantity_tuples: Optional[List[Tuple[float, float]]] = None,
        bid_price_quantity_tuples: Optional[List[Tuple[float, float]]] = None,
    ) -> Dict[str, List[Dict[str, str]]]:
        data = self.get_order_book_resp_mock_data(
            ask_price_quantity_tuples, bid_price_quantity_tuples
        )
        order_book_resp_mock = {"data": data}
        return order_book_resp_mock

    def get_marketdata_recent_trades_msg_mock(
        self,
        price_quantity_tuples: Optional[List[Tuple[float, float]]] = None,
        snapshot: bool = False,
    ) -> Dict:
        msg_mock = self.get_base_marketdata_mock_msg(snapshot)
        data = self.get_recent_trades_resp_mock_data(price_quantity_tuples)
        msg_mock["recent_trades"] = data
        return msg_mock

    def get_marketdata_order_books_msg_mock(
        self,
        ask_price_quantity_tuples: Optional[List[Tuple[float, float]]] = None,
        bid_price_quantity_tuples: Optional[List[Tuple[float, float]]] = None,
        snapshot: bool = False,
    ):
        msg_mock = self.get_base_marketdata_mock_msg(snapshot)
        data = self.get_order_book_resp_mock_data(
            ask_price_quantity_tuples, bid_price_quantity_tuples
        )
        msg_mock["order_books"] = data
        return msg_mock

    def get_base_marketdata_mock_msg(self, snapshot: bool = False) -> Dict:
        msg_mock = {
            "channel": "marketdata",
            "market_id": self.trading_pair,
            "status": "ok",
            "lag": 0,
            "ticker": {
                "time": "2018-08-17T03:00:43.000Z",
                "last": "0.00004221",
                "low": "0.00003953",
                "high": "0.00004233",
                "change": "0.00000195",
                "base_volume": "119304953.57728445",
                "quote_volume": "4914.391934022046355"
            },
            "reset": snapshot,
        }
        return msg_mock

    @staticmethod
    def get_recent_trades_resp_mock_data(
        price_quantity_tuples: Optional[List[Tuple[float, float]]] = None
    ) -> List[Dict[str, str]]:
        price_quantity_tuples = price_quantity_tuples or []
        trades_data = [
            {
                "price": str(price),
                "quantity": str(quantity),
                "time": "2018-08-17T02:56:17.249Z",
                "side": "buy",
                "tick_direction": "zeroup",
            } for price, quantity in price_quantity_tuples
        ]
        return trades_data

    @staticmethod
    def get_order_book_resp_mock_data(
        ask_price_quantity_tuples: Optional[List[Tuple[float, float]]] = None,
        bid_price_quantity_tuples: Optional[List[Tuple[float, float]]] = None,
    ) -> List[Dict[str, str]]:
        ask_price_quantity_tuples = ask_price_quantity_tuples or []
        bid_price_quantity_tuples = bid_price_quantity_tuples or []
        ask_data = [
            {"side": "sell", "price": str(price), "quantity": str(quantity)}
            for price, quantity in ask_price_quantity_tuples
        ]
        bid_data = [
            {"side": "buy", "price": str(price), "quantity": str(quantity)}
            for price, quantity in bid_price_quantity_tuples
        ]
        data = ask_data + bid_data
        return data

    @aioresponses()
    def test_get_last_traded_prices(self, mocked_api):
        last_price = 3252.4

        url = f"{CONSTANTS.TICKER_URL.format(self.domain)}"
        resp = self.get_ticker_resp_mock(last_price)
        mocked_api.get(url, body=json.dumps(resp))

        res = self.async_run_with_timeout(
            self.data_source.get_last_traded_prices([self.trading_pair], self.domain)
        )

        self.assertIn(self.trading_pair, res)
        self.assertEqual(last_price, res[self.trading_pair])

    @aioresponses()
    def test_fetch_trading_pairs(self, mocked_api):
        other_pair = "BTC-USDT"

        url = f"{CONSTANTS.MARKETS_URL.format(self.domain)}"
        resp = self.get_market_resp_mock(trading_pairs=[self.trading_pair, other_pair])
        mocked_api.get(url, body=json.dumps(resp))

        res = self.async_run_with_timeout(self.data_source.fetch_trading_pairs(self.domain))

        self.assertEqual(2, len(res))
        self.assertIn(self.trading_pair, res)
        self.assertIn(other_pair, res)

    @aioresponses()
    def test_get_order_book_data(self, mocked_api):
        url = f"{CONSTANTS.ORDER_BOOK_URL.format(self.domain)}"
        regex_url = re.compile(f"^{url}")
        resp = self.get_order_book_resp_mock(ask_price_quantity_tuples=[(1, 2), (3, 4)])
        mocked_api.get(regex_url, body=json.dumps(resp))

        res = self.async_run_with_timeout(
            self.data_source.get_order_book_data(self.trading_pair, self.domain)
        )

        self.assertEqual(res, resp)

        res_data = res["data"]

        for d in resp["data"]:
            self.assertIn(d, res_data)

    @aioresponses()
    def test_get_new_order_book(self, mocked_api):
        first_ask_price = 1

        url = f"{CONSTANTS.ORDER_BOOK_URL.format(self.domain)}"
        regex_url = re.compile(f"^{url}")
        resp = self.get_order_book_resp_mock(
            ask_price_quantity_tuples=[(first_ask_price, 2), (3, 4)]
        )
        mocked_api.get(regex_url, body=json.dumps(resp))

        res = self.async_run_with_timeout(
            self.data_source.get_new_order_book(self.trading_pair)
        )

        self.assertIsInstance(res, OrderBook)

        asks = list(res.ask_entries())
        bids = list(res.bid_entries())

        self.assertEqual(0, len(bids))
        self.assertEqual(2, len(asks))
        self.assertEqual(first_ask_price, asks[0].price)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch(
        "hummingbot.connector.exchange.probit.probit_api_order_book_data_source.ProbitAPIOrderBookDataSource._sleep",
        new_callable=AsyncMock,
    )
    def test_listen_for_subscriptions_logs_error_on_closed(self, sleep_mock, ws_connect_mock):
        called_event = asyncio.Event()
        continue_event = asyncio.Event()

        async def close_():
            called_event.set()
            await continue_event.wait()

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.close.side_effect = close_
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, message="", message_type=WSMsgType.CLOSED
        )
        self.async_tasks.append(
            self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
        )

        self.async_run_with_timeout(called_event.wait())

        log_target = (  # from _iter_messages
            "Unexpected error occurred iterating through websocket messages."
        )

        self.assertTrue(self.check_is_logged(log_level="ERROR", message=log_target))

        called_event.clear()
        continue_event.set()

        self.async_run_with_timeout(called_event.wait())

        log_target = (  # from listen_for_subscriptions
            "Unexpected error occurred when listening to order book streams. "
            "Retrying in 5 seconds..."
        )

        self.assertTrue(self.check_is_logged(log_level="ERROR", message=log_target))
        sleep_mock.assert_called_with(5.0)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_order_book_streams(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, message="")
        self.async_tasks.append(
            self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
        )
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_msgs = self.mocking_assistant.json_messages_sent_through_websocket(
            ws_connect_mock.return_value
        )

        self.assertGreaterEqual(len(sent_msgs), 1)

        msg_filters = sent_msgs[0]["filter"]

        self.assertIn(self.data_source.TRADE_FILTER_ID, msg_filters)
        self.assertIn(self.data_source.DIFF_FILTER_ID, msg_filters)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_trades(self, ws_connect_mock):
        trade_price = 1

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        message = self.get_marketdata_recent_trades_msg_mock(
            price_quantity_tuples=[(trade_price, 2)]
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(message)
        )

        self.async_tasks.append(
            self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
        )
        outputs = asyncio.Queue()
        self.async_tasks.append(
            self.ev_loop.create_task(self.data_source.listen_for_trades(self.ev_loop, outputs))
        )

        res = self.async_run_with_timeout(outputs.get())

        self.assertIsInstance(res, OrderBookMessage)
        self.assertEqual(str(trade_price), res.content["price"])

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_trades_ignores_snapshot_msg(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        message = self.get_marketdata_recent_trades_msg_mock(
            price_quantity_tuples=[(1, 2)], snapshot=True  # should be ignored
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(message)
        )
        trade_price = 2
        message = self.get_marketdata_recent_trades_msg_mock(
            price_quantity_tuples=[(trade_price, 2)], snapshot=False
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(message)
        )

        self.async_tasks.append(
            self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
        )
        outputs = asyncio.Queue()
        self.async_tasks.append(
            self.ev_loop.create_task(self.data_source.listen_for_trades(self.ev_loop, outputs))
        )
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        res = self.async_run_with_timeout(outputs.get())

        self.assertEqual(str(trade_price), res.content["price"])

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_generates_snapshot_msg(self, ws_connect_mock):
        first_ask_price = 1

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        message = self.get_marketdata_order_books_msg_mock(
            ask_price_quantity_tuples=[(first_ask_price, 2), (3, 4)], snapshot=True
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(message)
        )

        self.async_tasks.append(
            self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
        )
        outputs = asyncio.Queue()
        self.async_tasks.append(
            self.ev_loop.create_task(self.data_source.listen_for_order_book_diffs(self.ev_loop, outputs))
        )

        res = self.async_run_with_timeout(outputs.get())

        self.assertIsInstance(res, OrderBookMessage)
        self.assertEqual(2, len(res.asks))
        self.assertEqual(0, len(res.bids))
        self.assertEqual(first_ask_price, res.asks[0].price)

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_generates_diff_msg(self, ws_connect_mock):
        ask_price = 1

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        message = self.get_marketdata_order_books_msg_mock(
            ask_price_quantity_tuples=[(ask_price, 2)], snapshot=False
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(message)
        )

        self.async_tasks.append(
            self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
        )
        outputs = asyncio.Queue()
        self.async_tasks.append(
            self.ev_loop.create_task(self.data_source.listen_for_order_book_diffs(self.ev_loop, outputs))
        )

        res = self.async_run_with_timeout(outputs.get())

        self.assertIsInstance(res, OrderBookMessage)
        self.assertEqual(1, len(res.asks))
        self.assertEqual(0, len(res.bids))
        self.assertEqual(ask_price, res.asks[0].price)
