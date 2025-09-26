import asyncio
import json
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch

from bidict import bidict

import hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_constants as CONSTANTS
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_api_user_stream_data_source import (
    BitgetPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_auth import BitgetPerpetualAuth
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_derivative import BitgetPerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer


class BitgetPerpetualUserStreamDataSourceTests(IsolatedAsyncioWrapperTestCase):
    """Test case for BitgetPerpetualUserStreamDataSource."""

    level: int = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset: str = "BTC"
        cls.quote_asset: str = "USDT"
        cls.trading_pair: str = f"{cls.base_asset}-{cls.quote_asset}"
        cls.exchange_trading_pair: str = f"{cls.base_asset}{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.log_records: List[Any] = []
        self.listening_task: Optional[asyncio.Task] = None

        auth = BitgetPerpetualAuth(
            api_key="test_api_key",
            secret_key="test_secret_key",
            passphrase="test_passphrase",
            time_provider=TimeSynchronizer()
        )
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = BitgetPerpetualDerivative(
            client_config_map,
            bitget_perpetual_api_key="test_api_key",
            bitget_perpetual_secret_key="test_secret_key",
            bitget_perpetual_passphrase="test_passphrase",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        self.data_source = BitgetPerpetualUserStreamDataSource(
            auth=auth,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(
            bidict({
                self.exchange_trading_pair: self.trading_pair
            })
        )

    async def asyncSetUp(self) -> None:
        self.mocking_assistant: NetworkMockingAssistant = NetworkMockingAssistant()
        self.resume_test_event: asyncio.Event = asyncio.Event()

    def tearDown(self) -> None:
        if self.listening_task:
            self.listening_task.cancel()
        super().tearDown()

    def handle(self, record: Any) -> None:
        """
        Handle logging records by appending them to the log_records list.

        :param record: The log record to be handled.
        """
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        """
        Check if a specific message was logged with the given log level.

        :param log_level: The log level to check (e.g., "INFO", "ERROR").
        :param message: The message to check for in the logs.
        :return: True if the message was logged with the specified level, False otherwise.
        """
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def ws_login_event_mock_response(self) -> Dict[str, Any]:
        """
        Create a mock WebSocket response for login events.

        :return: A dictionary containing the mock login event response data.
        """
        return {
            "event": "login",
            "code": "0",
            "msg": ""
        }

    def ws_error_event_mock_response(self) -> Dict[str, Any]:
        """
        Create a mock WebSocket response for error events.

        :return: A dictionary containing the mock error event response data.
        """
        return {
            "event": "error",
            "code": "30005",
            "msg": "Invalid request"
        }

    def ws_subscribed_mock_response(self, channel: str) -> Dict[str, Any]:
        """
        Create a mock WebSocket response for subscription events.

        :param channel: The WebSocket channel to subscribe to.
        :return: A dictionary containing the mock subscription event response data.
        """
        return {
            "event": "subscribe",
            "arg": {
                "instType": CONSTANTS.USDT_PRODUCT_TYPE,
                "channel": channel,
                "coin": "default"
            }
        }

    def _create_exception_and_unlock_test_with_event(self, exception_class: Exception) -> None:
        """
        Raise an exception and unlock the test by setting the resume_test_event.

        :param exception: The exception to raise.
        """
        self.resume_test_event.set()

        raise exception_class

    def raise_test_exception(self, *args, **kwargs) -> None:
        """
        Raise the specified exception.

        :param exception_class: The exception class to raise.
        """

        self._create_exception_and_unlock_test_with_event(Exception("Test Error"))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listening_process_authenticates_and_subscribes_to_events(
        self,
        mock_ws: AsyncMock
    ) -> None:
        """
        Test that the listening process authenticates and subscribes to events correctly.

        :param mock_ws: Mocked WebSocket connection.
        """
        messages: asyncio.Queue = asyncio.Queue()
        initial_last_recv_time: float = self.data_source.last_recv_time
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_login_event_mock_response())
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_subscribed_mock_response(CONSTANTS.WS_POSITIONS_ENDPOINT))
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_subscribed_mock_response(CONSTANTS.WS_ORDERS_ENDPOINT))
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_subscribed_mock_response(CONSTANTS.WS_ACCOUNT_ENDPOINT))
        )

        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_user_stream(messages)
        )
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            mock_ws.return_value
        )
        authentication_request: Dict[str, Any] = sent_messages[0]
        subscription_request: Dict[str, Any] = sent_messages[1]
        expected_payload = {
            "op": "subscribe",
            "args": [
                {
                    "instType": CONSTANTS.USDT_PRODUCT_TYPE,
                    "channel": CONSTANTS.WS_ACCOUNT_ENDPOINT,
                    "coin": "default"
                },
                {
                    "instType": CONSTANTS.USDT_PRODUCT_TYPE,
                    "channel": CONSTANTS.WS_POSITIONS_ENDPOINT,
                    "coin": "default"
                },
                {
                    "instType": CONSTANTS.USDT_PRODUCT_TYPE,
                    "channel": CONSTANTS.WS_ORDERS_ENDPOINT,
                    "coin": "default"
                },
            ]
        }

        self.assertTrue(
            self._is_logged("INFO", "Subscribed to private channels...")
        )
        self.assertEqual(2, len(sent_messages))
        self.assertEqual("login", authentication_request["op"])
        self.assertEqual(expected_payload, subscription_request)
        self.assertGreater(self.data_source.last_recv_time, initial_last_recv_time)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_authentication_failure(self, mock_ws: AsyncMock) -> None:
        """
        Test that listen_for_user_stream logs an error on authentication failure.

        :param mock_ws: Mocked WebSocket connection.
        """
        messages: asyncio.Queue = asyncio.Queue()
        error_response: Dict[str, Any] = self.ws_error_event_mock_response()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(error_response)
        )

        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_user_stream(messages)
        )
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Error authenticating the private websocket connection. "
                f"Response message {error_response}"
            )
        )
        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds..."
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_does_not_queue_empty_payload(
        self,
        mock_ws: AsyncMock
    ) -> None:
        """
        Test that listen_for_user_stream does not queue empty payloads.

        :param mock_ws: Mocked WebSocket connection.
        """
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        msg_queue: asyncio.Queue = asyncio.Queue()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_login_event_mock_response())
        )
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, "")

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_connection_failed(self, mock_ws: AsyncMock) -> None:
        """
        Test that listen_for_user_stream logs an error on connection failure.

        :param mock_ws: Mocked WebSocket connection.
        """
        mock_ws.side_effect = self.raise_test_exception
        msg_queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )
        await self.resume_test_event.wait()

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds..."
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listening_process_canceled_on_cancel_exception(self, mock_ws: AsyncMock) -> None:
        """
        Test that listen_for_user_stream raises a CancelledError when cancelled.

        :param mock_ws: Mocked WebSocket connection.
        """
        messages = asyncio.Queue()
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_user_stream(messages)
