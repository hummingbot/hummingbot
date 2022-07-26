import asyncio
import json
import re
import unittest
from typing import Awaitable, Dict
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.kucoin import kucoin_constants as CONSTANTS, kucoin_web_utils as web_utils
from hummingbot.connector.exchange.kucoin.kucoin_api_order_book_data_source import KucoinAPIOrderBookDataSource
from hummingbot.connector.exchange.kucoin.kucoin_exchange import KucoinExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book_message import OrderBookMessage


class TestKucoinAPIOrderBookDataSource(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ws_endpoint = "ws://someEndpoint"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.async_task = None

        self.mocking_assistant = NetworkMockingAssistant()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = KucoinExchange(
            client_config_map=client_config_map,
            kucoin_api_key="",
            kucoin_passphrase="",
            kucoin_secret_key="",
            trading_pairs=[],
            trading_required=False)

        self.ob_data_source = KucoinAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory)

        self._original_full_order_book_reset_time = self.ob_data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.ob_data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.ob_data_source.logger().setLevel(1)
        self.ob_data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(bidict({self.trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        self.async_task and self.async_task.cancel()
        self.ob_data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
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
    def get_snapshot_mock() -> Dict:
        snapshot = {
            "code": "200000",
            "data": {
                "time": 1630556205455,
                "sequence": "1630556205456",
                "bids": [["0.3003", "4146.5645"]],
                "asks": [["0.3004", "1553.6412"]]
            }
        }
        return snapshot

    @aioresponses()
    def test_get_new_order_book(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_NO_AUTH_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_snapshot_mock()
        mock_api.get(regex_url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.ob_data_source.get_new_order_book(self.trading_pair))
        bid_entries = list(ret.bid_entries())
        ask_entries = list(ret.ask_entries())
        self.assertEqual(1, len(bid_entries))
        self.assertEqual(0.3003, bid_entries[0].price)
        self.assertEqual(4146.5645, bid_entries[0].amount)
        self.assertEqual(int(resp["data"]["sequence"]), bid_entries[0].update_id)
        self.assertEqual(1, len(ask_entries))
        self.assertEqual(0.3004, ask_entries[0].price)
        self.assertEqual(1553.6412, ask_entries[0].amount)
        self.assertEqual(int(resp["data"]["sequence"]), ask_entries[0].update_id)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.kucoin.kucoin_web_utils.next_message_id")
    def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs(self, mock_api, id_mock, ws_connect_mock):
        id_mock.side_effect = [1, 2]
        url = web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_WS_DATA_PATH_URL)

        resp = {
            "code": "200000",
            "data": {
                "instanceServers": [
                    {
                        "endpoint": "wss://test.url/endpoint",
                        "protocol": "websocket",
                        "encrypt": True,
                        "pingInterval": 50000,
                        "pingTimeout": 10000
                    }
                ],
                "token": "testToken"
            }
        }
        mock_api.post(url, body=json.dumps(resp))

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_trades = {
            "type": "ack",
            "id": 1
        }
        result_subscribe_diffs = {
            "type": "ack",
            "id": 2
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trades))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_diffs))

        self.listening_task = self.ev_loop.create_task(self.ob_data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(2, len(sent_subscription_messages))
        expected_trade_subscription = {
            "id": 1,
            "type": "subscribe",
            "topic": f"/market/match:{self.trading_pair}",
            "privateChannel": False,
            "response": False
        }
        self.assertEqual(expected_trade_subscription, sent_subscription_messages[0])
        expected_diff_subscription = {
            "id": 2,
            "type": "subscribe",
            "topic": f"/market/level2:{self.trading_pair}",
            "privateChannel": False,
            "response": False
        }
        self.assertEqual(expected_diff_subscription, sent_subscription_messages[1])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to public order book and trade channels..."
        ))

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.kucoin.kucoin_web_utils.next_message_id")
    @patch("hummingbot.connector.exchange.kucoin.kucoin_api_order_book_data_source.KucoinAPIOrderBookDataSource._time")
    def test_listen_for_subscriptions_sends_ping_message_before_ping_interval_finishes(
            self,
            mock_api,
            time_mock,
            id_mock,
            ws_connect_mock):

        id_mock.side_effect = [1, 2, 3, 4]
        time_mock.side_effect = [1000, 1100, 1101, 1102]  # Simulate first ping interval is already due
        url = web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_WS_DATA_PATH_URL)

        resp = {
            "code": "200000",
            "data": {
                "instanceServers": [
                    {
                        "endpoint": "wss://test.url/endpoint",
                        "protocol": "websocket",
                        "encrypt": True,
                        "pingInterval": 20000,
                        "pingTimeout": 10000
                    }
                ],
                "token": "testToken"
            }
        }
        mock_api.post(url, body=json.dumps(resp))

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_trades = {
            "type": "ack",
            "id": 1
        }
        result_subscribe_diffs = {
            "type": "ack",
            "id": 2
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trades))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_diffs))

        self.listening_task = self.ev_loop.create_task(self.ob_data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        expected_ping_message = {
            "id": 3,
            "type": "ping",
        }
        self.assertEqual(expected_ping_message, sent_messages[-1])

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    def test_listen_for_subscriptions_raises_cancel_exception(self, mock_api, _, ws_connect_mock):
        url = web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_WS_DATA_PATH_URL)

        resp = {
            "code": "200000",
            "data": {
                "instanceServers": [
                    {
                        "endpoint": "wss://test.url/endpoint",
                        "protocol": "websocket",
                        "encrypt": True,
                        "pingInterval": 50000,
                        "pingTimeout": 10000
                    }
                ],
                "token": "testToken"
            }
        }
        mock_api.post(url, body=json.dumps(resp))

        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.ob_data_source.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    def test_listen_for_subscriptions_logs_exception_details(self, mock_api, sleep_mock, ws_connect_mock):
        url = web_utils.public_rest_url(path_url=CONSTANTS.PUBLIC_WS_DATA_PATH_URL)

        resp = {
            "code": "200000",
            "data": {
                "instanceServers": [
                    {
                        "endpoint": "wss://test.url/endpoint",
                        "protocol": "websocket",
                        "encrypt": True,
                        "pingInterval": 50000,
                        "pingTimeout": 10000
                    }
                ],
                "token": "testToken"
            }
        }
        mock_api.post(url, body=json.dumps(resp))

        sleep_mock.side_effect = asyncio.CancelledError
        ws_connect_mock.side_effect = Exception("TEST ERROR.")

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.ob_data_source.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."))

    def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.ob_data_source._message_queue[self.ob_data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.ob_data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_trades_logs_exception(self):
        incomplete_resp = {
            "type": "message",
            "topic": f"/market/match:{self.trading_pair}",
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.ob_data_source._message_queue[self.ob_data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.ob_data_source.listen_for_trades(self.ev_loop, msg_queue)
        )

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public trade updates from exchange"))

    def test_listen_for_trades_successful(self):
        mock_queue = AsyncMock()
        trade_event = {
            "type": "message",
            "topic": f"/market/match:{self.trading_pair}",
            "subject": "trade.l3match",
            "data": {
                "sequence": "1545896669145",
                "type": "match",
                "symbol": self.trading_pair,
                "side": "buy",
                "price": "0.08200000000000000000",
                "size": "0.01022222000000000000",
                "tradeId": "5c24c5da03aa673885cd67aa",
                "takerOrderId": "5c24c5d903aa6772d55b371e",
                "makerOrderId": "5c2187d003aa677bd09d5c93",
                "time": "1545913818099033203"
            }
        }
        mock_queue.get.side_effect = [trade_event, asyncio.CancelledError()]
        self.ob_data_source._message_queue[self.ob_data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.ob_data_source.listen_for_trades(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertTrue(trade_event["data"]["tradeId"], msg.trade_id)

    def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.ob_data_source._message_queue[self.ob_data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.ob_data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_order_book_diffs_logs_exception(self):
        incomplete_resp = {
            "type": "message",
            "topic": f"/market/level2:{self.trading_pair}",
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.ob_data_source._message_queue[self.ob_data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.ob_data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
        )

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public order book updates from exchange"))

    def test_listen_for_order_book_diffs_successful(self):
        mock_queue = AsyncMock()
        diff_event = {
            "type": "message",
            "topic": "/market/level2:BTC-USDT",
            "subject": "trade.l2update",
            "data": {

                "sequenceStart": 1545896669105,
                "sequenceEnd": 1545896669106,
                "symbol": f"{self.trading_pair}",
                "changes": {

                    "asks": [["6", "1", "1545896669105"]],
                    "bids": [["4", "1", "1545896669106"]]
                }
            }
        }
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.ob_data_source._message_queue[self.ob_data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            self.listening_task = self.ev_loop.create_task(
                self.ob_data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
        except asyncio.CancelledError:
            pass

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertTrue(diff_event["data"]["sequenceEnd"], msg.update_id)

    @aioresponses()
    def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_NO_AUTH_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(
                self.ob_data_source.listen_for_order_book_snapshots(self.ev_loop, asyncio.Queue())
            )

    @aioresponses()
    @patch("hummingbot.connector.exchange.kucoin.kucoin_api_order_book_data_source"
           ".KucoinAPIOrderBookDataSource._sleep")
    def test_listen_for_order_book_snapshots_log_exception(self, mock_api, sleep_mock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        sleep_mock.side_effect = asyncio.CancelledError

        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_NO_AUTH_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=Exception)

        try:
            self.async_run_with_timeout(self.ob_data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue))
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}."))

    @aioresponses()
    def test_listen_for_order_book_snapshots_successful(self, mock_api, ):
        msg_queue: asyncio.Queue = asyncio.Queue()
        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_NO_AUTH_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        snapshot_data = {
            "code": "200000",
            "data": {
                "sequence": "3262786978",
                "time": 1550653727731,
                "bids": [["6500.12", "0.45054140"],
                         ["6500.11", "0.45054140"]],
                "asks": [["6500.16", "0.57753524"],
                         ["6500.15", "0.57753524"]]
            }
        }

        mock_api.get(regex_url, body=json.dumps(snapshot_data))

        self.listening_task = self.ev_loop.create_task(
            self.ob_data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(int(snapshot_data["data"]["sequence"]), msg.update_id)
