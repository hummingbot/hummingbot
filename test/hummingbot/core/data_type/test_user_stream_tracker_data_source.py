import asyncio
import unittest
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class MockUserStreamTrackerDataSource(UserStreamTrackerDataSource):
    """Mock implementation for testing"""

    def __init__(self):
        super().__init__()
        self._manage_listen_key_task = None
        self._current_listen_key = None
        self._listen_key_initialized_event = asyncio.Event()

    async def _connected_websocket_assistant(self) -> WSAssistant:
        return AsyncMock(spec=WSAssistant)

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        pass


class TestUserStreamTrackerDataSource(IsolatedAsyncioWrapperTestCase):

    def setUp(self):
        self.data_source = MockUserStreamTrackerDataSource()

    def test_init(self):
        self.assertIsNone(self.data_source._ws_assistant)

    def test_logger_creation(self):
        logger = self.data_source.logger()
        self.assertIsNotNone(logger)
        self.assertEqual(logger, self.data_source._logger)

    def test_last_recv_time_no_ws_assistant(self):
        self.assertEqual(self.data_source.last_recv_time, 0)

    def test_last_recv_time_with_ws_assistant(self):
        mock_ws = MagicMock()
        mock_ws.last_recv_time = 123.456
        self.data_source._ws_assistant = mock_ws
        self.assertEqual(self.data_source.last_recv_time, 123.456)

    @patch('asyncio.sleep')
    async def test_sleep(self, mock_sleep):
        await self.data_source._sleep(1.5)
        mock_sleep.assert_called_once_with(1.5)

    def test_time(self):
        with patch('time.time', return_value=123.456):
            self.assertEqual(self.data_source._time(), 123.456)

    async def test_process_event_message_empty(self):
        queue = asyncio.Queue()
        await self.data_source._process_event_message({}, queue)
        self.assertTrue(queue.empty())

    async def test_process_event_message_non_empty(self):
        queue = asyncio.Queue()
        message = {"test": "data"}
        await self.data_source._process_event_message(message, queue)
        self.assertFalse(queue.empty())
        result = queue.get_nowait()
        self.assertEqual(result, message)

    async def test_on_user_stream_interruption_no_ws_assistant(self):
        await self.data_source._on_user_stream_interruption(None)

    async def test_on_user_stream_interruption_with_ws_assistant(self):
        mock_ws = AsyncMock()
        await self.data_source._on_user_stream_interruption(mock_ws)
        mock_ws.disconnect.assert_called_once()

    async def test_send_ping(self):
        mock_ws = AsyncMock()
        await self.data_source._send_ping(mock_ws)
        mock_ws.ping.assert_called_once()

    async def test_stop_with_manage_listen_key_task_not_done(self):
        # Test lines 95-101: Cancel and await _manage_listen_key_task when not done
        async def mock_coroutine():
            await asyncio.sleep(0.1)
            return "done"

        mock_task = asyncio.create_task(mock_coroutine())
        await asyncio.sleep(0.01)  # Let task start
        self.data_source._manage_listen_key_task = mock_task

        await self.data_source.stop()

        self.assertIsNone(self.data_source._manage_listen_key_task)

    async def test_stop_with_manage_listen_key_task_done(self):
        # Test that done tasks are not cancelled
        async def mock_coroutine():
            return "done"

        mock_task = asyncio.create_task(mock_coroutine())
        await mock_task  # Let it complete
        self.data_source._manage_listen_key_task = mock_task

        await self.data_source.stop()

        self.assertIsNone(self.data_source._manage_listen_key_task)

    async def test_stop_with_manage_listen_key_task_cancelled_error(self):
        # Test lines 99-100: Handle CancelledError when awaiting task
        async def mock_coroutine():
            raise asyncio.CancelledError()

        mock_task = asyncio.create_task(mock_coroutine())
        # Wait a bit to let task start
        await asyncio.sleep(0.01)
        self.data_source._manage_listen_key_task = mock_task

        await self.data_source.stop()

        self.assertIsNone(self.data_source._manage_listen_key_task)

    async def test_stop_clears_listen_key_state(self):
        # Test lines 104-107: Clear listen key state
        self.data_source._current_listen_key = "test_key"
        self.data_source._listen_key_initialized_event = asyncio.Event()
        self.data_source._listen_key_initialized_event.set()

        await self.data_source.stop()

        self.assertIsNone(self.data_source._current_listen_key)
        self.assertFalse(self.data_source._listen_key_initialized_event.is_set())

    async def test_stop_disconnects_ws_assistant(self):
        # Test lines 111-112: Disconnect and clear ws_assistant
        mock_ws = AsyncMock()
        self.data_source._ws_assistant = mock_ws

        await self.data_source.stop()

        mock_ws.disconnect.assert_called_once()
        self.assertIsNone(self.data_source._ws_assistant)

    async def test_stop_no_ws_assistant(self):
        # Test that stop works when no ws_assistant exists
        self.data_source._ws_assistant = None

        await self.data_source.stop()

        self.assertIsNone(self.data_source._ws_assistant)


if __name__ == '__main__':
    unittest.main()
