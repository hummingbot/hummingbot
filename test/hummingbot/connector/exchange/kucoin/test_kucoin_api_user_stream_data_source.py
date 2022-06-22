import asyncio
import json
import re
import unittest
from typing import Awaitable, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.kucoin import kucoin_constants as CONSTANTS, kucoin_web_utils as web_utils
from hummingbot.connector.exchange.kucoin.kucoin_api_user_stream_data_source import KucoinAPIUserStreamDataSource
from hummingbot.connector.exchange.kucoin.kucoin_auth import KucoinAuth
from hummingbot.connector.exchange.kucoin.kucoin_exchange import KucoinExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class TestKucoinAPIUserStreamDataSource(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.api_key = "someKey"
        cls.api_passphrase = "somePassPhrase"
        cls.api_secret_key = "someSecretKey"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000
        self.auth = KucoinAuth(
            self.api_key,
            self.api_passphrase,
            self.api_secret_key,
            time_provider=self.mock_time_provider)

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = KucoinExchange(
            client_config_map=client_config_map,
            kucoin_api_key="",
            kucoin_passphrase="",
            kucoin_secret_key="",
            trading_pairs=[],
            trading_required=False)

        self.data_source = KucoinAPIUserStreamDataSource(
            auth=self.auth,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory)

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
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
    def get_listen_key_mock():
        listen_key = {
            "code": "200000",
            "data": {
                "token": "someToken",
                "instanceServers": [
                    {
                        "endpoint": "wss://someEndpoint",
                        "encrypt": True,
                        "protocol": "websocket",
                        "pingInterval": 18000,
                        "pingTimeout": 10000,
                    }
                ]
            }
        }
        return listen_key

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.kucoin.kucoin_web_utils.next_message_id")
    def test_listen_for_user_stream_subscribes_to_orders_and_balances_events(self, mock_api, id_mock, ws_connect_mock):
        id_mock.side_effect = [1, 2]
        url = web_utils.private_rest_url(path_url=CONSTANTS.PRIVATE_WS_DATA_PATH_URL)

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

        output_queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(2, len(sent_subscription_messages))
        expected_orders_subscription = {
            "id": 1,
            "type": "subscribe",
            "topic": "/spotMarket/tradeOrders",
            "privateChannel": True,
            "response": False
        }
        self.assertEqual(expected_orders_subscription, sent_subscription_messages[0])
        expected_balances_subscription = {
            "id": 2,
            "type": "subscribe",
            "topic": "/account/balance",
            "privateChannel": True,
            "response": False
        }
        self.assertEqual(expected_balances_subscription, sent_subscription_messages[1])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to private order changes and balance updates channels..."
        ))

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_get_listen_key_successful_with_user_update_event(self, mock_api, mock_ws):
        url = web_utils.private_rest_url(path_url=CONSTANTS.PRIVATE_WS_DATA_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = self.get_listen_key_mock()
        mock_api.post(regex_url, body=json.dumps(mock_response))

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        order_event = {
            "type": "message",
            "topic": "/spotMarket/tradeOrders",
            "subject": "orderChange",
            "channelType": "private",
            "data": {

                "symbol": "KCS-USDT",
                "orderType": "limit",
                "side": "buy",
                "orderId": "5efab07953bdea00089965d2",
                "type": "open",
                "orderTime": 1593487481683297666,
                "size": "0.1",
                "filledSize": "0",
                "price": "0.937",
                "clientOid": "1593487481000906",
                "remainSize": "0.1",
                "status": "open",
                "ts": 1593487481683297666
            }
        }
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, json.dumps(order_event))

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        msg = self.async_run_with_timeout(msg_queue.get())
        self.assertEqual(order_event, msg)
        mock_ws.return_value.ping.assert_called()

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_does_not_queue_pong_payload(self, mock_api, mock_ws):
        url = web_utils.private_rest_url(path_url=CONSTANTS.PRIVATE_WS_DATA_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = self.get_listen_key_mock()

        mock_pong = {
            "id": "1545910590801",
            "type": "pong"
        }
        mock_api.post(regex_url, body=json.dumps(mock_response))

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, json.dumps(mock_pong))

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    def test_listen_for_user_stream_connection_failed(self, mock_api, sleep_mock, mock_ws):
        url = web_utils.private_rest_url(path_url=CONSTANTS.PRIVATE_WS_DATA_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = self.get_listen_key_mock()
        mock_api.post(regex_url, body=json.dumps(mock_response))

        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = asyncio.CancelledError  # to finish the task execution

        msg_queue = asyncio.Queue()
        try:
            self.async_run_with_timeout(self.data_source.listen_for_user_stream(msg_queue))
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR",
                            "Unexpected error while listening to user stream. Retrying after 5 seconds..."))

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    def test_listen_for_user_stream_iter_message_throws_exception(self, mock_api, sleep_mock, mock_ws):
        url = web_utils.private_rest_url(path_url=CONSTANTS.PRIVATE_WS_DATA_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = self.get_listen_key_mock()
        mock_api.post(regex_url, body=json.dumps(mock_response))

        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.receive.side_effect = Exception("TEST ERROR")
        sleep_mock.side_effect = asyncio.CancelledError  # to finish the task execution

        try:
            self.async_run_with_timeout(self.data_source.listen_for_user_stream(msg_queue))
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds..."))

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.kucoin.kucoin_web_utils.next_message_id")
    @patch("hummingbot.connector.exchange.kucoin.kucoin_api_user_stream_data_source.KucoinAPIUserStreamDataSource"
           "._time")
    def test_listen_for_user_stream_sends_ping_message_before_ping_interval_finishes(
            self,
            mock_api,
            time_mock,
            id_mock,
            ws_connect_mock):

        id_mock.side_effect = [1, 2, 3, 4]
        time_mock.side_effect = [1000, 1100, 1101, 1102]  # Simulate first ping interval is already due
        url = web_utils.private_rest_url(path_url=CONSTANTS.PRIVATE_WS_DATA_PATH_URL)

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

        output_queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        expected_ping_message = {
            "id": 3,
            "type": "ping",
        }
        self.assertEqual(expected_ping_message, sent_messages[-1])
