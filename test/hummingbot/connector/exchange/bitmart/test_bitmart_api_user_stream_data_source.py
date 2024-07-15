import asyncio
import json
import unittest
from typing import Awaitable, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import WSMsgType
from bidict import bidict

import hummingbot.connector.exchange.bitmart.bitmart_constants as CONSTANTS
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.bitmart import bitmart_utils
from hummingbot.connector.exchange.bitmart.bitmart_api_user_stream_data_source import BitmartAPIUserStreamDataSource
from hummingbot.connector.exchange.bitmart.bitmart_auth import BitmartAuth
from hummingbot.connector.exchange.bitmart.bitmart_exchange import BitmartExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant


class BitmartAPIUserStreamDataSourceTests(unittest.TestCase):
    # the level is required to receive logs from the data source logger
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
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

        self.time_synchronizer = MagicMock()
        self.time_synchronizer.time.return_value = 1640001112.223

        self.auth = BitmartAuth(
            api_key="test_api_key",
            secret_key="test_secret_key",
            memo="test_memo",
            time_provider=self.time_synchronizer)

        self.connector = BitmartExchange(
            client_config_map=self.client_config_map,
            bitmart_api_key="test_api_key",
            bitmart_secret_key="test_secret_key",
            bitmart_memo="test_memo",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        self.connector._web_assistants_factory._auth = self.auth

        self.data_source = BitmartAPIUserStreamDataSource(
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

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _raise_exception(self, exception_class):
        raise exception_class

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_subscribes_to_orders_events(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        successful_login_response = {"event": "login"}
        result_subscribe_orders = {
            "event": "subscribe",
            "topic": CONSTANTS.PRIVATE_ORDER_PROGRESS_CHANNEL_NAME,
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(successful_login_response))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_orders))

        output_queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(2, len(sent_messages))
        expected_login = {
            "op": "login",
            "args": [
                "test_api_key",
                str(int(self.time_synchronizer.time() * 1e3)),
                "f0f176c799346a7730c9c237a09d14742971f3ab59848dde75ef1ac95b04c4e5"]  # noqa: mock
        }
        self.assertEqual(expected_login, sent_messages[0])
        expected_orders_subscription = {
            "op": "subscribe",
            "args": [f"{CONSTANTS.PRIVATE_ORDER_PROGRESS_CHANNEL_NAME}:{self.ex_trading_pair}"]
        }
        self.assertEqual(expected_orders_subscription, sent_messages[1])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to private account and orders channels..."
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_logs_error_when_login_fails(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        erroneous_login_response = {"event": "login", "errorCode": "4001"}

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(erroneous_login_response))

        output_queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(self._is_logged(
            "ERROR",
            "Error authenticating the private websocket connection"
        ))

        self.assertTrue(self._is_logged(
            "ERROR",
            "Unexpected error while listening to user stream. Retrying after 5 seconds..."
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_does_not_queue_invalid_payload(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        successful_login_response = {"event": "login"}
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(successful_login_response))

        event_without_data = {
            "table": CONSTANTS.PRIVATE_ORDER_PROGRESS_CHANNEL_NAME
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(event_without_data))

        event_without_table = {
            "data": [
                {
                    "symbol": self.ex_trading_pair,
                    "side": "buy",
                    "type": "market",
                    "notional": "",
                    "size": "1.0000000000",
                    "ms_t": "1609926028000",
                    "price": "46100.0000000000",
                    "filled_notional": "46100.0000000000",
                    "filled_size": "1.0000000000",
                    "margin_trading": "0",
                    "state": "4",
                    "order_id": "2147857398",
                    "order_type": "0",
                    "last_fill_time": "1609926039226",
                    "last_fill_price": "46100.00000",
                    "last_fill_count": "1.00000",
                    "exec_type": "M",
                    "detail_id": "256348632",
                    "client_order_id": "order4872191"
                }
            ],
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(event_without_table))

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
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR",
                            "Unexpected error while listening to user stream. Retrying after 5 seconds..."))

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

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    def test_listening_process_logs_exception_during_events_subscription(self, sleep_mock, mock_ws):
        # This is to force a KeyError in _subscribe_channels
        self.connector._set_trading_pair_symbol_map(bidict({'some-pair': 'some-pair'}))

        messages = asyncio.Queue()
        sleep_mock.side_effect = asyncio.CancelledError
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        # Add the authentication response for the websocket
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value,
            json.dumps({"event": "login"}))

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(messages))

        try:
            self.async_run_with_timeout(self.listening_task, timeout=3)
        except asyncio.CancelledError:
            pass

        self.assertTrue(self._is_logged(
            "ERROR",
            "Unexpected error occurred subscribing to order book trading and delta streams..."))
        self.assertTrue(self._is_logged(
            "ERROR",
            "Unexpected error while listening to user stream. Retrying after 5 seconds..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_processes_order_event(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        successful_login_response = {"event": "login"}
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(successful_login_response))

        order_event = {
            "data": [
                {
                    "symbol": self.ex_trading_pair,
                    "side": "buy",
                    "type": "market",
                    "notional": "",
                    "size": "1.0000000000",
                    "ms_t": "1609926028000",
                    "price": "46100.0000000000",
                    "filled_notional": "46100.0000000000",
                    "filled_size": "1.0000000000",
                    "margin_trading": "0",
                    "state": "4",
                    "order_id": "2147857398",
                    "order_type": "0",
                    "last_fill_time": "1609926039226",
                    "last_fill_price": "46100.00000",
                    "last_fill_count": "1.00000",
                    "exec_type": "M",
                    "detail_id": "256348632",
                    "client_order_id": "order4872191"
                }
            ],
            "table": CONSTANTS.PRIVATE_ORDER_PROGRESS_CHANNEL_NAME
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
    def test_listen_for_user_stream_processes_compressed_order_event(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        successful_login_response = {"event": "login"}
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(successful_login_response))

        order_event = {
            "data": [
                {
                    "symbol": self.ex_trading_pair,
                    "side": "buy",
                    "type": "market",
                    "notional": "",
                    "size": "1.0000000000",
                    "ms_t": "1609926028000",
                    "price": "46100.0000000000",
                    "filled_notional": "46100.0000000000",
                    "filled_size": "1.0000000000",
                    "margin_trading": "0",
                    "state": "4",
                    "order_id": "2147857398",
                    "order_type": "0",
                    "last_fill_time": "1609926039226",
                    "last_fill_price": "46100.00000",
                    "last_fill_count": "1.00000",
                    "exec_type": "M",
                    "detail_id": "256348632",
                    "client_order_id": "order4872191"
                }
            ],
            "table": CONSTANTS.PRIVATE_ORDER_PROGRESS_CHANNEL_NAME
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=bitmart_utils.compress_ws_message(json.dumps(order_event)),
            message_type=WSMsgType.BINARY)

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
        successful_login_response = {"event": "login"}
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(successful_login_response))

        order_event = {
            "errorCode": "4001",
            "errorMessage": "Error",
            "data": [
                {
                    "symbol": self.ex_trading_pair,
                    "side": "buy",
                    "type": "market",
                    "notional": "",
                    "size": "1.0000000000",
                    "ms_t": "1609926028000",
                    "price": "46100.0000000000",
                    "filled_notional": "46100.0000000000",
                    "filled_size": "1.0000000000",
                    "margin_trading": "0",
                    "state": "4",
                    "order_id": "2147857398",
                    "order_type": "0",
                    "last_fill_time": "1609926039226",
                    "last_fill_price": "46100.00000",
                    "last_fill_count": "1.00000",
                    "exec_type": "M",
                    "detail_id": "256348632",
                    "client_order_id": "order4872191"
                }
            ],
            "table": CONSTANTS.PRIVATE_ORDER_PROGRESS_CHANNEL_NAME
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

        self.assertTrue(self._is_logged(
            "ERROR",
            "Unexpected error while listening to user stream. Retrying after 5 seconds..."
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_logs_details_for_invalid_event_message(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        successful_login_response = {"event": "login"}
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(successful_login_response))

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message="invalid message content")

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())

        self.assertTrue(self._is_logged(
            "WARNING",
            "Invalid event message received through the order book data source connection (invalid message content)"
        ))
