import asyncio
import concurrent.futures
import threading
import unittest
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase, async_to_sync


class TestIsolatedAsyncioWrapperTestCase(unittest.IsolatedAsyncioTestCase):
    def test_setUpClass_with_existing_loop(self):
        self.main_loop = asyncio.get_event_loop()

        IsolatedAsyncioWrapperTestCase.setUpClass()
        self.assertIsNotNone(IsolatedAsyncioWrapperTestCase.main_event_loop)
        self.assertEqual(self.main_loop, IsolatedAsyncioWrapperTestCase.main_event_loop)

        self.main_loop = None

    def test_setUpClass_with_new_loop(self):
        self.main_loop = asyncio.get_event_loop()
        self.local_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.local_loop)

        IsolatedAsyncioWrapperTestCase.setUpClass()
        self.assertIsNotNone(IsolatedAsyncioWrapperTestCase.main_event_loop)
        self.assertEqual(self.local_loop, IsolatedAsyncioWrapperTestCase.main_event_loop)

        self.local_loop.close()
        asyncio.set_event_loop(self.main_loop)
        self.main_loop = None

    def test_setUpClass_without_existing_loop(self):
        def run_test_in_thread(future):
            asyncio.set_event_loop(None)

            try:
                IsolatedAsyncioWrapperTestCase.setUpClass()
                self.assertIsNotNone(IsolatedAsyncioWrapperTestCase.main_event_loop)
                self.assertEqual(asyncio.get_event_loop(), IsolatedAsyncioWrapperTestCase.main_event_loop)
            except Exception as e:
                future.set_exception(e)
            else:
                future.set_result(None)

        future = concurrent.futures.Future()
        thread = threading.Thread(target=run_test_in_thread, args=(future,))
        thread.start()
        thread.join()
        future.result()

    def test_tearDownClass_with_existing_loop(self):
        self.main_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.main_loop)

        IsolatedAsyncioWrapperTestCase.main_event_loop = self.main_loop
        IsolatedAsyncioWrapperTestCase.tearDownClass()
        self.assertEqual(self.main_loop, asyncio.get_event_loop())

        self.main_loop.close()
        asyncio.set_event_loop(None)
        self.main_loop = None

    def test_tearDownClass_without_existing_loop(self):
        # Close the main event loop if it exists
        def run_test_in_thread(future):
            try:
                asyncio.set_event_loop(None)
                asyncio.get_event_loop()
            except RuntimeError:
                pass

            try:
                IsolatedAsyncioWrapperTestCase.tearDownClass()
                asyncio.get_event_loop()
            except Exception as e:
                future.set_exception(e)
            else:
                future.set_result(None)

        future = concurrent.futures.Future()
        thread = threading.Thread(target=run_test_in_thread, args=(future,))
        thread.start()
        thread.join()
        future.result()

    async def _dummy_coro(self, name, delay):
        """A dummy coroutine that simply sleeps for a delay."""
        await asyncio.sleep(delay)

    async def _dummy_coro_to_await(self, name, delay):
        """A dummy coroutine that simply sleeps for a delay."""
        await asyncio.sleep(delay)

    async def test_await_task_completion(self):
        # Create some tasks with different coroutine names
        task1 = asyncio.create_task(self._dummy_coro("task1", 0.5))
        task2 = asyncio.create_task(self._dummy_coro("task2", 0.75))
        task3 = asyncio.create_task(self._dummy_coro_to_await("task3", 2))

        # Use the await_task_completion method to wait for task1 and task2 to complete
        self.assertFalse(task1.done())
        self.assertFalse(task2.done())
        self.assertFalse(task3.done())

        await IsolatedAsyncioWrapperTestCase.await_task_completion(["_dummy_coro"])

        # At this point, task1 and task2 should be done, but task3 should still be running
        self.assertTrue(task1.done())
        self.assertTrue(task2.done())
        self.assertFalse(task3.done())

        # Now wait for task3 to complete as well
        await IsolatedAsyncioWrapperTestCase.await_task_completion("_dummy_coro_to_await")
        self.assertTrue(task3.done())


class TestAsyncToSyncInLoop(unittest.TestCase):
    @async_to_sync
    async def async_add(self, a: int, b: int) -> int:
        await asyncio.sleep(0.1)
        return a + b

    def test_async_add(self):
        result = self.async_add(1, 2)
        self.assertEqual(result, 3)

    @async_to_sync
    async def async_raise_exception(self) -> None:
        await asyncio.sleep(0.1)
        raise ValueError("Test exception")

    def test_async_raise_exception(self):
        with self.assertRaises(ValueError) as context:
            self.async_raise_exception()
        self.assertEqual(str(context.exception), "Test exception")

    def test_main_event_loop_unchanged(self):
        # Save the current event loop
        try:
            main_loop = asyncio.get_event_loop()
        except RuntimeError:
            # If no event loop exists, create one
            main_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(main_loop)

        # Run a function decorated with @async_to_sync
        self.async_add(1, 2)

        # Check that the current event loop is still the same
        self.assertEqual(main_loop, asyncio.get_event_loop())

    def test_main_event_loop_unchanged_after_exception(self):
        # Save the current event loop
        try:
            main_loop = asyncio.get_event_loop()
        except RuntimeError:
            # If no event loop exists, create one
            main_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(main_loop)

        # Run a function decorated with @async_to_sync that raises an exception
        with self.assertRaises(ValueError):
            self.async_raise_exception()

        # Check that the current event loop is still the same
        self.assertEqual(main_loop, asyncio.get_event_loop())


if __name__ == "__main__":
    unittest.main()
