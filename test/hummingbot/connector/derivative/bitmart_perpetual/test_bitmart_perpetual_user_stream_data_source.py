import asyncio
import json
import unittest
from typing import Awaitable, Optional
from unittest.mock import AsyncMock, patch

import hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_constants as CONSTANTS
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.bitmart_perpetual import bitmart_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_auth import BitmartPerpetualAuth
from hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_derivative import BitmartPerpetualDerivative
from hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_user_stream_data_source import (
    BitmartPerpetualUserStreamDataSource,
)
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class BitmartPerpetualUserStreamDataSourceUnitTests(unittest.TestCase):
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
        cls.domain = CONSTANTS.DOMAIN

        cls.api_key = "TEST_API_KEY"
        cls.secret_key = "TEST_SECRET_KEY"
        cls.memo = "TEST_MEMO"
        cls.listen_key = "TEST_LISTEN_KEY"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.emulated_time = 1640001112.223
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = BitmartPerpetualDerivative(
            client_config_map=client_config_map,
            bitmart_perpetual_api_key="",
            bitmart_perpetual_api_secret="",
            domain=self.domain,
            trading_pairs=[])

        self.auth = BitmartPerpetualAuth(api_key=self.api_key,
                                         api_secret=self.secret_key,
                                         memo=self.memo,
                                         time_provider=self)
        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)
        api_factory = web_utils.build_api_factory(auth=self.auth)
        self.data_source = BitmartPerpetualUserStreamDataSource(
            auth=self.auth, domain=self.domain, api_factory=api_factory, connector=self.connector,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mock_done_event = asyncio.Event()
        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _raise_exception(self, exception_class):
        raise exception_class

    def _mock_responses_done_callback(self, *_, **__):
        self.mock_done_event.set()

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _create_return_value_and_unlock_test_with_event(self, value):
        self.resume_test_event.set()
        return value

    def _simulate_user_update_event(self):
        # Order Trade Update
        resp = {
            "group": "futures/order",
            "data": [
                {
                    "action": 3,
                    "order": {
                        "order_id": "220906179895578",
                        "client_order_id": "BM1234",
                        "price": "1",
                        "size": "1000",
                        "symbol": self.ex_trading_pair,
                        "state": 2,
                        "side": 1,
                        "type": "limit",
                        "leverage": "5",
                        "open_type": "isolated",
                        "deal_avg_price": "0",
                        "deal_size": "0",
                        "create_time": 1662368173000,
                        "update_time": 1662368173000,
                        "plan_order_id": "220901412155341",
                        "last_trade": {
                            "lastTradeID": 1247592391,
                            "fillQty": "1",
                            "fillPrice": "25667.2",
                            "fee": "-0.00027",
                            "feeCcy": "USDT"
                        },
                        "trigger_price": "-",
                        "trigger_price_type": "-",
                        "execution_price": "-",
                        "activation_price_type": "-",
                        "activation_price": "-",
                        "callback_rate": "-"
                    }
                }
            ]
        }
        return json.dumps(resp)

    @staticmethod
    def _subscription_response(channel: str):
        message = {
            'action': 'subscribe',
            'group': channel,
            'request': {
                'action': 'subscribe',
                'args': [channel]
            },
            'success': True
        }
        return json.dumps(message)

    @staticmethod
    def _authentication_response(success: bool):
        message = {
            "action": "access",
            "success": success
        }
        return json.dumps(message)

    def time(self):
        # Implemented to emulate a TimeSynchronizer
        return self.emulated_time

    def test_last_recv_time(self):
        # Initial last_recv_time
        self.assertEqual(0, self.data_source.last_recv_time)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listening_process_authenticates_and_subscribes_to_events(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        initial_last_recv_time = self.data_source.last_recv_time

        # Add the authentication response for the websocket
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, self._authentication_response(True))
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            self._subscription_response(CONSTANTS.WS_POSITIONS_CHANNEL))
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            self._subscription_response(CONSTANTS.WS_ORDERS_CHANNEL))
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            self._subscription_response(CONSTANTS.WS_ACCOUNT_CHANNEL))

        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source._listen_for_user_stream_on_url("test_url", messages)
        )
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(
            self._is_logged("INFO", "Subscribed to private account and orders channels test_url...")
        )

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(ws_connect_mock.return_value)
        self.assertEqual(4, len(sent_messages))
        expected_authentication_payload = {
            'action': 'access',
            'args': [
                'TEST_API_KEY',
                '1640001112223',
                '3718d08b91b979cf8b0e4b300734f4edbe42fd91dbca8db2c8f1639a546c37b2',  # noqa: mock
                'web'
            ]
        }
        authentication_request = sent_messages[0]
        self.assertEqual(expected_authentication_payload, authentication_request)
        for i, channel in enumerate([CONSTANTS.WS_POSITIONS_CHANNEL, CONSTANTS.WS_ORDERS_CHANNEL, CONSTANTS.WS_ACCOUNT_CHANNEL], start=1):
            expected_payload = {
                "action": "subscribe",
                "args": [channel]
            }
            self.assertEqual(expected_payload, sent_messages[i])

        self.assertGreater(self.data_source.last_recv_time, initial_last_recv_time)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_authentication_failure(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source._listen_for_user_stream_on_url("test_url", messages))
        self.mocking_assistant.add_websocket_aiohttp_message(
            ws_connect_mock.return_value,
            self._authentication_response(False))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(self._is_logged("ERROR", "Error authenticating the private websocket connection"))
        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream test_url. Retrying after 5 seconds..."
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_does_not_queue_empty_payload(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, self._authentication_response(True)
        )
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, "")

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source._listen_for_user_stream_on_url("test_url", msg_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_connection_failed(self, mock_ws):
        mock_ws.side_effect = lambda *arg, **kwars: self._create_exception_and_unlock_test_with_event(
            Exception("TEST ERROR."))

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source._listen_for_user_stream_on_url("test_url", msg_queue)
        )

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged(
                "ERROR", "Unexpected error while listening to user stream test_url. Retrying after 5 seconds..."
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listening_process_canceled_on_cancel_exception(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(messages))
            self.async_run_with_timeout(self.listening_task)
