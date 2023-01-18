import asyncio
import json
import re
import unittest
from typing import Awaitable, Dict, List
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS
from hummingbot.connector.exchange.gate_io.gate_io_api_order_book_data_source import GateIoAPIOrderBookDataSource
from hummingbot.connector.exchange.gate_io.gate_io_exchange import GateIoExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book import OrderBook, OrderBookMessage


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
        cls.ex_trading_pair = f"{cls.base_asset}_{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.async_tasks: List[asyncio.Task] = []

        self.mocking_assistant = NetworkMockingAssistant()
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = GateIoExchange(
            client_config_map=client_config_map,
            gate_io_api_key="",
            gate_io_secret_key="",
            trading_pairs=[],
            trading_required=False)

        self.data_source = GateIoAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory)

        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        for task in self.async_tasks:
            task.cancel()
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
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
                "currency_pair": self.ex_trading_pair,
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
                "s": self.ex_trading_pair,
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
                "s": self.ex_trading_pair,
                "U": 48791820,
                "u": 48791830,
                "b": [bids],
                "a": [asks],
            }
        }
        return ob_snapshot

    @aioresponses()
    def test_get_order_book_data_raises(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_BOOK_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = ""
        for _ in range(CONSTANTS.API_MAX_RETRIES):
            mock_api.get(regex_url, body=json.dumps(resp), status=500)

        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                coroutine=self.data_source.get_new_order_book(self.trading_pair)
            )

    @aioresponses()
    def test_get_order_book_data(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_BOOK_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_order_book_data_mock()
        mock_api.get(regex_url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(
            coroutine=self.data_source.get_new_order_book(self.trading_pair)
        )

        bid_entries = list(ret.bid_entries())
        ask_entries = list(ret.ask_entries())
        self.assertEqual(1, len(bid_entries))
        self.assertEqual(float(resp["bids"][0][0]), bid_entries[0].price)
        self.assertEqual(float(resp["bids"][0][1]), bid_entries[0].amount)
        self.assertEqual(int(resp["id"]), bid_entries[0].update_id)
        self.assertEqual(1, len(ask_entries))
        self.assertEqual(float(resp["asks"][0][0]), ask_entries[0].price)
        self.assertEqual(float(resp["asks"][0][1]), ask_entries[0].amount)
        self.assertEqual(int(resp["id"]), ask_entries[0].update_id)

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
        resp1 = {"time": 1632223851, "channel": CONSTANTS.TRADES_ENDPOINT_NAME, "event": "subscribe", "result": {"status": "success"}}
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp1)
        )
        resp2 = {
            "time": 1632223851, "channel": CONSTANTS.TRADES_ENDPOINT_NAME, "event": "unsubscribe", "result": {"status": "success"}
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value, json.dumps(resp2)
        )

        output_queue = asyncio.Queue()
        t = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
        self.async_tasks.append(t)
        t = self.ev_loop.create_task(self.data_source.listen_for_trades(self.ev_loop, output_queue))
        self.async_tasks.append(t)
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(output_queue.empty())
        self.assertFalse(
            self._is_logged(
                "ERROR",
                f"Unexpected error while parsing ws trades message {resp1}."
            )
        )
        self.assertFalse(
            self._is_logged(
                "ERROR",
                f"Unexpected error while parsing ws trades message {resp2}."
            )
        )

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch(
        "hummingbot.connector.exchange.gate_io.gate_io_api_order_book_data_source.GateIoAPIOrderBookDataSource._sleep")
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
                "Unexpected error when processing public trade updates from exchange"
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
                "Unexpected error when processing public order book updates from exchange"
            ))

    @patch("aiohttp.client.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_snapshot(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        asks = ["19080.24", "0.1638"]
        bids = ["19079.55", "0.0195"]
        resp = self.get_order_book_diff_mock(asks=asks, bids=bids)
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
        self.assertEqual(asks, msg.content["asks"][0], msg=f"{msg}")

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
    @patch(
        "hummingbot.connector.exchange.gate_io.gate_io_api_order_book_data_source.GateIoAPIOrderBookDataSource._sleep",
        new_callable=AsyncMock)
    def test_listen_for_order_book_snapshots_logs_error_when_exception_happens(
            self,
            mock_api,
            sleep_mock):
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
                "ERROR",
                f"Unexpected error fetching order book snapshot for {self.trading_pair}."
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
