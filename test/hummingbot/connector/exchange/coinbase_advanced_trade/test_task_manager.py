import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock, patch

from hummingbot.connector.exchange.coinbase_advanced_trade.task_manager import TaskManager, TaskState


class TestTaskManager(IsolatedAsyncioWrapperTestCase):
    async def asyncSetUp(self) -> None:
        self.wrapper = TaskManager(asyncio.sleep, 1)

    async def test_initial_state(self):
        wrapper = TaskManager(asyncio.sleep, 1)
        self.assertEqual(wrapper._task_state, TaskState.STOPPED)
        self.assertIsNone(wrapper._task)
        self.assertIsNone(wrapper._task_exception)

    async def test_state_transitions(self):
        wrapper = TaskManager(asyncio.sleep, 1)
        await wrapper.start_task()
        self.assertEqual(wrapper._task_state, TaskState.CREATED)
        await asyncio.sleep(1.1)  # give the task time to finish
        self.assertEqual(wrapper._task_state, TaskState.STOPPED)

    async def test_logging(self):
        wrapper = TaskManager(asyncio.sleep, 1)
        with patch.object(TaskManager, "_logger") as mock_logger:
            await wrapper.start_task()
            await wrapper.start_task()
            mock_logger.error.assert_called_with("Cannot start a Task Manager that is already started")

    async def test_start_with_task(self) -> None:
        self.assertIsNone(self.wrapper._task)
        await self.wrapper.start_task()
        self.assertIsNotNone(self.wrapper._task)
        self.assertFalse(self.wrapper._task.done())

    async def test_stop_with_start(self) -> None:
        await self.wrapper.start_task()
        await self.wrapper.stop_task()
        await asyncio.sleep(0.1)
        self.assertIsNone(self.wrapper._task)

    async def test_start_while_running(self) -> None:
        await self.wrapper.start_task()
        with patch.object(TaskManager, "logger") as mock_logger:
            await self.wrapper.start_task()
            mock_logger.assert_called()

    async def test_stop_while_running(self) -> None:
        await self.wrapper.start_task()
        await self.wrapper.stop_task()
        await self.wrapper.stop_task()

    async def test_task_completion(self) -> None:
        await self.wrapper.start_task()
        self.assertFalse(self.wrapper._task.done())
        await asyncio.sleep(1.01)  # give the task time to finish
        self.assertIsNone(self.wrapper._task)

    async def test_task_exception(self):
        # Create a task that raises an exception

        async def failing_task():
            await asyncio.sleep(0.1)
            raise RuntimeError("Task failed")

        wrapper = TaskManager(failing_task)
        # Start the task
        await wrapper.start_task()

        # The task should be running
        self.assertTrue(wrapper._task)

        # Wait for the task to fail
        await asyncio.sleep(0.2)

        # Check that the task has indeed failed
        self.assertIsInstance(wrapper._task_exception, RuntimeError)
        self.assertEqual(str(wrapper._task_exception), "Task failed")

        # The task should not be running
        self.assertTrue(wrapper._task.done())

    async def test_success_callback(self):
        callback = MagicMock()

        async def successful_task():
            await asyncio.sleep(0.1)

        wrapper = TaskManager(successful_task, success_callback=callback)
        await wrapper.start_task()
        await asyncio.sleep(0.2)  # give the task time to finish

        callback.assert_called_once()

    async def test_exception_callback(self):
        callback = MagicMock()

        async def failing_task():
            await asyncio.sleep(0.1)
            raise RuntimeError("Task failed")

        wrapper = TaskManager(failing_task, exception_callback=callback)
        await wrapper.start_task()
        await asyncio.sleep(0.2)  # give the task time to fail

        callback.assert_called_once_with(wrapper._task_exception)

    async def test_success_event(self):
        event = asyncio.Event()

        async def successful_task():
            await asyncio.sleep(0.1)

        wrapper = TaskManager(successful_task, success_event=event)
        await wrapper.start_task()

        # Wait for the task to finish and the event to be set
        await event.wait()
        self.assertTrue(event.is_set())

    async def test_exception_event(self):
        event = asyncio.Event()

        async def failing_task():
            await asyncio.sleep(0.1)
            raise RuntimeError("Task failed")

        wrapper = TaskManager(failing_task, exception_event=event)
        await wrapper.start_task()

        # Wait for the task to fail and the event to be set
        await event.wait()
        self.assertTrue(event.is_set())
