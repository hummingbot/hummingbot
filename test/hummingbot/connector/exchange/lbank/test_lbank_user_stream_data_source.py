import asyncio
import json
import unittest
from typing import Awaitable, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses.core import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.lbank import lbank_constants as CONSTANTS, lbank_web_utils as web_utils
from hummingbot.connector.exchange.lbank.lbank_api_user_stream_data_source import LbankAPIUserStreamDataSource
from hummingbot.connector.exchange.lbank.lbank_auth import LbankAuth
from hummingbot.connector.exchange.lbank.lbank_exchange import LbankExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class LbankUserStreamDataSourceUnitTests(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset.lower()}_{cls.quote_asset.lower()}"

        cls.listen_key = "TEST_LISTEN_KEY"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000

        self.time_synchronizer = MagicMock()
        self.time_synchronizer.time.return_value = 1640001112.223

        self.auth = LbankAuth(api_key="TEST_API_KEY", secret_key="TEST_SECRET", auth_method="HmacSHA256")

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = LbankExchange(
            client_config_map=client_config_map,
            lbank_api_key="",
            lbank_secret_key="",
            lbank_auth_method="HmacSHA256",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

        self.connector._web_assistants_factory._auth = self.auth

        self.data_source = LbankAPIUserStreamDataSource(
            auth=self.auth,
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            trading_pairs=[self.trading_pair],
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _raise_exception(self, exception_class):
        raise exception_class

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @aioresponses()
    def test_get_listening_key_successful(self, mock_api):
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_CREATE_LISTENING_KEY_PATH_URL)

        response = {"result": True, "data": self.listen_key}

        mock_api.post(url, body=json.dumps(response))
        listening_key = self.async_run_with_timeout(self.data_source._get_listening_key())

        self.assertEqual(self.listen_key, listening_key)

    @aioresponses()
    def test_get_listening_key_unsuccessful(self, mock_api):
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_CREATE_LISTENING_KEY_PATH_URL)

        response = {"result": False, "data": None, "error_code": 10007}

        mock_api.post(url, body=json.dumps(response))

        with self.assertRaises(ValueError):
            self.async_run_with_timeout(self.data_source._get_listening_key())

        expected_error = f"Unable to fetch listening key. Error Code: 10007 - Invalid signature. Response: {response}"
        self.assertTrue(self._is_logged("ERROR", expected_error))

    @aioresponses()
    def test_get_listening_key_raises_exception(self, mock_api):
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_CREATE_LISTENING_KEY_PATH_URL)

        mock_api.post(url, exception=Exception("Test Error"))
        with self.assertRaises(Exception):
            self.async_run_with_timeout(self.data_source._get_listening_key())

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error fetching user stream listening key. Error: Test Error")
        )

    @aioresponses()
    def test_extend_listening_key_successful(self, mock_api):
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_REFRESH_LISTENING_KEY_PATH_URL)

        response = {"result": True, "data": True}

        mock_api.post(url, body=json.dumps(response))

        self.data_source._current_listening_key = "TEST_LISTENING_KEY"
        extension_status: bool = self.async_run_with_timeout(self.data_source._extend_listening_key())

        self.assertTrue(extension_status)

    @aioresponses()
    def test_extend_listening_key_raises_cancel(self, mock_api):
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_REFRESH_LISTENING_KEY_PATH_URL)

        mock_api.post(url, exception=asyncio.CancelledError)

        self.data_source._current_listening_key = self.listen_key
        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source._extend_listening_key())

    @aioresponses()
    def test_extend_listening_key_logs_exception(self, mock_api):
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_REFRESH_LISTENING_KEY_PATH_URL)

        mock_api.post(url, exception=Exception("Test Error"))

        self.data_source._current_listening_key = self.listen_key
        extension_status: bool = self.async_run_with_timeout(self.data_source._extend_listening_key())

        self.assertFalse(extension_status)
        self.assertTrue(
            self._is_logged(
                "ERROR", "Unexpected error occurred extending validity of listening key... Error: Test Error"
            )
        )

    @patch(
        "hummingbot.connector.exchange.lbank.lbank_api_user_stream_data_source.LbankAPIUserStreamDataSource"
        "._get_ws_assistant",
        new_callable=AsyncMock,
    )
    def test_handles_ping_message_raises_cancel(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        ws_connect_mock.return_value.send.side_effect = asyncio.CancelledError

        ping_message = {"ping": "someRandomString", "action": "ping"}

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source._handle_ping_message(ping_message))

    @patch(
        "hummingbot.connector.exchange.lbank.lbank_api_user_stream_data_source.LbankAPIUserStreamDataSource"
        "._get_ws_assistant",
        new_callable=AsyncMock,
    )
    def test_handles_ping_message_logs_exception(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        ws_connect_mock.return_value.send.side_effect = Exception("Test Error")

        ping_message = {"ping": "someRandomString", "action": "ping"}

        with self.assertRaisesRegex(Exception, "Test Error"):
            self.async_run_with_timeout(self.data_source._handle_ping_message(ping_message))

        self.assertTrue(
            self._is_logged(
                "ERROR", "Unexpected error occurred sending ping request to user stream connection... Error: Test Error"
            )
        )

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_subscribes_to_orders_and_balances_events(self, mock_api, ws_connect_mock):
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_CREATE_LISTENING_KEY_PATH_URL)
        create_key_response = {"result": True, "data": self.listen_key}
        mock_api.post(url, body=json.dumps(create_key_response))

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        # Use ping message to resume test
        ping_message = {"ping": "someRandomString", "action": "ping"}
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(ping_message)
        )

        output_queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_json_message = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )

        self.assertEqual(3, len(sent_json_message))
        expected_subscribe_asset_payload = {
            "action": "subscribe",
            "subscribe": "assetUpdate",
            "subscribeKey": self.listen_key,
        }
        self.assertEqual(expected_subscribe_asset_payload, sent_json_message[0])
        expected_subscribe_orders_payload = {
            "action": "subscribe",
            "subscribe": "orderUpdate",
            "subscribeKey": self.listen_key,
            "pair": self.ex_trading_pair,
        }
        self.assertEqual(expected_subscribe_orders_payload, sent_json_message[1])
        self.assertTrue(self._is_logged("INFO", "Subscribed to user assets and order websocket channels..."))

    @aioresponses()
    @patch(
        "hummingbot.connector.exchange.lbank.lbank_api_user_stream_data_source.LbankAPIUserStreamDataSource"
        "._ping_request_interval")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_sends_ping_request(self, mock_api, ws_connect_mock, ping_interval_mock):
        # Change interval configuration to force the timeout
        ping_interval_mock.side_effect = [-1, asyncio.CancelledError]

        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_CREATE_LISTENING_KEY_PATH_URL)
        create_key_response = {"result": True, "data": self.listen_key}
        mock_api.post(url, body=json.dumps(create_key_response))

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        output_queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))
        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        sent_json_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )

        self.assertEqual("ping", sent_json_messages[2]["action"])  # Note first 2 msg are subscription requests
        self.assertIn("ping", sent_json_messages[2])

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_queues_account_events(self, mock_api, ws_connect_mock):
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_CREATE_LISTENING_KEY_PATH_URL)
        create_listening_response = {"result": True, "data": self.listen_key}
        mock_api.post(url, body=json.dumps(create_listening_response))

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        # Asset Update
        asset_update = {
            "data": {
                "asset": "50",
                "assetCode": self.quote_asset,
                "free": "26",
                "freeze": "24",
                "time": 1655785565477,
                "type": "ORDER_CREATE",
            },
            "SERVER": "V2",
            "type": "assetUpdate",
            "TS": "2022-06-21T12:26:05.478",
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(asset_update)
        )

        # Order Update
        order_update = {
            "SERVER": "V2",
            "orderUpdate": {
                "accAmt": "0",
                "amount": "0",
                "avgPrice": "0",
                "customerID": "",
                "orderAmt": "0.0012",
                "orderPrice": "20000",
                "orderStatus": 0,
                "price": "20000",
                "remainAmt": "24",
                "role": "taker",
                "symbol": self.ex_trading_pair,
                "type": "buy",
                "updateTime": 1655785565476,
                "uuid": "someUuid",
                "volumePrice": "0",
            },
            "type": "orderUpdate",
            "pair": self.ex_trading_pair,
            "TS": "2022-06-21T12:26:05.479",
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(order_update)
        )

        # NOTE: Ping message should not be queued
        ping_message = {"ping": "someRandomString", "action": "ping"}
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=json.dumps(ping_message)
        )

        output_queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(2, output_queue.qsize())
        self.assertEqual(asset_update, output_queue.get_nowait())
        self.assertEqual(order_update, output_queue.get_nowait())

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_manage_listening_key_task_loop_sets_initialized_event(self, mock_api, ws_connect_mock):
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_CREATE_LISTENING_KEY_PATH_URL)
        create_listening_response = {"result": True, "data": self.listen_key}

        mock_api.post(url, body=json.dumps(create_listening_response))
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.listening_task = self.ev_loop.create_task(self.data_source._manage_listening_key_task_loop())

        self.async_run_with_timeout(self.data_source._listen_key_initialized_event.wait())

    @aioresponses()
    def test_manage_listening_key_task_loop_raises_cancel(self, mock_api):
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_CREATE_LISTENING_KEY_PATH_URL)
        mock_api.post(url, exception=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source._manage_listening_key_task_loop())

        self.assertIsNone(self.data_source._current_listening_key)
        self.assertFalse(self.data_source._listen_key_initialized_event.is_set())

    @aioresponses()
    def test_manage_listening_key_task_loop_logs_exception(self, mock_api):
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_CREATE_LISTENING_KEY_PATH_URL)
        mock_api.post(url, exception=Exception("Test Error"))

        self.async_run_with_timeout(self.data_source._manage_listening_key_task_loop())

        self.assertIsNone(self.data_source._current_listening_key)
        self.assertFalse(self.data_source._listen_key_initialized_event.is_set())

        self.assertTrue(
            self._is_logged(
                "ERROR", "Unexpected error occurred maintaining listening key. Error: Test Error"
            )
        )

    @aioresponses()
    @patch("hummingbot.connector.exchange.lbank.lbank_api_user_stream_data_source.LbankAPIUserStreamDataSource._time")
    def test_manage_listening_key_ping_successful(self, mock_api, mock_time):
        mock_time.return_value = 0
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_CREATE_LISTENING_KEY_PATH_URL)
        create_key_response = {"result": True, "data": self.listen_key}
        mock_api.post(url, body=json.dumps(create_key_response))

        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_REFRESH_LISTENING_KEY_PATH_URL)
        extend_key_response = {"result": True}
        mock_api.post(url, body=json.dumps(extend_key_response))

        # Raise exception to resume test
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_REFRESH_LISTENING_KEY_PATH_URL)
        mock_api.post(url, exception=asyncio.CancelledError)

        with patch("hummingbot.connector.exchange.lbank.lbank_constants.LBANK_LISTEN_KEY_KEEP_ALIVE_INTERVAL", 0):
            with self.assertRaises(asyncio.CancelledError):
                self.async_run_with_timeout(self.data_source._manage_listening_key_task_loop())

        self.assertTrue(self._is_logged("INFO", f"Refreshed listening key: {self.listen_key}"))

    @aioresponses()
    @patch("hummingbot.connector.exchange.lbank.lbank_api_user_stream_data_source.LbankAPIUserStreamDataSource._time")
    def test_manage_listening_key_ping_unsuccessful(self, mock_api, mock_time):
        mock_time.return_value = 0
        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_CREATE_LISTENING_KEY_PATH_URL)
        create_key_response = {"result": True, "data": self.listen_key}
        mock_api.post(url, body=json.dumps(create_key_response))

        url = web_utils.private_rest_url(path_url=CONSTANTS.LBANK_REFRESH_LISTENING_KEY_PATH_URL)
        extend_key_response = {"result": False}
        mock_api.post(url, body=json.dumps(extend_key_response))

        with patch("hummingbot.connector.exchange.lbank.lbank_constants.LBANK_LISTEN_KEY_KEEP_ALIVE_INTERVAL", 0):
            self.async_run_with_timeout(self.data_source._manage_listening_key_task_loop())

        self.assertTrue(self._is_logged("ERROR", "Unable to extend validity of listening key..."))
