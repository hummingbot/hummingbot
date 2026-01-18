import asyncio
import unittest
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, patch

from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource


class MockUserStreamTrackerDataSource(UserStreamTrackerDataSource):
    """Mock implementation for testing"""

    def __init__(self):
        super().__init__()
        self._mock_last_recv_time = 123.456

    @property
    def last_recv_time(self) -> float:
        return self._mock_last_recv_time

    async def _connected_websocket_assistant(self):
        return AsyncMock()

    async def _subscribe_channels(self, websocket_assistant):
        pass

    async def listen_for_user_stream(self, output: asyncio.Queue):
        # Mock implementation that puts test data
        await output.put({"test": "data"})

    async def stop(self):
        pass


class TestUserStreamTracker(IsolatedAsyncioWrapperTestCase):

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mock_data_source = MockUserStreamTrackerDataSource()
        self.tracker = UserStreamTracker(self.mock_data_source)

    def test_init(self):
        self.assertIsInstance(self.tracker._user_stream, asyncio.Queue)
        self.assertEqual(self.tracker._data_source, self.mock_data_source)
        self.assertIsNone(self.tracker._user_stream_tracking_task)

    def test_logger_creation(self):
        logger = self.tracker.logger()
        self.assertIsNotNone(logger)
        self.assertEqual(logger, self.tracker._ust_logger)

    def test_data_source_property(self):
        self.assertEqual(self.tracker.data_source, self.mock_data_source)

    def test_last_recv_time_property(self):
        self.assertEqual(self.tracker.last_recv_time, 123.456)

    def test_user_stream_property(self):
        self.assertIsInstance(self.tracker.user_stream, asyncio.Queue)

    async def test_start_no_existing_task(self):
        # Test normal start when no task exists
        self.assertIsNone(self.tracker._user_stream_tracking_task)

        # Mock the listen_for_user_stream to complete immediately
        async def mock_listen(*args):
            return None

        with patch.object(self.tracker._data_source, 'listen_for_user_stream', side_effect=mock_listen):
            await self.tracker.start()

            self.assertIsNotNone(self.tracker._user_stream_tracking_task)
            self.assertTrue(self.tracker._user_stream_tracking_task.done())

    async def test_start_with_existing_done_task(self):
        # Test start when existing task is done
        async def mock_coroutine():
            return "done"

        mock_existing_task = asyncio.create_task(mock_coroutine())
        await mock_existing_task  # Let it complete
        self.tracker._user_stream_tracking_task = mock_existing_task

        # Mock the listen_for_user_stream to complete immediately
        async def mock_listen(*args):
            return None

        with patch.object(self.tracker._data_source, 'listen_for_user_stream', side_effect=mock_listen), \
             patch.object(self.tracker, 'stop') as mock_stop:

            await self.tracker.start()

            mock_stop.assert_called_once()
            self.assertIsNotNone(self.tracker._user_stream_tracking_task)
            self.assertTrue(self.tracker._user_stream_tracking_task.done())

    async def test_start_with_existing_running_task(self):
        # Test line 35: return early if task is not done
        async def mock_coroutine():
            await asyncio.sleep(0.1)
            return "done"

        mock_existing_task = asyncio.create_task(mock_coroutine())
        await asyncio.sleep(0.01)  # Let task start
        self.tracker._user_stream_tracking_task = mock_existing_task

        with patch('hummingbot.core.utils.async_utils.safe_ensure_future') as mock_safe_ensure_future, \
             patch.object(self.tracker, 'stop') as mock_stop:

            await self.tracker.start()

            # Should return early without calling stop or creating new task
            mock_stop.assert_not_called()
            mock_safe_ensure_future.assert_not_called()
            self.assertEqual(self.tracker._user_stream_tracking_task, mock_existing_task)

    async def test_stop_no_task(self):
        # Test stop when no task exists
        self.assertIsNone(self.tracker._user_stream_tracking_task)

        with patch.object(self.tracker._data_source, 'stop') as mock_data_source_stop:
            await self.tracker.stop()
            mock_data_source_stop.assert_called_once()
            self.assertIsNone(self.tracker._user_stream_tracking_task)

    async def test_stop_with_done_task(self):
        # Test stop when task is done
        async def mock_coroutine():
            return "done"

        mock_task = asyncio.create_task(mock_coroutine())
        await mock_task  # Let it complete
        self.tracker._user_stream_tracking_task = mock_task

        with patch.object(self.tracker._data_source, 'stop') as mock_data_source_stop:
            await self.tracker.stop()

            mock_data_source_stop.assert_called_once()
            self.assertIsNone(self.tracker._user_stream_tracking_task)

    async def test_stop_with_running_task(self):
        # Test lines 48-52: Cancel and await running task
        async def mock_coroutine():
            await asyncio.sleep(0.1)
            return "done"

        mock_task = asyncio.create_task(mock_coroutine())
        await asyncio.sleep(0.01)  # Let task start
        self.tracker._user_stream_tracking_task = mock_task

        with patch.object(self.tracker._data_source, 'stop') as mock_data_source_stop:
            await self.tracker.stop()

            mock_data_source_stop.assert_called_once()
            self.assertIsNone(self.tracker._user_stream_tracking_task)

    async def test_stop_with_cancelled_error(self):
        # Test lines 51-52: Handle CancelledError when awaiting task
        async def mock_coroutine():
            raise asyncio.CancelledError()

        mock_task = asyncio.create_task(mock_coroutine())
        await asyncio.sleep(0.01)  # Let task start
        self.tracker._user_stream_tracking_task = mock_task

        with patch.object(self.tracker._data_source, 'stop') as mock_data_source_stop:
            await self.tracker.stop()

            mock_data_source_stop.assert_called_once()
            self.assertIsNone(self.tracker._user_stream_tracking_task)


if __name__ == '__main__':
    unittest.main()
