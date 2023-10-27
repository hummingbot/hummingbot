import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock, patch

from hummingbot.connector.exchange.coinbase_advanced_trade.task_manager import (
    TaskManager,
    TaskManagerException,
    TaskState,
)


class TestTaskManager(IsolatedAsyncioWrapperTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.task_manager = TaskManager(asyncio.sleep, 1)

    async def test_initial_state(self):
        self.assertIsNone(self.task_manager._success_callback)
        self.assertIsNone(self.task_manager._exception_callback)
        self.assertIsNone(self.task_manager._success_event)
        self.assertIsNone(self.task_manager._exception_event)

        self.assertTrue(callable(self.task_manager.task_function))

        self.assertEqual(self.task_manager._task_state, TaskState.STOPPED)
        self.assertIsNone(self.task_manager._task)
        self.assertIsNone(self.task_manager._task_exception)

    async def test_initial_state_with_params(self):
        # Creating a mock callback function
        def mock_success_callback():
            pass

        def mock_exception_callback():
            pass

        mock_success_event = asyncio.Event()
        mock_exception_event = asyncio.Event()

        self.task_manager = TaskManager(
            asyncio.sleep,
            1,
            success_callback=mock_success_callback,
            exception_callback=mock_exception_callback,
            success_event=mock_success_event,
            exception_event=mock_exception_event
        )

        # Check that the TaskManager is correctly initialized
        self.assertEqual(self.task_manager._success_callback, mock_success_callback)
        self.assertEqual(self.task_manager._exception_callback, mock_exception_callback)
        self.assertEqual(self.task_manager._success_event, mock_success_event)
        self.assertEqual(self.task_manager._exception_event, mock_exception_event)

        self.assertTrue(callable(self.task_manager.task_function))

        self.assertEqual(self.task_manager._task_state, TaskState.STOPPED)
        self.assertIsNone(self.task_manager._task)
        self.assertIsNone(self.task_manager._task_exception)

    async def test_task_state_transitions(self):
        self.assertEqual(self.task_manager._task_state, TaskState.STOPPED)
        task = asyncio.create_task(self.task_manager._task_wrapper())
        await asyncio.sleep(0.1)  # Give the task a moment to start
        self.assertEqual(self.task_manager._task_state, TaskState.STARTED)
        await task
        self.assertEqual(self.task_manager._task_state, TaskState.STOPPED)

    async def test_logging(self):
        with patch.object(TaskManager, "_logger") as mock_logger:
            await self.task_manager.stop_task()
            mock_logger.debug.assert_called_with("Attempting to stop_task() a task that has not been created (or "
                                                 "already stopped)")
            self.task_manager.stop_task_nowait()
            mock_logger.debug.assert_called_with("Attempting to stop_task_nowait() a task that has not been created ("
                                                 "or already stopped)")
            await self.task_manager.start_task()
            await self.task_manager.start_task()
            mock_logger.debug.assert_called_with("Cannot start_task() a Task Manager that is already started")

    async def test_start_with_task(self) -> None:
        self.assertIsNone(self.task_manager._task)
        await self.task_manager.start_task()
        self.assertIsNotNone(self.task_manager._task)
        self.assertFalse(self.task_manager._task.done())

    async def test_stop_with_start(self) -> None:
        await self.task_manager.start_task()
        await self.task_manager.stop_task()
        await asyncio.sleep(0.1)
        self.assertIsNone(self.task_manager._task)

    async def test_start_while_running(self) -> None:
        await self.task_manager.start_task()
        with patch.object(TaskManager, "logger") as mock_logger:
            await self.task_manager.start_task()
            mock_logger.assert_called()

    async def test_stop_while_running(self) -> None:
        await self.task_manager.start_task()
        await self.task_manager.stop_task()
        await self.task_manager.stop_task()

    async def test_task_completion(self) -> None:
        await self.task_manager.start_task()
        self.assertFalse(self.task_manager._task.done())
        await asyncio.sleep(1.01)  # give the task time to finish
        self.assertIsNone(self.task_manager._task)

    async def test_task_exception(self):
        # Create a task that raises an exception

        async def failing_task():
            await asyncio.sleep(1)
            raise RuntimeError("Task failed")

        self.task_manager = TaskManager(failing_task)
        # Start the task
        await self.task_manager.start_task()
        await asyncio.sleep(0.1)  # give the task time to start

        # The task should be running
        self.assertTrue(self.task_manager.is_running)

        # Wait for the task to fail
        await asyncio.sleep(1)

        # Check that the task has indeed failed
        self.assertIsInstance(self.task_manager._task_exception, TaskManagerException)
        self.assertTrue("Task failed" in str(self.task_manager._task_exception))

        # The task should not be running
        self.assertFalse(self.task_manager.is_running)

    async def test_success_callback(self):
        callback = MagicMock()

        async def successful_task():
            await asyncio.sleep(0.1)

        self.task_manager = TaskManager(successful_task, success_callback=callback)
        await self.task_manager.start_task()
        await asyncio.sleep(0.2)  # give the task time to finish

        callback.assert_called_once()
        self.assertIsNone(self.task_manager.task_exception)

    async def test_exception_callback(self):
        callback = MagicMock()

        async def failing_task():
            await asyncio.sleep(0.1)
            raise RuntimeError("Task failed")

        self.task_manager = TaskManager(failing_task, exception_callback=callback)
        await self.task_manager.start_task()
        await asyncio.sleep(0.2)  # give the task time to fail

        callback.assert_called_once()
        self.assertIsInstance(self.task_manager.task_exception, TaskManagerException)

    async def test_success_event(self):
        event = asyncio.Event()

        async def successful_task():
            await asyncio.sleep(0.1)

        self.task_manager = TaskManager(successful_task, success_event=event)
        await self.task_manager.start_task()

        # Wait for the task to finish and the event to be set
        await event.wait()
        self.assertTrue(event.is_set())
        self.assertIsNone(self.task_manager.task_exception)

    async def test_exception_event(self):
        event = asyncio.Event()

        class CustomException(Exception):
            pass

        async def failing_task():
            await asyncio.sleep(1)
            raise CustomException("Task failed")

        self.task_manager = TaskManager(failing_task, exception_event=event)
        await self.task_manager.start_task()

        # Wait for the task to fail and the event to be set
        await event.wait()
        self.assertTrue(event.is_set())
        self.assertIsInstance(self.task_manager.task_exception, TaskManagerException)
