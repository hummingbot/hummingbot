import asyncio
import json
import re
import unittest
from decimal import Decimal
from typing import Awaitable, Dict, List
from unittest.mock import patch, AsyncMock

from aioresponses import aioresponses

from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS
from hummingbot.connector.exchange.gate_io.gate_io_api_order_book_data_source import GateIoAPIOrderBookDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook, OrderBookMessage
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class TestGateIoAPIOrderBookDataSource(unittest.TestCase):
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
        self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        api_factory = WebAssistantsFactory()
        self.data_source = GateIoAPIOrderBookDataSource(
            self.throttler, trading_pairs=[self.trading_pair], api_factory=api_factory
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

    def get_last_trade_instance_data_mock(self) -> List:
        last_trade_instance_data = [
            {
                "currency_pair": f"{self.base_asset}_{self.quote_asset}",
                "last": "0.2959",
                "lowest_ask": "0.295918",
                "highest_bid": "0.295898",
                "change_percentage": "-1.72",
                "base_volume": "78497066.828007",
                "quote_volume": "23432064.936692",
                "high_24h": "0.309372",
                "low_24h": "0.286827",
            }
        ]
        return last_trade_instance_data

    @staticmethod
    def get_order_book_data_mock() -> Dict:
        order_book_data = {
            "id": 1890172054,
            "current": 1630644717528,
            "update": 1630644716786,
            "asks": [
                ["0.298705", "5020"]
            ],
            "bids": [
                ["0.298642", "2703.17"]
            ]
        }
        return order_book_data

    def get_trade_data_mock(self) -> Dict:
        trade_data = {
            "time": 1606292218,
            "channel": "spot.trades",
            "event": "update",
            "result": {
                "id": 309143071,
                "create_time": 1606292218,
                "create_time_ms": "1606292218213.4578",
                "side": "sell",
                "currency_pair": f"{self.base_asset}_{self.quote_asset}",
                "amount": "16.4700000000",
                "price": "0.4705000000"
            }
        }
        return trade_data

    def get_order_book_update_mock(self) -> Dict:
        ob_update = {
            "time": 1606294781,
            "channel": "spot.order_book_update",
            "event": "update",
            "result": {
                "t": 1606294781123,
                "e": "depthUpdate",
                "E": 1606294781,
                "s": f"{self.base_asset}_{self.quote_asset}",
                "U": 48776301,
                "u": 48776306,
                "b": [
                    [
                        "19137.74",
                        "0.0001"
                    ],
                ],
                "a": [
                    [
                        "19137.75",
                        "0.6135"
                    ]
                ]
            }
        }
        return ob_update

    def get_order_book_diff_mock(self, asks: List[str], bids: List[str]) -> Dict:
        ob_snapshot = {
            "time": 1606295412,
            "channel": "spot.order_book_update",
            "event": "update",
            "result": {
                "t": 1606295412123,
                "e": "depthUpdate",
                "E": 1606295412,
                "s": f"{self.base_asset}_{self.quote_asset}",
                "U": 48791820,
                "u": 48791830,
                "b": [bids],
                "a": [asks],
            }
        }
        return ob_snapshot

    @aioresponses()
    def test_get_last_trade_instance(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.TICKER_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_last_trade_instance_data_mock()
        mock_api.get(regex_url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(
            coroutine=GateIoAPIOrderBookDataSource.get_last_traded_prices(trading_pairs=[self.trading_pair])
        )

        self.assertEqual(ret[self.trading_pair], Decimal(resp[0]["last"]))

    @aioresponses()
    def test_fetch_trading_pairs(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.SYMBOL_PATH_URL}"
        resp = [
            {
                "id": f"{self.base_asset}_{self.quote_asset}"
            },
            {
                "id": "SOME_PAIR"
            }
        ]
        mock_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=GateIoAPIOrderBookDataSource.fetch_trading_pairs())

        self.assertTrue(self.trading_pair in ret)
        self.assertTrue("SOME-PAIR" in ret)

    @patch("hummingbot.connector.exchange.gate_io.gate_io_utils.retry_sleep_time")
    @aioresponses()
    def test_get_order_book_data_raises(self, retry_sleep_time_mock, mock_api):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_BOOK_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = ""
        for _ in range(CONSTANTS.API_MAX_RETRIES):
            mock_api.get(regex_url, body=json.dumps(resp), status=500)

        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                coroutine=GateIoAPIOrderBookDataSource.get_order_book_data(self.trading_pair)
            )

    @aioresponses()
    def test_get_order_book_data(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_BOOK_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_order_book_data_mock()
        mock_api.get(regex_url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(
            coroutine=GateIoAPIOrderBookDataSource.get_order_book_data(self.trading_pair)
        )

        self.assertEqual(resp, ret)  # shallow comparison is ok

    @aioresponses()
    def test_get_new_order_book(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_BOOK_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_order_book_data_mock()
        mock_api.get(regex_url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.data_source.get_new_order_book(self.trading_pair))

        self.assertTrue(isinstance(ret, OrderBook))

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_trades(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        resp = self.get_trade_data_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp)
        )
        output_queue = asyncio.Queue()

        t = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
        self.async_tasks.append(t)
        t = self.ev_loop.create_task(self.data_source.listen_for_trades(self.ev_loop, output_queue))
        self.async_tasks.append(t)
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(websocket_mock=ws_connect_mock.return_value)

        self.assertTrue(not output_queue.empty())
        self.assertTrue(isinstance(output_queue.get_nowait(), OrderBookMessage))

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_trades_skips_subscribe_unsubscribe_messages(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        resp = {"time": 1632223851, "channel": "spot.usertrades", "event": "subscribe", "result": {"status": "success"}}
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp)
        )
        resp = {
            "time": 1632223851, "channel": "spot.usertrades", "event": "unsubscribe", "result": {"status": "success"}
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp)
        )

        output_queue = asyncio.Queue()
        t = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
        self.async_tasks.append(t)
        t = self.ev_loop.create_task(self.data_source.listen_for_trades(self.ev_loop, output_queue))
        self.async_tasks.append(t)
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(output_queue.empty())

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.gate_io.gate_io_api_order_book_data_source.GateIoAPIOrderBookDataSource._sleep")
    def test_listen_for_trades_logs_error_when_exception_happens(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        incomplete_response = {
            "time": 1606292218,
            "channel": "spot.trades",
            "event": "update",
            "result": {
                "id": 309143071,
                "currency_pair": f"{self.base_asset}_{self.quote_asset}",
            }
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(incomplete_response)
        )
        output_queue = asyncio.Queue()

        t = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
        self.async_tasks.append(t)
        t = self.ev_loop.create_task(self.data_source.listen_for_trades(self.ev_loop, output_queue))
        self.async_tasks.append(t)
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(websocket_mock=ws_connect_mock.return_value)

        self.assertTrue(
            self._is_logged(
                "ERROR",
                f"Unexpected error while parsing ws trades message {incomplete_response}."
            ))

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_update(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        resp = self.get_order_book_update_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp)
        )
        output_queue = asyncio.Queue()

        t = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
        self.async_tasks.append(t)
        t = self.ev_loop.create_task(self.data_source.listen_for_order_book_diffs(self.ev_loop, output_queue))
        self.async_tasks.append(t)
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(websocket_mock=ws_connect_mock.return_value)

        self.assertTrue(not output_queue.empty())
        self.assertTrue(isinstance(output_queue.get_nowait(), OrderBookMessage))

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch(
        "hummingbot.connector.exchange.gate_io.gate_io_api_order_book_data_source.GateIoAPIOrderBookDataSource._sleep",
        new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_update_logs_error_when_exception_happens(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        incomplete_response = {
            "time": 1606294781,
            "channel": "spot.order_book_update",
            "event": "update",
            "result": {}
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(incomplete_response)
        )
        output_queue = asyncio.Queue()

        t = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
        self.async_tasks.append(t)
        t = self.ev_loop.create_task(self.data_source.listen_for_order_book_diffs(self.ev_loop, output_queue))
        self.async_tasks.append(t)
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(websocket_mock=ws_connect_mock.return_value)

        self.assertTrue(
            self._is_logged(
                "ERROR",
                f"Unexpected error while parsing ws order book message {incomplete_response}."
            ))

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_snapshot(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        asks = ["19080.24", "0.1638"]
        resp = self.get_order_book_diff_mock(asks=asks, bids=["19079.55", "0.0195"])
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp)
        )
        output_queue = asyncio.Queue()

        t = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
        self.async_tasks.append(t)
        t = self.ev_loop.create_task(self.data_source.listen_for_order_book_diffs(self.ev_loop, output_queue))
        self.async_tasks.append(t)
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(websocket_mock=ws_connect_mock.return_value)

        self.assertTrue(not output_queue.empty())

        msg = output_queue.get_nowait()

        self.assertTrue(isinstance(msg, OrderBookMessage))
        self.assertEqual(asks, msg.content["a"][0])

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_snapshot_skips_subscribe_unsubscribe_messages(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        resp = {"time": 1632223851, "channel": "spot.usertrades", "event": "subscribe", "result": {"status": "success"}}
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp)
        )
        resp = {
            "time": 1632223851, "channel": "spot.usertrades", "event": "unsubscribe", "result": {"status": "success"}
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp)
        )

        output_queue = asyncio.Queue()
        t = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
        self.async_tasks.append(t)
        t = self.ev_loop.create_task(self.data_source.listen_for_order_book_diffs(self.ev_loop, output_queue))
        self.async_tasks.append(t)
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(output_queue.empty())

    @aioresponses()
    def test_listen_for_order_book_snapshots(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_BOOK_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_order_book_data_mock()
        mock_api.get(regex_url, body=json.dumps(resp))
        output_queue = asyncio.Queue()

        t = self.ev_loop.create_task(self.data_source.listen_for_order_book_snapshots(self.ev_loop, output_queue))
        self.async_tasks.append(t)
        ret = self.async_run_with_timeout(coroutine=output_queue.get())

        self.assertTrue(isinstance(ret, OrderBookMessage))

    @aioresponses()
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    @patch(
        "hummingbot.connector.exchange.gate_io.gate_io_api_order_book_data_source.GateIoAPIOrderBookDataSource._sleep",
        new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.gate_io.gate_io_utils._sleep", new_callable=AsyncMock)
    def test_listen_for_order_book_snapshots_logs_error_when_exception_happens(
            self,
            mock_api,
            utils_sleep,
            sleep_mock,
            _):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_BOOK_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, exception=Exception("Test Error"))
        output_queue = asyncio.Queue()
        sleep_mock.side_effect = asyncio.CancelledError

        t = self.ev_loop.create_task(self.data_source.listen_for_order_book_snapshots(self.ev_loop, output_queue))
        self.async_tasks.append(t)

        try:
            self.async_run_with_timeout(t)
        except asyncio.CancelledError:
            # Ignore the CancelledError raised by the mocked _sleep
            pass

        self.assertTrue(
            self._is_logged(
                "NETWORK",
                "Unexpected error with WebSocket connection."
            )
        )

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch(
        "hummingbot.connector.exchange.gate_io.gate_io_api_order_book_data_source.GateIoAPIOrderBookDataSource._sleep",
        new_callable=AsyncMock)
    def test_listen_for_subscriptions_logs_error_when_exception_happens(self, sleep_mock, ws_connect_mock):
        # ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.side_effect = Exception("Test Error")
        sleep_mock.side_effect = asyncio.CancelledError

        t = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
        self.async_tasks.append(t)

        try:
            self.async_run_with_timeout(t)
        except asyncio.CancelledError:
            # Ignore the CancelledError raised by the mocked _sleep
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."
            ))
