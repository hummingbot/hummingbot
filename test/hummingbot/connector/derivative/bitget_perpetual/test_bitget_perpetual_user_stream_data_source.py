import asyncio
import json
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict

import hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_constants as CONSTANTS
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
        self.connector = BitgetPerpetualDerivative(
            bitget_perpetual_api_key="test_api_key",
            bitget_perpetual_secret_key="test_secret_key",
            bitget_perpetual_passphrase="test_passphrase",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        self.connector._unified_account = True
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
                "instType": CONSTANTS.INST_TYPE_UTA,
                "topic": channel
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
                    "instType": CONSTANTS.INST_TYPE_UTA,
                    "topic": CONSTANTS.WS_ACCOUNT_ENDPOINT
                },
                {
                    "instType": CONSTANTS.INST_TYPE_UTA,
                    "topic": CONSTANTS.WS_POSITIONS_ENDPOINT
                },
                {
                    "instType": CONSTANTS.INST_TYPE_UTA,
                    "topic": CONSTANTS.WS_ORDERS_ENDPOINT
                },
                {
                    "instType": CONSTANTS.INST_TYPE_UTA,
                    "topic": CONSTANTS.WS_FILL_ENDPOINT
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
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    async def test_listen_for_user_stream_connection_failed(self, sleep_mock: AsyncMock, mock_ws: AsyncMock) -> None:
        """
        A failed connection is logged, waited out and retried.

        :param sleep_mock: Mocked retry sleep; the second call ends the listener.
        :param mock_ws: Mocked WebSocket connection.
        """
        mock_ws.side_effect = Exception("Test Error")
        sleep_mock.side_effect = [None, asyncio.CancelledError()]
        msg_queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_user_stream(msg_queue)

        self.assertEqual(2, mock_ws.call_count)
        self.assertIsNone(self.data_source._ws_assistant)
        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds..."
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    async def test_listen_for_user_stream_iter_message_throws_exception(
        self, sleep_mock: AsyncMock, mock_ws: AsyncMock
    ) -> None:
        """
        An error while reading the stream tears the session down: the ping task stops and the
        websocket reference is cleared before the retry.

        :param sleep_mock: Mocked retry sleep, which ends the listener.
        :param mock_ws: Mocked WebSocket connection.
        """
        self.data_source._refresh_server_time_offset = AsyncMock()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_login_event_mock_response())
        )
        self.mocking_assistant.add_websocket_aiohttp_exception(
            websocket_mock=mock_ws.return_value,
            exception=Exception("Test Error")
        )
        sleep_mock.side_effect = asyncio.CancelledError
        msg_queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_user_stream(msg_queue)

        self.assertEqual(1, mock_ws.call_count)
        self.assertIsNone(self.data_source._ws_assistant)
        self.assertIsNone(self.data_source._ping_task)
        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds..."
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_sends_one_ping_after_subscribing(self, mock_ws: AsyncMock) -> None:
        self.data_source._refresh_server_time_offset = AsyncMock()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_login_event_mock_response())
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_subscribed_mock_response(CONSTANTS.WS_ORDERS_ENDPOINT))
        )

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(asyncio.Queue())
        )
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(
            [CONSTANTS.PUBLIC_WS_PING_REQUEST],
            self.mocking_assistant.text_messages_sent_through_websocket(mock_ws.return_value)
        )
        self.assertIsNotNone(self.data_source._ping_task)

    async def test_send_interval_ping_waits_one_interval_before_pinging(self) -> None:
        ws = AsyncMock()
        ping_task = self.local_event_loop.create_task(self.data_source.send_interval_ping(ws))
        await asyncio.sleep(0)

        ws.send.assert_not_called()
        ping_task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await ping_task

    async def test_user_stream_interruption_stops_the_ping_task(self) -> None:
        ws = AsyncMock()
        await self.data_source._subscribe_channels(websocket_assistant=ws)
        ping_task = self.data_source._ping_task

        await self.data_source._on_user_stream_interruption(websocket_assistant=ws)

        self.assertTrue(ping_task.cancelled())
        self.assertIsNone(self.data_source._ping_task)
        ws.disconnect.assert_awaited_once()

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

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_rejects_login_echo_with_error_code(
        self,
        mock_ws: AsyncMock
    ) -> None:
        """
        A response echoing the "login" event but carrying a non-zero code is a rejected session.
        The listener must fail authentication rather than subscribe on it.

        :param mock_ws: Mocked WebSocket connection.
        """
        failed_login: Dict[str, Any] = self.ws_login_event_mock_response()
        failed_login["code"] = "30005"
        failed_login["msg"] = "Login failed"

        messages: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(failed_login)
        )

        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_user_stream(messages)
        )
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Error authenticating the private websocket connection. "
                f"Response message {failed_login}"
            )
        )
        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds..."
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_restarts_when_subscription_is_rejected(
        self,
        mock_ws: AsyncMock
    ) -> None:
        """
        A rejected private subscription leaves the connection up but silent, so the listener must
        tear the session down and reconnect instead of only logging. It pauses first, so a
        rejection that never clears does not reconnect about once a second.

        :param mock_ws: Mocked WebSocket connection.
        """
        error_response: Dict[str, Any] = self.ws_error_event_mock_response()

        messages: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_login_event_mock_response())
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(error_response)
        )

        async def _sleep(delay: float) -> None:
            # Return at once from the rejection pause, and park the listener's own retry wait so it
            # does not reconnect while the test checks what happened.
            if delay != CONSTANTS.WS_SUBSCRIPTION_RETRY_INTERVAL_SECONDS:
                await asyncio.Event().wait()

        self.data_source._sleep = AsyncMock(side_effect=_sleep)
        self.data_source._refresh_server_time_offset = AsyncMock()
        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_user_stream(messages)
        )
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, messages.qsize())
        self.assertTrue(
            self._is_logged(
                "ERROR",
                f"Failed to subscribe to private channels: {error_response['msg']} ({error_response['code']})"
            )
        )
        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds..."
            )
        )
        self.data_source._sleep.assert_any_await(CONSTANTS.WS_SUBSCRIPTION_RETRY_INTERVAL_SECONDS)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_authenticate_refreshes_the_server_time_offset_first(
        self,
        mock_ws: AsyncMock
    ) -> None:
        """
        The login signature is rejected once its timestamp drifts more than 30 seconds from the
        exchange clock (30014). TimeSynchronizer derives that timestamp from perf_counter, which
        stalls while the host is suspended, so the offset has to be re-sampled before signing.
        """
        self.data_source._refresh_server_time_offset = AsyncMock()

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_login_event_mock_response())
        )

        output_queue: asyncio.Queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(output=output_queue)
        )
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.data_source._refresh_server_time_offset.assert_called()

    @patch("hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_web_utils.get_current_server_time", new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_authenticate_keeps_the_existing_offset_when_the_time_resync_fails(
        self,
        mock_ws: AsyncMock,
        server_time_mock: AsyncMock
    ) -> None:
        """
        A failed resync must not block the login, and must not cost the offset the connector
        already has: with no samples left the synchronizer signs with the local clock, which the
        exchange refuses (30014) whenever that clock is more than 30 seconds out.
        """
        synchronizer = self.connector._time_synchronizer
        for _ in range(5):
            synchronizer.add_time_offset_ms_sample(-60_000.0)
        server_time_mock.side_effect = IOError("server time unavailable")

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_login_event_mock_response())
        )

        output_queue: asyncio.Queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(output=output_queue)
        )
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        sent = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=mock_ws.return_value
        )
        self.assertEqual("login", sent[0]["op"])
        server_time_mock.assert_awaited()
        self.assertEqual(-60_000.0, synchronizer.time_offset_ms)

    @patch("hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_web_utils.get_current_server_time", new_callable=AsyncMock)
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_authenticate_discards_stale_clock_samples_before_resampling(
        self,
        mock_ws: AsyncMock,
        server_time_mock: AsyncMock
    ) -> None:
        """
        TimeSynchronizer derives its offset from the median and weighted average of a five-sample
        deque, so appending one fresh sample to five stale ones barely moves it: after an
        hour-long suspend the offset is still around 49 minutes out, well outside the exchange's
        30-second window, and five fresh samples are needed to recover. The stale samples have to
        be discarded for the refresh to mean anything.
        """
        synchronizer = self.connector._time_synchronizer
        for _ in range(5):
            synchronizer.add_time_offset_ms_sample(-3_600_000.0)
        self.assertEqual(-3_600_000.0, synchronizer.time_offset_ms)
        # Freeze the local counter so the fresh sample is exactly the server time minus it.
        synchronizer._current_seconds_counter = MagicMock(return_value=1_000.0)
        server_time_mock.return_value = 1_000_000.0

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_login_event_mock_response())
        )

        output_queue: asyncio.Queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(output=output_queue)
        )
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        # One fresh sample is now the whole offset, so the login timestamp is usable again.
        self.assertEqual(0.0, synchronizer.time_offset_ms)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_unified_account_connects_to_the_v3_private_websocket(self, mock_ws: AsyncMock) -> None:
        self.data_source._refresh_server_time_offset = AsyncMock()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(self.ws_login_event_mock_response())
        )

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(asyncio.Queue())
        )
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual("wss://ws.bitget.com/v3/ws/private", mock_ws.call_args.args[0])
