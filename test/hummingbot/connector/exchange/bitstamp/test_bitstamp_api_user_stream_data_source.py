import asyncio
import json
import re
from typing import Awaitable, Optional
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.bitstamp import bitstamp_constants as CONSTANTS, bitstamp_web_utils as web_utils
from hummingbot.connector.exchange.bitstamp.bitstamp_api_user_stream_data_source import BitstampAPIUserStreamDataSource
from hummingbot.connector.exchange.bitstamp.bitstamp_exchange import BitstampExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant


class BitstampUserStreamDataSourceTests(TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = ""

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()
        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = BitstampExchange(
            client_config_map=client_config_map,
            bitstamp_api_key="TEST_API_KEY",
            bitstamp_api_secret="TEST_SECRET",
            trading_pairs=[],
            trading_required=False,
            domain=self.domain,
            time_provider=self.mock_time_provider
        )

        self.data_source = BitstampAPIUserStreamDataSource(
            auth=self.connector.authenticator,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=self.domain
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

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

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _create_return_value_and_unlock_test_with_event(self, value):
        self.resume_test_event.set()
        return value

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _authentication_response(self, user_id: int) -> str:
        message = {
            "token": "some-token",
            "user_id": user_id,
            "valid_sec": 60
        }

        return json.dumps(message)

    def _subscription_response(self, channel: str, user_id: int) -> str:
        private_channel = f"{channel}-{user_id}"
        message = {
            "event": "bts:subscribe",
            "data": {
                "channel": private_channel
            }
        }

        return json.dumps(message)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @aioresponses()
    def test_listening_process_authenticates_and_subscribes_to_events(self, mock_ws, mock_api):
        user_id = 1
        url = web_utils.private_rest_url(CONSTANTS.WEBSOCKET_TOKEN_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=self._authentication_response(user_id))

        self.listening_task = self.ev_loop.create_task(
            self.data_source._subscribe_channels(mock_ws))
        self.ev_loop.run_until_complete(self.listening_task)

        self.assertTrue(
            self._is_logged("INFO", "Subscribed to private account and orders channels...")
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @aioresponses()
    def test_subscribe_channels_raises_cancel_exception(self, mock_ws, mock_api):
        user_id = 1
        url = web_utils.private_rest_url(CONSTANTS.WEBSOCKET_TOKEN_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=self._authentication_response(user_id))

        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source._subscribe_channels(mock_ws))
            self.ev_loop.run_until_complete(self.listening_task)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @aioresponses()
    def test_subscribe_channels_raises_exception_and_logs_error(self, mock_ws, mock_api):
        user_id = 1
        url = web_utils.private_rest_url(CONSTANTS.WEBSOCKET_TOKEN_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=self._authentication_response(user_id), repeat=True)

        mock_ws.send.side_effect = ConnectionError("Test Error")

        with self.assertRaises(ConnectionError, msg="Test Error"):
            self.listening_task = self.ev_loop.create_task(
                self.data_source._subscribe_channels(mock_ws))
            self.ev_loop.run_until_complete(self.listening_task)

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred subscribing to order book trading...")
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @aioresponses()
    def test_listen_for_user_stream_logs_subscribed_message(self, mock_ws, mock_api):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.configure_http_request_mock(mock_api)

        user_id = 1
        url = web_utils.private_rest_url(CONSTANTS.WEBSOCKET_TOKEN_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=self._authentication_response(user_id))

        message_event_subscription_success = {
            "event": "bts:subscription_succeeded",
            "channel": CONSTANTS.WS_PRIVATE_MY_TRADES.format(self.ex_trading_pair, user_id),
            "data": {}
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(message_event_subscription_success))

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())

        self.assertTrue(self._is_logged("INFO", f"Successfully subscribed to '{message_event_subscription_success['channel']}'..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @aioresponses()
    def test_listen_for_user_stream_does_queue_valid_payload(self, mock_ws, mock_api):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.configure_http_request_mock(mock_api)

        user_id = 1
        url = web_utils.private_rest_url(CONSTANTS.WEBSOCKET_TOKEN_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=self._authentication_response(user_id))

        valid_message = {
            'data': {
                'id': 1,
                'amount': '3600.00000000',
                'price': '0.12200',
                'microtimestamp': '1000',
                'fee': '1.3176',
                'order_id': 12345,
                'trade_account_id': 0,
                'side': 'buy'
            },
            'channel': 'private-my_trades_coinalphahbot-1',
            'event': 'trade'
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(valid_message))

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=mock_ws.return_value)

        self.assertEqual(1, msg_queue.qsize())
        self.assertEqual(valid_message, msg_queue.get_nowait())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @aioresponses()
    def test_listen_for_user_stream_does_not_queue_invalid_payload(self, mock_ws, mock_api):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.configure_http_request_mock(mock_api)

        user_id = 1
        url = web_utils.private_rest_url(CONSTANTS.WEBSOCKET_TOKEN_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=self._authentication_response(user_id))

        message_with_unknown_event_type = {
            "event": "unknown-event"
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(message_with_unknown_event_type))

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @aioresponses()
    def test_listen_for_user_stream_reconnects_on_request(self, mock_ws, mock_api):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.configure_http_request_mock(mock_api)

        user_id = 1
        url = web_utils.private_rest_url(CONSTANTS.WEBSOCKET_TOKEN_URL, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=self._authentication_response(user_id), repeat=True)

        reconnect_event = {
            "event": "bts:request_reconnect",
            "channel": "",
            "data": ""
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(reconnect_event))

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())
        self.assertTrue(self._is_logged("WARNING", "The websocket connection was closed (Received request to reconnect. Reconnecting...)"))
