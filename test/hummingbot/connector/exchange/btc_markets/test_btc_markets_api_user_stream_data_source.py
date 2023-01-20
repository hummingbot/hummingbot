import asyncio
import base64
import hashlib
import hmac
import json
import unittest
from typing import Awaitable, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.btc_markets import btc_markets_constants as CONSTANTS
from hummingbot.connector.exchange.btc_markets.btc_markets_api_user_stream_data_source import (
    BtcMarketsAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.btc_markets.btc_markets_auth import BtcMarketsAuth
from hummingbot.connector.exchange.btc_markets.btc_markets_exchange import BtcMarketsExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant


class BtcMarketsAPIUserStreamDataSourceTest(unittest.TestCase):
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
        cls.domain = CONSTANTS.DEFAULT_DOMAIN
        cls.api_key = "someKey"
        cls.api_secret_key = "XXXX"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000

        self.auth = BtcMarketsAuth(
            self.api_key,
            self.api_secret_key,
            time_provider=self.mock_time_provider)

        self.connector = BtcMarketsExchange(
            client_config_map=self.client_config_map,
            btc_markets_api_key="",
            btc_markets_api_secret="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )

        self.connector._web_assistants_factory._auth = self.auth

        self.data_source = BtcMarketsAPIUserStreamDataSource(
            auth=self.auth,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory)

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(
            bidict({self.ex_trading_pair: self.trading_pair}))

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

    def _raise_exception(self, exception_class):
        raise exception_class

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_logs_error_when_login_fails(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        erroneous_login_response = {"messageType": "error", "code": 1, "message": "authentication failed. invalid key"}

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(erroneous_login_response))

        output_queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(0, output_queue.qsize())

        self.assertTrue(self._is_logged(
            "ERROR",
            "Unexpected error while listening to user stream. Retrying after 5 seconds..."
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_does_not_queue_invalid_payload(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        event_with_invalid_messageType = {
            "messageType": "Invalid message type"
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(event_with_invalid_messageType))

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())

    @patch("hummingbot.connector.exchange.btc_markets.btc_markets_auth.BtcMarketsAuth._time")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_subscribe_events(self, ws_connect_mock, auth_time_mock):
        auth_time_mock.side_effect = [1000]
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_orders = {
            "event": "subscribe",
            "topic": CONSTANTS.ORDER_CHANGE_EVENT_TYPE,
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_orders))

        output_queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(1, len(sent_subscription_messages))

        now = int((self.mock_time_provider.time.return_value) * 1e3)
        strToSign = f"/users/self/subscribe\n{now}"
        signature = base64.b64encode(hmac.new(
            base64.b64decode(self.api_secret_key), strToSign.encode("utf8"), digestmod=hashlib.sha512).digest()).decode('utf8')
        auth_subscription = {
            "signature": signature,
            "key": self.api_key,
            "marketIds": [self.ex_trading_pair],
            "timestamp": str(now),
            "messageType": 'subscribe',
            "channels": [CONSTANTS.ORDER_CHANGE_EVENT_TYPE, CONSTANTS.FUND_CHANGE_EVENT_TYPE, CONSTANTS.HEARTBEAT]
        }
        self.assertEqual(auth_subscription, sent_subscription_messages[0])

        self.assertTrue(self._is_logged("INFO", "Subscribed to private account and orders channels..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_does_not_queue_heartbeat_payload(self, mock_ws):

        mock_pong = {
            "messageType": CONSTANTS.HEARTBEAT
        }
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, json.dumps(mock_pong))

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    def test_listen_for_user_stream_connection_failed(self, sleep_mock, mock_ws):
        mock_ws.side_effect = Exception("TEST ERROR")
        sleep_mock.side_effect = asyncio.CancelledError

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        try:
            with self.assertRaises(Exception):
                self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listening_process_canceled_when_cancel_exception_during_initialization(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_user_stream(messages))
            self.ev_loop.run_until_complete(self.listening_task)

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listening_process_canceled_when_cancel_exception_during_authentication(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.receive.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_user_stream(messages))
            self.ev_loop.run_until_complete(self.listening_task)

    def test_subscribe_channels_raises_cancel_exception(self):
        ws_assistant = AsyncMock()
        ws_assistant.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source._subscribe_channels(ws_assistant))
            self.ev_loop.run_until_complete(self.listening_task)

    # @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    # @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    # def test_listening_process_logs_exception_during_events_subscription(self, sleep_mock, mock_ws):
    #     self.connector._set_trading_pair_symbol_map({})

    #     messages = asyncio.Queue()
    #     sleep_mock.side_effect = asyncio.CancelledError
    #     mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
    #     self.mocking_assistant.add_websocket_aiohttp_message(
    #         mock_ws.return_value,
    #         json.dumps({'messageType': 'subscribe'}))

    #     self.listening_task = self.ev_loop.create_task(
    #         self.data_source.listen_for_user_stream(messages))

    #     try:
    #         self.async_run_with_timeout(self.listening_task, timeout=3)
    #     except asyncio.CancelledError:
    #         pass

    #     self.assertTrue(self._is_logged(
    #         "ERROR",
    #         "Unexpected error occurred subscribing to order book trading and delta streams..."))
    #     self.assertTrue(self._is_logged(
    #         "ERROR",
    #         "Unexpected error while listening to user stream. Retrying after 5 seconds..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_order_change_fund_change(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        subscription_result = {
            "messageType": "subscribe",
            "marketIds": [self.trading_pair],
            "channels": [CONSTANTS.ORDER_CHANGE_EVENT_TYPE, CONSTANTS.FUND_CHANGE_EVENT_TYPE, CONSTANTS.HEARTBEAT]
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(subscription_result))

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(asyncio.Queue()))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(1, len(sent_subscription_messages))
        expected_order_change_subscription = {
            "messageType": "subscribe",
            "marketIds": [self.ex_trading_pair],
            "channels": [CONSTANTS.ORDER_CHANGE_EVENT_TYPE, CONSTANTS.FUND_CHANGE_EVENT_TYPE, CONSTANTS.HEARTBEAT]
        }
        self.assertEqual(expected_order_change_subscription["channels"], sent_subscription_messages[0]["channels"])

        self.assertTrue(
            self._is_logged("INFO", "Subscribed to private account and orders channels..."))

    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws, _):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(asyncio.Queue()))
            self.async_run_with_timeout(self.listening_task)

    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = asyncio.CancelledError

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(asyncio.Queue()))

        try:
            with self.assertRaises(Exception):
                self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

    def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            self.listening_task = self.ev_loop.create_task(self.data_source._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred subscribing to private account and orders channels ...")
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_processes_order_event(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        order_event = {
            "orderId": 79003,
            "marketId": 'BTC-AUD',
            "side": 'Bid',
            "type": 'Limit',
            "openVolume": '1',
            "status": 'Placed',
            "triggerStatus": '',
            "trades": [],
            "timestamp": '2019-04-08T20:41:19.339Z',
            "messageType": 'orderChange'
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(order_event))

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(1, msg_queue.qsize())
        order_event_message = msg_queue.get_nowait()
        self.assertEqual(order_event, order_event_message)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_logs_details_for_order_event_with_errors(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        order_event = {
            "messageType": 'error',
            "code": 3,
            "message": 'invalid marketIds'
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(order_event))

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())

        self.assertTrue(self._is_logged("ERROR", "Unexpected error while listening to user stream. Retrying after 5 seconds..."))
