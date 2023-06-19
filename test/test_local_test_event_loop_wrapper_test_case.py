import asyncio
import time
import unittest
from test.isolated_asyncio_wrapper_test_case import LocalTestEventLoopWrapperTestCase


class TestLocalTestEventLoopWrapperTestCase(unittest.TestCase):
    def setUp(self):
        self.test_case = LocalTestEventLoopWrapperTestCase()
        self.test_case.setUpClass()

    def tearDown(self):
        self.test_case.tearDownClass()

    def test_setUp_with_existing_loop(self):
        self.main_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.main_loop)

        self.test_case.setUp()
        self.assertIsNotNone(self.test_case.local_event_loop)
        self.assertEqual(self.test_case.local_event_loop, asyncio.get_event_loop())
        self.assertNotEqual(self.main_loop, self.test_case.local_event_loop)

        self.main_loop.close()
        asyncio.set_event_loop(None)
        self.main_loop = None

    def test_setUp_without_existing_loop(self):
        # Close the main event loop if it exists
        try:
            loop = asyncio.get_event_loop()
            loop.close()
            asyncio.set_event_loop(None)
        except RuntimeError:
            pass

        self.test_case.setUp()
        self.assertIsNotNone(self.test_case.local_event_loop)
        self.assertEqual(self.test_case.local_event_loop, asyncio.get_event_loop())

    def test_tearDown_with_existing_loop(self):
        self.main_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.main_loop)

        self.test_case.local_event_loop = self.main_loop
        self.test_case.tearDown()
        self.assertIsNone(self.test_case.local_event_loop)
        self.assertEqual(self.main_loop, asyncio.get_event_loop())

        self.main_loop.close()
        asyncio.set_event_loop(None)
        self.main_loop = None

    def test_tearDown_without_existing_loop(self):
        # Close the main event loop if it exists
        try:
            loop = asyncio.get_event_loop()
            loop.close()
            asyncio.set_event_loop(None)
        except RuntimeError:
            pass

        self.test_case.tearDown()
        self.assertIsNone(self.test_case.local_event_loop)

        # Verify that get_event_loop still raises a RuntimeError, indicating that no event loop exists
        with self.assertRaises(RuntimeError):
            asyncio.get_event_loop()

    def test_tearDownClass_with_existing_loop(self):
        self.main_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.main_loop)

        LocalTestEventLoopWrapperTestCase.main_event_loop = self.main_loop
        self.test_case.tearDownClass()
        self.assertIsNone(LocalTestEventLoopWrapperTestCase.main_event_loop)
        self.assertEqual(self.main_loop, asyncio.get_event_loop())

        self.main_loop.close()
        asyncio.set_event_loop(None)
        self.main_loop = None

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
