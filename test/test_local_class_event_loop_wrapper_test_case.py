import asyncio
import time
import unittest
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase, LocalClassEventLoopWrapperTestCase


class TestLocalClassEventLoopWrapperTestCase(unittest.TestCase):
    def setUp(self):
        self.test_case = LocalClassEventLoopWrapperTestCase()
        self.test_case.setUpClass()

    def tearDown(self):
        self.test_case.tearDownClass()

    def test_setUpClass_with_existing_loop(self):
        self.main_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.main_loop)

        LocalClassEventLoopWrapperTestCase.setUpClass()
        self.assertIsNotNone(LocalClassEventLoopWrapperTestCase.main_event_loop)
        self.assertEqual(self.main_loop, LocalClassEventLoopWrapperTestCase.main_event_loop)
        self.assertNotEqual(self.main_loop, LocalClassEventLoopWrapperTestCase.local_event_loop)

        self.main_loop = None

    def test_setUpClass_without_existing_loop(self):
        # Close the main event loop if it exists
        asyncio.set_event_loop(None)

        # Call setUpClass and verify that it does not create a new event loop
        LocalClassEventLoopWrapperTestCase.setUpClass()
        self.assertIsNotNone(LocalClassEventLoopWrapperTestCase.main_event_loop)
        self.assertEqual(asyncio.get_event_loop(), LocalClassEventLoopWrapperTestCase.local_event_loop)

    def test_tearDownClass_with_existing_loop(self):
        self.main_loop = asyncio.new_event_loop()

        LocalClassEventLoopWrapperTestCase.main_event_loop = self.main_loop
        LocalClassEventLoopWrapperTestCase.local_event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(LocalClassEventLoopWrapperTestCase.local_event_loop)

        LocalClassEventLoopWrapperTestCase.tearDownClass()
        self.assertIsNone(LocalClassEventLoopWrapperTestCase.main_event_loop)
        self.assertIsNone(LocalClassEventLoopWrapperTestCase.local_event_loop)
        self.assertEqual(self.main_loop, asyncio.get_event_loop())

        self.main_loop.close()
        asyncio.set_event_loop(None)
        self.main_loop = None

    def test_exception_in_test_case(self):
        IsolatedAsyncioWrapperTestCase.setUpClass()

        try:
            # Simulate a test case that raises an exception
            raise Exception("Test exception")
        except Exception:
            pass

        # Despite the exception, tearDownClass should still correctly clean up the event loop
        LocalClassEventLoopWrapperTestCase.tearDownClass()
        self.assertIsNone(LocalClassEventLoopWrapperTestCase.main_event_loop)

    def test_run_async_with_timeout(self):
        self.test_case.setUp()

        # Test a coroutine that finishes before the timeout
        start_time = time.time()
        result = self.test_case.run_async_with_timeout(asyncio.sleep(0.1), timeout=1.0)
        end_time = time.time()
        self.assertIsNone(result)
        self.assertLess(end_time - start_time, 1.0)

        # Test a coroutine that doesn't finish before the timeout
        with self.assertRaises(asyncio.TimeoutError):
            self.test_case.run_async_with_timeout(asyncio.sleep(2.0), timeout=1.0)

        self.test_case.tearDown()


if __name__ == "__main__":
    unittest.main()
